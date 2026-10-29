"""Closed-trades builder: detection, assembly with the spec formulas, retry and freezing."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Any

import pytest

from journal_service import abi_client
from journal_service.abi_client import AbiReadError, fetch_cycle
from journal_service.parser import parse_line
from journal_service.storage import Cursor, Store
from journal_service.trades import TradeBuilder, TradesStats, closed_trade_counts
from tests.support import applied, closed, dump, live_entry, protection

SID = "ema_pullback:abc"
CID = "cycle-1"


def exec_event(
    order_id: str,
    price: str,
    qty: str,
    fee: str,
    time_ms: int,
    side: str,
    exec_type: str = "Trade",
) -> dict[str, Any]:
    return {
        "fact_kind": "execution",
        "exec_type": exec_type,
        "order_id": order_id,
        "symbol": "BTCUSDT",
        "order_status": None,
        "raw": {
            "execPrice": price,
            "execQty": qty,
            "execFee": fee,
            "execTime": str(time_ms),
            "side": side,
            "symbol": "BTCUSDT",
            "execType": exec_type,
        },
    }


def state(order_id: str, status: str, side: str) -> dict[str, Any]:
    return {
        "fact_kind": "order_state",
        "exec_type": None,
        "order_id": order_id,
        "symbol": "BTCUSDT",
        "order_status": status,
        "raw": {"orderStatus": status, "side": side},
    }


def order(role: str, order_id: str, *events: dict[str, Any], truncated: bool = False) -> Any:
    return {
        "link": {"role": role, "order_id": order_id},
        "events": list(events),
        "truncated": truncated,
    }


def cycle(*orders: Any, truncated: bool = False) -> dict[str, Any]:
    return {
        "strategy_instance_id": SID,
        "trade_cycle_id": CID,
        "orders": list(orders),
        "truncated": truncated,
    }


# Real Demo trade of 2026-10-25 (BTC short closed by its stop).
REAL_SHORT = cycle(
    order(
        "entry",
        "bf880957",
        state("bf880957", "Filled", "Sell"),
        exec_event("bf880957", "80496.1", "3.818", "169.03376039", 1792939843422, "Sell"),
    ),
    order(
        "stop_loss",
        "97c748dd",
        state("97c748dd", "Filled", "Buy"),
        exec_event("97c748dd", "80750", "3.818", "169.566925", 1792940451013, "Buy"),
    ),
    order("take_profit", "0aa37e01", state("0aa37e01", "Deactivated", "Buy")),
)


class Rig:
    def __init__(self, tmp_path: Path) -> None:
        self.db_path = tmp_path / "journal.sqlite3"
        self.store = Store(self.db_path)
        self.answers: list[Any] = []
        self.calls: list[tuple[str, str, str]] = []
        self.now = 1_000
        self.stats = TradesStats(abi_configured=True)
        self.builder = self.make_builder("http://abi:8787")
        self._offset = 0

    def make_builder(self, base_url: str) -> TradeBuilder:
        return TradeBuilder(self.db_path, base_url, self.stats, self.fetch, lambda: self.now)

    def fetch(self, base_url: str, sid: str, cid: str) -> dict[str, Any]:
        self.calls.append((base_url, sid, cid))
        answer = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        if isinstance(answer, Exception):
            raise answer
        return answer  # type: ignore[no-any-return]

    def ingest(self, *records: dict[str, Any]) -> None:
        rows = []
        for record in records:
            parsed = parse_line(dump(record).encode())
            assert parsed.row is not None
            rows.append(parsed.row)
        self._offset += len(rows)
        self.store.commit_batch(
            source="runtime", rows=rows, cursor=Cursor(1, 1, self._offset), ingested_at_ms=1
        )

    def row(self, sid: str = SID, cid: str = CID) -> dict[str, Any]:
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        try:
            found = db.execute(
                "SELECT * FROM closed_trades WHERE strategy_instance_id = ? AND trade_cycle_id = ?",
                (sid, cid),
            ).fetchone()
        finally:
            db.close()
        assert found is not None
        return dict(found)

    def count(self) -> int:
        db = sqlite3.connect(self.db_path)
        try:
            return int(db.execute("SELECT COUNT(*) FROM closed_trades").fetchone()[0])
        finally:
            db.close()


@pytest.fixture
def rig(tmp_path: Path) -> Iterator[Rig]:
    value = Rig(tmp_path)
    yield value
    value.store.close()


def short_plan() -> list[dict[str, Any]]:
    return [
        applied("a1", trigger_price="80484", stop_loss="80744.7", take_profit="79571.3"),
        closed("c1", reason="stop_loss", order_id="97c748dd"),
    ]


def test_real_demo_short_is_completed_with_spec_numbers(rig: Rig) -> None:
    rig.ingest(*short_plan())
    rig.answers = [REAL_SHORT]
    rig.builder.run_pass()
    row = rig.row()
    assert row["status"] == "complete"
    assert row["symbol"] == "BTCUSDT"
    assert row["side"] == "short"
    assert row["close_reason"] == "stop_loss"
    assert row["closing_order_id"] == "97c748dd"
    assert row["entry_avg_price"] == "80496.1"
    assert row["exit_avg_price"] == "80750"
    assert row["entry_qty"] == row["exit_qty"] == "3.818"
    assert row["entry_fill_count"] == row["exit_fill_count"] == 1
    assert row["gross_pnl_usdt"] == "-969.3902"
    assert row["fees_usdt"] == "338.60068539"
    assert row["net_pnl_usdt"] == "-1307.99088539"
    assert row["opened_at_ms"] == 1792939843422
    assert row["closed_at_ms"] == 1792940451013
    assert row["duration_ms"] == 1792940451013 - 1792939843422
    assert row["planned_entry_price"] == "80484"
    assert row["last_stop"] == "80744.7"
    # Risk from actual entry to the initial stop: (80744.7 - 80496.1) * 3.818.
    assert row["risk_usdt"] == "949.1548"
    assert row["r_multiple"].startswith("-1.3780585")
    # Short entry 80496.1 above the 80484 plan is better: negative slippage.
    assert row["entry_slippage_pct"].startswith("-0.0150")
    # Stop at 80744.7 filled at 80750: worse, positive slippage.
    assert row["exit_slippage_pct"].startswith("0.00656")
    assert row["attempts"] == 1
    assert row["last_error"] is None
    assert row["completed_at_ms"] == 1_000
    assert rig.calls == [("http://abi:8787", SID, CID)]


def test_long_with_several_entry_fills_and_two_exit_orders(rig: Rig) -> None:
    rig.ingest(
        applied("a1", trigger_price="100", stop_loss="95", take_profit="110"),
        protection("p1", cycle=CID, confirmed_protection={"stop_price": "98", "take_price": "109"}),
        closed("c1", reason="runtime_signal", order_id="close-1"),
    )
    rig.answers = [
        cycle(
            order(
                "entry",
                "e1",
                exec_event("e1", "100", "1", "0.1", 10, "Buy"),
                exec_event("e1", "104", "3", "0.3", 20, "Buy"),
            ),
            order("stop_loss", "sl", exec_event("sl", "106", "1", "0.1", 30, "Sell")),
            order(
                "close",
                "close-1",
                state("close-1", "Filled", "Sell"),
                exec_event("close-1", "110", "3", "0.3", 40, "Sell"),
            ),
        )
    ]
    rig.builder.run_pass()
    row = rig.row()
    assert row["status"] == "complete"
    assert row["side"] == "long"
    assert (row["entry_avg_price"], row["entry_qty"], row["entry_fill_count"]) == ("103", "4", 2)
    assert (row["exit_avg_price"], row["exit_qty"], row["exit_fill_count"]) == ("109", "4", 2)
    assert row["gross_pnl_usdt"] == "24"
    assert row["fees_usdt"] == "0.8"
    assert row["net_pnl_usdt"] == "23.2"
    assert row["entry_notional_usdt"] == "412"
    assert (row["last_stop"], row["last_take"]) == ("98", "109")
    assert row["risk_usdt"] == "32"
    assert row["r_multiple"] == "0.725"
    assert row["entry_slippage_pct"] == "3"
    assert row["exit_slippage_pct"] is None
    assert (row["opened_at_ms"], row["closed_at_ms"], row["duration_ms"]) == (10, 40, 30)


def test_missing_plan_leaves_plan_fields_null(rig: Rig) -> None:
    rig.ingest(closed("c1", reason="stop_loss", order_id="97c748dd"))
    rig.answers = [REAL_SHORT]
    rig.builder.run_pass()
    row = rig.row()
    assert row["status"] == "complete"
    for name in (
        "planned_entry_price",
        "planned_initial_stop",
        "planned_initial_take",
        "last_stop",
        "last_take",
        "risk_usdt",
        "r_multiple",
        "entry_slippage_pct",
        "exit_slippage_pct",
    ):
        assert row[name] is None, name
    assert row["net_pnl_usdt"] == "-1307.99088539"


def test_funding_execution_is_ignored(rig: Rig) -> None:
    rig.ingest(*short_plan())
    with_funding = json.loads(json.dumps(REAL_SHORT))
    with_funding["orders"][0]["events"].append(
        exec_event("bf880957", "80604.6", "2.07", "-7.94046393", 1792944000000, "Sell", "Funding")
    )
    rig.answers = [with_funding]
    rig.builder.run_pass()
    assert rig.row()["net_pnl_usdt"] == "-1307.99088539"


def test_exit_arriving_later_completes_on_a_later_pass(rig: Rig) -> None:
    rig.ingest(*short_plan())
    entry_only = cycle(REAL_SHORT["orders"][0])
    rig.answers = [entry_only, REAL_SHORT]
    rig.builder.run_pass()
    first = rig.row()
    assert (first["status"], first["last_error"], first["attempts"]) == (
        "incomplete",
        "closing_order_not_filled",
        1,
    )
    assert first["net_pnl_usdt"] is None
    rig.now = 2_000
    rig.builder.run_pass()
    second = rig.row()
    assert (second["status"], second["attempts"], second["completed_at_ms"]) == (
        "complete",
        2,
        2_000,
    )


def test_no_entry_execution_stays_incomplete(rig: Rig) -> None:
    rig.ingest(*short_plan())
    rig.answers = [cycle(REAL_SHORT["orders"][1])]
    rig.builder.run_pass()
    assert rig.row()["last_error"] == "no_entry_execution"


@pytest.mark.parametrize(
    ("answer", "code"),
    [
        (AbiReadError("abi_unavailable"), "abi_unavailable"),
        (AbiReadError("abi_http_503"), "abi_http_503"),
        (cycle(*REAL_SHORT["orders"], truncated=True), "abi_truncated"),
        ({"orders": "nonsense"}, "abi_bad_response"),
    ],
)
def test_abi_failures_keep_the_row_incomplete(rig: Rig, answer: Any, code: str) -> None:
    rig.ingest(*short_plan())
    rig.answers = [answer]
    rig.builder.run_pass()
    row = rig.row()
    assert (row["status"], row["last_error"]) == ("incomplete", code)
    assert rig.stats.snapshot() == (1_000, code)


def test_abi_not_configured_creates_rows_without_calls(rig: Rig) -> None:
    rig.ingest(*short_plan())
    rig.make_builder("").run_pass()
    assert rig.row()["last_error"] == "abi_not_configured"
    assert rig.calls == []


def test_complete_row_is_never_touched_again(rig: Rig) -> None:
    rig.ingest(*short_plan())
    rig.answers = [REAL_SHORT]
    rig.builder.run_pass()
    before = rig.row()
    rig.now = 5_000
    rig.answers = [AbiReadError("abi_unavailable")]
    rig.builder.run_pass()
    rig.make_builder("http://abi:8787").run_pass()
    assert rig.row() == before
    assert len(rig.calls) == 1


def test_second_closure_of_the_same_cycle_is_ignored(rig: Rig) -> None:
    rig.ingest(*short_plan())
    rig.ingest(closed("c2", reason="take_profit", order_id="other"))
    rig.answers = [REAL_SHORT]
    rig.builder.run_pass()
    row = rig.row()
    assert (row["close_event_id"], row["close_reason"]) == ("c1", "stop_loss")
    assert rig.count() == 1


def test_old_closures_are_backfilled_and_unclosed_cycles_ignored(rig: Rig) -> None:
    rig.ingest(
        live_entry("l1"),
        applied("a2", cycle="never-filled"),
        closed("c1", cycle="old-1", order_id="x1"),
        closed("c2", cycle="old-2", order_id="x2", instance="other:1"),
    )
    rig.answers = [AbiReadError("abi_unavailable")]
    rig.builder.run_pass()
    assert rig.count() == 2
    assert rig.row(SID, "old-1")["status"] == "incomplete"
    assert rig.row("other:1", "old-2")["status"] == "incomplete"
    assert closed_trade_counts(rig.db_path) == {"complete": 0, "incomplete": 2}


def test_ingestion_continues_while_abi_is_down(rig: Rig) -> None:
    rig.ingest(*short_plan())
    rig.answers = [AbiReadError("abi_unavailable")]
    rig.builder.run_pass()
    rig.ingest(live_entry("l2", 1300))
    db = sqlite3.connect(rig.db_path)
    try:
        assert db.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 3
    finally:
        db.close()


class _Abi(BaseHTTPRequestHandler):
    status = 200
    body = b"{}"
    paths: list[str] = []

    def do_GET(self) -> None:
        type(self).paths.append(self.path)
        self.send_response(type(self).status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(type(self).body)))
        self.end_headers()
        self.wfile.write(type(self).body)

    def log_message(self, format: str, *args: Any) -> None:
        return


@pytest.fixture
def abi_url() -> Iterator[str]:
    _Abi.paths = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Abi)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_client_reads_the_per_cycle_route_with_encoded_ids(abi_url: str) -> None:
    _Abi.status, _Abi.body = 200, json.dumps({"orders": []}).encode()
    assert fetch_cycle(abi_url + "/", "ema:a/b", "c 1") == {"orders": []}
    assert _Abi.paths == ["/v1/strategy-instances/ema%3Aa%2Fb/trade-cycles/c%201/exchange-journal"]


@pytest.mark.parametrize(
    ("status", "body", "code"),
    [
        (503, b'{"error": {}}', "abi_http_503"),
        (200, b"not json", "abi_bad_response"),
        (200, b"[]", "abi_bad_response"),
    ],
)
def test_client_errors(abi_url: str, status: int, body: bytes, code: str) -> None:
    _Abi.status, _Abi.body = status, body
    with pytest.raises(AbiReadError) as error:
        fetch_cycle(abi_url, SID, CID)
    assert error.value.code == code


def test_client_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(abi_client, "TIMEOUT_S", 0.5)
    with pytest.raises(AbiReadError) as error:
        fetch_cycle("http://127.0.0.1:9", SID, CID)
    assert error.value.code == "abi_unavailable"
