"""Schema version 2: the closed-trades table and the upgrade from version 1."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from journal_service import storage
from journal_service.parser import EventRow
from journal_service.storage import Cursor, Store

CLOSED_TRADE_COLUMNS = [
    "strategy_instance_id",
    "trade_cycle_id",
    "symbol",
    "side",
    "close_reason",
    "close_event_id",
    "closing_order_id",
    "status",
    "opened_at_ms",
    "entry_avg_price",
    "entry_qty",
    "entry_notional_usdt",
    "entry_fill_count",
    "entry_fee_usdt",
    "closed_at_ms",
    "exit_avg_price",
    "exit_qty",
    "exit_fill_count",
    "exit_fee_usdt",
    "duration_ms",
    "planned_entry_price",
    "planned_initial_stop",
    "planned_initial_take",
    "last_stop",
    "last_take",
    "gross_pnl_usdt",
    "fees_usdt",
    "net_pnl_usdt",
    "price_return_pct",
    "net_return_pct",
    "risk_usdt",
    "r_multiple",
    "entry_slippage_pct",
    "exit_slippage_pct",
    "created_at_ms",
    "completed_at_ms",
    "attempts",
    "last_attempt_at_ms",
    "last_error",
]


def _read(path: Path, sql: str) -> list[tuple[object, ...]]:
    db = sqlite3.connect(path)
    try:
        return db.execute(sql).fetchall()
    finally:
        db.close()


def _make_version_1(path: Path) -> None:
    db = sqlite3.connect(path, isolation_level=None)
    try:
        for statement in storage._SCHEMA_V1.split(";"):
            if statement.strip():
                db.execute(statement)
        db.execute(
            "INSERT INTO events VALUES ('runtime', 'e1', 'trade_cycle_closed', 2, "
            "'2026-10-29T12:00:00Z', 'sid', 'cycle-1', NULL, '{}', 5)"
        )
        db.execute("INSERT INTO ingest_cursor VALUES ('runtime', 1, 2, 300)")
        db.execute("PRAGMA user_version=1")
    finally:
        db.close()


def test_new_database_has_version_2_with_both_tables(tmp_path: Path) -> None:
    path = tmp_path / "journal.sqlite3"
    Store(path).close()
    assert _read(path, "PRAGMA user_version") == [(2,)]
    tables = {r[0] for r in _read(path, "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"events", "ingest_cursor", "closed_trades"} <= tables


def test_closed_trades_has_exactly_the_specified_columns_and_key(tmp_path: Path) -> None:
    path = tmp_path / "journal.sqlite3"
    Store(path).close()
    info = _read(path, "PRAGMA table_info(closed_trades)")
    assert [row[1] for row in info] == CLOSED_TRADE_COLUMNS
    key = sorted((row[5], row[1]) for row in info if row[5])
    assert key == [(1, "strategy_instance_id"), (2, "trade_cycle_id")]
    indexes = {row[1] for row in _read(path, "PRAGMA index_list(closed_trades)")}
    assert {"closed_trades_closed_at", "closed_trades_status"} <= indexes
    assert _read(path, "SELECT COUNT(*) FROM closed_trades") == [(0,)]


def test_version_1_upgrades_in_place_and_keeps_events_and_cursor(tmp_path: Path) -> None:
    path = tmp_path / "journal.sqlite3"
    _make_version_1(path)
    before = _read(path, "SELECT * FROM events")
    store = Store(path)
    try:
        assert store.get_cursor("runtime") == Cursor(1, 2, 300)
    finally:
        store.close()
    assert _read(path, "PRAGMA user_version") == [(2,)]
    assert _read(path, "SELECT * FROM events") == before
    assert _read(path, "SELECT COUNT(*) FROM closed_trades") == [(0,)]


def test_reopening_version_2_changes_nothing(tmp_path: Path) -> None:
    path = tmp_path / "journal.sqlite3"
    store = Store(path)
    store.commit_batch(
        source="runtime",
        rows=[
            EventRow("e1", "live_entry_evaluated", 2, "2026-10-29T12:00:00Z", "sid", None, 1, "{}")
        ],
        cursor=Cursor(1, 2, 3),
        ingested_at_ms=7,
    )
    store.close()
    schema = _read(path, "SELECT sql FROM sqlite_master ORDER BY name")
    Store(path).close()
    assert _read(path, "SELECT sql FROM sqlite_master ORDER BY name") == schema
    assert _read(path, "SELECT event_id FROM events") == [("e1",)]


def test_unknown_version_refuses_to_start(tmp_path: Path) -> None:
    path = tmp_path / "journal.sqlite3"
    db = sqlite3.connect(path)
    db.execute("PRAGMA user_version=3")
    db.close()
    with pytest.raises(RuntimeError, match="unsupported journal database version 3"):
        Store(path)
