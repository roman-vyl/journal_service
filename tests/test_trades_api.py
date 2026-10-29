"""Read API over closed_trades: list with filters and order, one row, 400/404, read-only."""

from __future__ import annotations

import json
import sqlite3
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from threading import Thread
from typing import Any

import pytest

from journal_service.health import build_server
from journal_service.stats import IngestStats
from journal_service.storage import Store
from tests.test_trades import CID, REAL_SHORT, SID, Rig, short_plan


class Api:
    def __init__(self, tmp_path: Path) -> None:
        self.rig = Rig(tmp_path)
        self.db_path = self.rig.db_path
        self.server = build_server("127.0.0.1", 0, "runtime", IngestStats(), self.db_path)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def get(self, path: str) -> tuple[int, Any]:
        try:
            with urllib.request.urlopen(self.base + path, timeout=3) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())

    def put(
        self,
        sid: str,
        cid: str,
        *,
        status: str = "complete",
        closed_at_ms: int | None = None,
        created_at_ms: int = 1,
        close_event_id: str = "e",
    ) -> None:
        db = sqlite3.connect(self.db_path)
        try:
            db.execute(
                "INSERT INTO closed_trades (strategy_instance_id, trade_cycle_id, close_reason,"
                " close_event_id, closing_order_id, status, closed_at_ms, created_at_ms, attempts)"
                " VALUES (?, ?, 'stop_loss', ?, 'o', ?, ?, ?, 1)",
                (sid, cid, close_event_id, status, closed_at_ms, created_at_ms),
            )
            db.commit()
        finally:
            db.close()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.rig.store.close()


@pytest.fixture
def api(tmp_path: Path) -> Iterator[Api]:
    value = Api(tmp_path)
    try:
        yield value
    finally:
        value.close()


def keys(body: Any) -> list[tuple[str, str]]:
    return [(t["strategy_instance_id"], t["trade_cycle_id"]) for t in body["trades"]]


def test_empty_table(api: Api) -> None:
    assert api.get("/v1/closed-trades") == (200, {"trades": [], "truncated": False})


def test_all_rows_incomplete_first_then_by_close_time(api: Api) -> None:
    api.put("a", "c3", closed_at_ms=300, close_event_id="e3")
    api.put("a", "c1", closed_at_ms=100, close_event_id="e1")
    api.put("b", "c2", closed_at_ms=100, close_event_id="e0")
    api.put("b", "c9", status="incomplete", created_at_ms=50)
    api.put("a", "c8", status="incomplete", created_at_ms=20)
    status, body = api.get("/v1/closed-trades")
    assert status == 200
    assert keys(body) == [("a", "c8"), ("b", "c9"), ("b", "c2"), ("a", "c1"), ("a", "c3")]
    assert body["truncated"] is False


def test_filters(api: Api) -> None:
    api.put("a", "c1", closed_at_ms=100)
    api.put("a", "c2", closed_at_ms=200)
    api.put("a", "c3", closed_at_ms=300)
    api.put("b", "c4", closed_at_ms=200)
    api.put("a", "c5", status="incomplete")
    assert keys(api.get("/v1/closed-trades?strategy_instance_id=b")[1]) == [("b", "c4")]
    period = api.get("/v1/closed-trades?from_closed_ms=200&to_closed_ms=300")[1]
    assert keys(period) == [("a", "c2"), ("b", "c4"), ("a", "c3")]
    waiting = api.get("/v1/closed-trades?status=incomplete")[1]
    assert keys(waiting) == [("a", "c5")]
    assert waiting["trades"][0]["attempts"] == 1
    assert "last_error" in waiting["trades"][0]
    both = api.get("/v1/closed-trades?strategy_instance_id=a&status=complete&to_closed_ms=200")[1]
    assert keys(both) == [("a", "c1"), ("a", "c2")]


def test_limit_truncates(api: Api) -> None:
    for i in range(5):
        api.put("a", f"c{i}", closed_at_ms=100 + i)
    body = api.get("/v1/closed-trades?limit=2")[1]
    assert keys(body) == [("a", "c0"), ("a", "c1")]
    assert body["truncated"] is True
    assert api.get("/v1/closed-trades?limit=5")[1]["truncated"] is False


def test_real_short_returned_as_stored(api: Api) -> None:
    api.rig.ingest(*short_plan())
    api.rig.answers = [REAL_SHORT]
    api.rig.builder.run_pass()
    stored = api.rig.row()
    status, body = api.get(f"/v1/closed-trades/{SID}/{CID}")
    assert status == 200
    assert body == {"trade": stored}
    assert body["trade"]["net_pnl_usdt"] == "-1307.99088539"
    assert body["trade"]["gross_pnl_usdt"] == "-969.3902"
    assert body["trade"]["status"] == "complete"
    assert body["trade"]["r_multiple"] == stored["r_multiple"]
    assert api.get("/v1/closed-trades")[1]["trades"] == [stored]


def test_one_trade_with_encoded_path(api: Api) -> None:
    api.put("ema:x/y", "c 1", closed_at_ms=1)
    status, body = api.get("/v1/closed-trades/ema%3Ax%2Fy/c%201")
    assert status == 200
    assert body["trade"]["strategy_instance_id"] == "ema:x/y"


def test_unknown_trade_is_404(api: Api) -> None:
    assert api.get("/v1/closed-trades/a/nope") == (404, {"error": "closed trade not found"})


@pytest.mark.parametrize(
    "path",
    [
        "/v1/closed-trades/",
        "/v1/closed-trades/a",
        "/v1/closed-trades/a/b/c",
        "/v1/closed-trades/a/",
    ],
)
def test_bad_trade_paths_are_404(api: Api, path: str) -> None:
    assert api.get(path)[0] == 404


@pytest.mark.parametrize(
    "query",
    [
        "limit=0",
        "limit=x",
        "limit=",
        "from_closed_ms=x",
        "to_closed_ms=1.5",
        "from_closed_ms=5&to_closed_ms=4",
        "status=open",
        "status=",
        "strategy_instance_id=",
        "strategy_instance_id=%20",
    ],
)
def test_invalid_requests_are_400(api: Api, query: str) -> None:
    status, body = api.get(f"/v1/closed-trades?{query}")
    assert status == 400
    assert body["error"]


def test_reads_do_not_write(api: Api) -> None:
    api.put("a", "c1", status="incomplete")
    before = api.db_path.stat().st_mtime_ns, api.rig.row("a", "c1")
    api.get("/v1/closed-trades")
    api.get("/v1/closed-trades/a/c1")
    assert (api.db_path.stat().st_mtime_ns, api.rig.row("a", "c1")) == before


def test_store_still_writable_after_reads(api: Api) -> None:
    api.get("/v1/closed-trades")
    api.rig.ingest(*short_plan())
    api.rig.answers = [REAL_SHORT]
    api.rig.builder.run_pass()
    assert api.rig.row()["status"] == "complete"
    Store(api.db_path).close()
