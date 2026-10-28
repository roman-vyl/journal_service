import json
import sqlite3
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from journal_service.health import build_server
from journal_service.stats import IngestStats
from journal_service.storage import Store
from journal_service.tailer import Tailer
from tests.support import (
    ENTRY,
    append,
    applied,
    closed,
    declined,
    ended,
    live_entry,
    open_trade,
    opened,
    protection,
)

STEP = 300_000
B0 = 1_760_000_000_000


class Api:
    def __init__(self, tmp_path: Path) -> None:
        self.journal = tmp_path / "runtime.jsonl"
        self.journal.touch()
        self.db_path = tmp_path / "journal.sqlite3"
        self.store = Store(self.db_path)
        self.stats = IngestStats()
        self.tailer = Tailer(
            store=self.store, source="runtime", path=self.journal, stats=self.stats
        )
        self.server = build_server("127.0.0.1", 0, "runtime", self.stats, self.db_path)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def ingest(self, *records: Any) -> None:
        append(self.journal, *records)
        self.tailer.poll_once()

    def get(self, path: str) -> tuple[int, Any]:
        try:
            with urllib.request.urlopen(self.base + path, timeout=3) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.store.close()


@pytest.fixture
def api(tmp_path: Path) -> Iterator[Api]:
    rig = Api(tmp_path)
    try:
        yield rig
    finally:
        rig.close()


def bar(i: int) -> int:
    return B0 + i * STEP


def test_range_is_inclusive_and_ordered(api: Api) -> None:
    api.ingest(*[live_entry(f"e{i}", bar(i), instance="s1") for i in range(1, 11)])
    status, body = api.get(
        f"/v1/events?strategy_instance_id=s1&from_bar_ms={bar(3)}&to_bar_ms={bar(6)}"
    )
    assert status == 200
    assert [e["bar_open_time_ms"] for e in body["events"]] == [bar(i) for i in (3, 4, 5, 6)]
    assert body["truncated"] is False
    first = body["events"][0]
    assert set(first) == {
        "event_id", "event_type", "schema_version", "occurred_at",
        "strategy_instance_id", "trade_cycle_id", "bar_open_time_ms", "body",
    }  # fmt: skip
    assert first["trade_cycle_id"] is None


def test_null_and_signal_returned_unchanged_and_missing_bar_absent(api: Api) -> None:
    sig = live_entry(
        "e2", bar(2), desired_entry={**ENTRY, "planned_entry_price": "1.23456789012345678901"}
    )
    api.ingest(live_entry("e1", bar(1)), sig, live_entry("e4", bar(4)))
    _, body = api.get("/v1/events?strategy_instance_id=ema_pullback:abc")
    assert [e["bar_open_time_ms"] for e in body["events"]] == [bar(1), bar(2), bar(4)]
    assert body["events"][0]["body"]["payload"]["desired_entry"] is None
    assert body["events"][1]["body"] == sig
    assert body["events"][1]["body"]["payload"]["desired_entry"]["planned_entry_price"] == (
        "1.23456789012345678901"
    )


def test_bar_evaluated_twice_returns_both(api: Api) -> None:
    api.ingest(live_entry("a", bar(1)), live_entry("b", bar(1)))
    _, body = api.get("/v1/events?strategy_instance_id=ema_pullback:abc")
    assert [e["event_id"] for e in body["events"]] == ["a", "b"]


def test_applied_entry_is_stored_with_cycle_and_returned_with_its_evaluation(api: Api) -> None:
    evaluation = live_entry("e1", bar(1), desired_entry=ENTRY)
    entry = applied("a1", bar(1), cycle="cycle-9")
    api.ingest(evaluation, entry, live_entry("e2", bar(2)))
    _, body = api.get(
        f"/v1/events?strategy_instance_id=ema_pullback:abc&from_bar_ms={bar(1)}&to_bar_ms={bar(1)}"
    )
    assert [e["event_type"] for e in body["events"]] == [
        "live_entry_evaluated",
        "entry_package_applied",
    ]
    assert body["events"][1]["body"] == entry
    db = sqlite3.connect(api.db_path)
    rows = db.execute(
        "SELECT trade_cycle_id, bar_open_time_ms FROM events WHERE event_id = 'a1'"
    ).fetchall()
    db.close()
    assert rows == [("cycle-9", bar(1))]


def test_other_instances_not_mixed_in(api: Api) -> None:
    api.ingest(live_entry("a", bar(1), instance="s1"), live_entry("b", bar(1), instance="s2"))
    _, body = api.get("/v1/events?strategy_instance_id=s1")
    assert [e["event_id"] for e in body["events"]] == ["a"]


def test_limit_truncates_oldest_first(api: Api) -> None:
    api.ingest(*[live_entry(f"e{i}", bar(i), instance="s1") for i in range(1, 6)])
    _, body = api.get("/v1/events?strategy_instance_id=s1&limit=3")
    assert [e["bar_open_time_ms"] for e in body["events"]] == [bar(1), bar(2), bar(3)]
    assert body["truncated"] is True
    _, body = api.get("/v1/events?strategy_instance_id=s1&limit=5")
    assert body["truncated"] is False


@pytest.mark.parametrize(
    "query",
    [
        "",
        "strategy_instance_id=",
        "strategy_instance_id=s1&from_bar_ms=x",
        "strategy_instance_id=s1&to_bar_ms=1.5",
        "strategy_instance_id=s1&limit=abc",
        "strategy_instance_id=s1&limit=0",
        "strategy_instance_id=s1&from_bar_ms=10&to_bar_ms=5",
    ],
)
def test_invalid_requests_are_400(api: Api, query: str) -> None:
    status, body = api.get(f"/v1/events?{query}")
    assert status == 400
    assert isinstance(body["error"], str) and body["error"]


def test_range_returns_every_record_without_limit(api: Api) -> None:
    count = 12_000
    api.ingest(*[live_entry(f"e{i}", bar(i), instance="s1") for i in range(1, count + 1)])
    status, body = api.get("/v1/events?strategy_instance_id=s1")
    assert status == 200 and body["truncated"] is False
    assert [e["bar_open_time_ms"] for e in body["events"]] == [bar(i) for i in range(1, count + 1)]
    _, part = api.get(
        f"/v1/events?strategy_instance_id=s1&from_bar_ms={bar(101)}&to_bar_ms={bar(9100)}"
    )
    assert len(part["events"]) == 9000 and part["truncated"] is False


def test_unknown_path_is_404(api: Api) -> None:
    assert api.get("/v1/other")[0] == 404


def test_strategy_instances(api: Api) -> None:
    assert api.get("/v1/strategy-instances") == (200, {"strategy_instances": []})
    api.ingest(
        *[live_entry(f"a{i}", bar(i), instance="A") for i in (1, 2, 3)],
        *[live_entry(f"b{i}", bar(i), instance="B") for i in (4, 5, 6, 7, 8)],
    )
    _, body = api.get("/v1/strategy-instances")
    rows = {r["strategy_instance_id"]: r for r in body["strategy_instances"]}
    assert list(rows) == ["A", "B"]
    assert rows["A"]["event_count"] == 3
    assert (rows["A"]["first_bar_open_time_ms"], rows["A"]["last_bar_open_time_ms"]) == (
        bar(1), bar(3),
    )  # fmt: skip
    assert rows["B"]["event_count"] == 5
    assert rows["B"]["last_occurred_at"]


def test_query_does_not_write_and_ingestion_continues(api: Api) -> None:
    api.ingest(live_entry("a", bar(1)))
    before = api.stats.snapshot().cursor_offset
    api.get("/v1/events?strategy_instance_id=ema_pullback:abc")
    api.get("/v1/strategy-instances")
    api.ingest(live_entry("b", bar(2)))
    assert api.stats.snapshot().cursor_offset > before
    _, body = api.get("/v1/events?strategy_instance_id=ema_pullback:abc")
    assert len(body["events"]) == 2
    # the request connection is read-only
    from journal_service.query import _connect

    db = _connect(api.db_path)
    with pytest.raises(sqlite3.OperationalError):
        db.execute("DELETE FROM events")
    db.close()


def test_health_unchanged_and_ingest_filter_unchanged(api: Api) -> None:
    api.ingest(live_entry("old", bar(1), schema_version=1), live_entry("ok", bar(2)))
    status, body = api.get("/health")
    assert status == 200 and body["stored_count"] == 1 and body["skipped_count"] == 1
    assert set(body) == {"status", "sources", "stored_count", "skipped_count", "malformed_count"}


def test_events_of_one_trade_cycle(api: Api) -> None:
    api.ingest(
        live_entry("e1", bar(1)),
        applied("a1", bar(1), cycle="cycle-1"),
        applied("a2", bar(5), cycle="cycle-2"),
        closed("c1", bar(4), cycle="cycle-1"),
        closed("c2", bar(8), cycle="cycle-2"),
        applied("x1", bar(1), cycle="cycle-1", instance="other"),
    )
    status, body = api.get(
        "/v1/events?strategy_instance_id=ema_pullback:abc&trade_cycle_id=cycle-1"
    )
    assert status == 200
    assert [e["event_id"] for e in body["events"]] == ["a1", "c1"]
    assert {e["trade_cycle_id"] for e in body["events"]} == {"cycle-1"}
    assert body["events"][1]["body"] == closed("c1", bar(4), cycle="cycle-1")

    _, body = api.get(
        "/v1/events?strategy_instance_id=ema_pullback:abc"
        "&trade_cycle_id=cycle-1&event_type=trade_cycle_closed"
    )
    assert [e["event_id"] for e in body["events"]] == ["c1"]


def test_closure_without_bar_is_returned_only_without_bar_bounds(api: Api) -> None:
    api.ingest(
        live_entry("e1", bar(1)),
        applied("a1", bar(1), cycle="cycle-1"),
        closed("c1", None, cycle="cycle-1"),
    )
    _, body = api.get("/v1/events?strategy_instance_id=ema_pullback:abc")
    assert [e["event_id"] for e in body["events"]] == ["c1", "e1", "a1"]
    assert body["events"][0]["bar_open_time_ms"] is None

    _, body = api.get("/v1/events?strategy_instance_id=ema_pullback:abc&trade_cycle_id=cycle-1")
    assert [e["event_id"] for e in body["events"]] == ["c1", "a1"]

    for bounds in (f"&from_bar_ms={bar(0)}", f"&to_bar_ms={bar(9)}"):
        _, body = api.get(f"/v1/events?strategy_instance_id=ema_pullback:abc{bounds}")
        assert "c1" not in [e["event_id"] for e in body["events"]]


def test_whole_cycle_with_opening_by_trade_cycle_id(api: Api) -> None:
    api.ingest(
        live_entry("e1", bar(1)),
        applied("a1", bar(1), cycle="cycle-1"),
        opened("o1", bar(2), cycle="cycle-1"),
        closed("c1", bar(4), cycle="cycle-1"),
        opened("o2", None, cycle="cycle-2", entry_order_id=None),
    )
    _, body = api.get("/v1/events?strategy_instance_id=ema_pullback:abc&trade_cycle_id=cycle-1")
    assert [e["event_id"] for e in body["events"]] == ["a1", "o1", "c1"]
    assert body["events"][1]["body"] == opened("o1", bar(2), cycle="cycle-1")

    _, body = api.get("/v1/events?strategy_instance_id=ema_pullback:abc")
    assert [e["event_id"] for e in body["events"]][0] == "o2"
    assert body["events"][0]["bar_open_time_ms"] is None
    assert body["events"][0]["trade_cycle_id"] == "cycle-2"


def test_whole_cycle_with_open_trade_events_by_trade_cycle_id(api: Api) -> None:
    api.ingest(
        live_entry("e1", bar(1)),
        applied("a1", bar(1), cycle="cycle-1"),
        opened("o1", bar(2), cycle="cycle-1"),
        # Same bar as the opening, written after it (Runtime freezes the first fill
        # before it asks Engine for the open-trade projection).
        open_trade("t2", bar(2), cycle="cycle-1", occurred_at="2026-10-16T12:40:01.512233+00:00"),
        open_trade("t3", bar(3), cycle="cycle-1"),
        protection("p3", bar(3), cycle="cycle-1"),
        open_trade("x3", bar(3), cycle="cycle-2"),
        closed("c1", bar(4), cycle="cycle-1"),
    )
    _, body = api.get("/v1/events?strategy_instance_id=ema_pullback:abc&trade_cycle_id=cycle-1")
    assert [e["event_id"] for e in body["events"]] == ["a1", "o1", "t2", "t3", "p3", "c1"]
    assert body["events"][4]["body"] == protection("p3", bar(3), cycle="cycle-1")


def test_declined_entry_is_returned_with_its_evaluation_and_alone_by_cycle(api: Api) -> None:
    evaluation = live_entry("e1", bar(1), desired_entry=ENTRY)
    refusal = declined("d1", bar(1), cycle="cycle-9")
    api.ingest(
        evaluation, refusal, live_entry("e2", bar(2)), applied("a1", bar(2), cycle="cycle-3")
    )
    _, body = api.get(
        f"/v1/events?strategy_instance_id=ema_pullback:abc&from_bar_ms={bar(1)}&to_bar_ms={bar(1)}"
    )
    assert [e["event_type"] for e in body["events"]] == [
        "live_entry_evaluated",
        "entry_package_declined",
    ]
    assert body["events"][1]["body"] == refusal
    assert body["events"][1]["trade_cycle_id"] == "cycle-9"

    _, body = api.get("/v1/events?strategy_instance_id=ema_pullback:abc&trade_cycle_id=cycle-9")
    assert [e["event_id"] for e in body["events"]] == ["d1"]


def test_ended_entry_cycle_is_returned_by_cycle_and_by_bar(api: Api) -> None:
    api.ingest(
        applied("a1", bar(1), cycle="cycle-1"),
        ended("x1", bar(2), cycle="cycle-1"),
        applied("a2", bar(2), cycle="cycle-2"),
        ended("x2", None, cycle="cycle-2", reason="disabled"),
    )
    _, body = api.get("/v1/events?strategy_instance_id=ema_pullback:abc&trade_cycle_id=cycle-1")
    assert [e["event_id"] for e in body["events"]] == ["a1", "x1"]
    assert body["events"][1]["body"] == ended("x1", bar(2), cycle="cycle-1")

    _, body = api.get("/v1/events?strategy_instance_id=ema_pullback:abc&trade_cycle_id=cycle-2")
    assert [e["event_id"] for e in body["events"]] == ["x2", "a2"]
    assert body["events"][0]["bar_open_time_ms"] is None
    assert body["events"][0]["trade_cycle_id"] == "cycle-2"

    _, body = api.get(
        f"/v1/events?strategy_instance_id=ema_pullback:abc&from_bar_ms={bar(2)}&to_bar_ms={bar(2)}"
    )
    assert [e["event_id"] for e in body["events"]] == ["a2", "x1"]
