"""Read-only queries over the closed_trades table for the HTTP read API."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from journal_service.query import InvalidQuery, _connect, _int_param
from journal_service.trades import COMPLETE, INCOMPLETE

# Rows with no close time (still incomplete) first, by creation; then by close time.
_ORDER = (
    "ORDER BY closed_at_ms IS NOT NULL, closed_at_ms, "
    "CASE WHEN closed_at_ms IS NULL THEN created_at_ms END, close_event_id"
)


def _rows(db: sqlite3.Connection, sql: str, args: list[Any]) -> list[dict[str, Any]]:
    db.row_factory = sqlite3.Row
    return [dict(row) for row in db.execute(sql, args).fetchall()]


def list_closed_trades(path: Path, params: dict[str, str]) -> dict[str, Any]:
    from_closed = _int_param(params, "from_closed_ms")
    to_closed = _int_param(params, "to_closed_ms")
    limit = _int_param(params, "limit")
    if limit is not None and limit < 1:
        raise InvalidQuery("limit must be at least 1")
    if from_closed is not None and to_closed is not None and from_closed > to_closed:
        raise InvalidQuery("from_closed_ms must not be greater than to_closed_ms")
    status = params.get("status")
    if status is not None and status not in (COMPLETE, INCOMPLETE):
        raise InvalidQuery("status must be complete or incomplete")
    instance = params.get("strategy_instance_id")
    if instance is not None and not instance.strip():
        raise InvalidQuery("strategy_instance_id must not be empty")

    sql = ["SELECT * FROM closed_trades WHERE 1 = 1"]
    args: list[Any] = []
    if instance is not None:
        sql.append("AND strategy_instance_id = ?")
        args.append(instance.strip())
    if status is not None:
        sql.append("AND status = ?")
        args.append(status)
    if from_closed is not None:
        sql.append("AND closed_at_ms >= ?")
        args.append(from_closed)
    if to_closed is not None:
        sql.append("AND closed_at_ms <= ?")
        args.append(to_closed)
    sql.append(_ORDER)
    if limit is not None:
        sql.append("LIMIT ?")
        args.append(limit + 1)

    with closing(_connect(path)) as db:
        rows = _rows(db, " ".join(sql), args)
    return {"trades": rows[:limit], "truncated": limit is not None and len(rows) > limit}


def closed_trade(
    path: Path, strategy_instance_id: str, trade_cycle_id: str
) -> dict[str, Any] | None:
    with closing(_connect(path)) as db:
        rows = _rows(
            db,
            "SELECT * FROM closed_trades WHERE strategy_instance_id = ? AND trade_cycle_id = ?",
            [strategy_instance_id, trade_cycle_id],
        )
    return rows[0] if rows else None
