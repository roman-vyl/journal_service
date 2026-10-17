"""Read-only queries over the events table for the HTTP read API."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

DEFAULT_LIMIT = 1000
MAX_LIMIT = 5000


class InvalidQuery(ValueError):
    """A request parameter is missing or invalid (answered as HTTP 400)."""


def _connect(path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
    db.execute("PRAGMA query_only = ON")
    return db


def _int_param(params: dict[str, str], name: str) -> int | None:
    raw = params.get(name)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        raise InvalidQuery(f"{name} must be an integer") from None


def events_for_instance(path: Path, params: dict[str, str]) -> dict[str, Any]:
    instance = params.get("strategy_instance_id", "").strip()
    if not instance:
        raise InvalidQuery("strategy_instance_id is required")
    from_bar = _int_param(params, "from_bar_ms")
    to_bar = _int_param(params, "to_bar_ms")
    limit = _int_param(params, "limit")
    if limit is None:
        limit = DEFAULT_LIMIT
    if limit < 1 or limit > MAX_LIMIT:
        raise InvalidQuery(f"limit must be between 1 and {MAX_LIMIT}")
    if from_bar is not None and to_bar is not None and from_bar > to_bar:
        raise InvalidQuery("from_bar_ms must not be greater than to_bar_ms")

    sql = [
        "SELECT event_id, event_type, schema_version, occurred_at, strategy_instance_id,",
        "bar_open_time_ms, body FROM events WHERE strategy_instance_id = ?",
    ]
    args: list[Any] = [instance]
    event_type = params.get("event_type")
    if event_type:
        sql.append("AND event_type = ?")
        args.append(event_type)
    if from_bar is not None:
        sql.append("AND bar_open_time_ms >= ?")
        args.append(from_bar)
    if to_bar is not None:
        sql.append("AND bar_open_time_ms <= ?")
        args.append(to_bar)
    sql.append("ORDER BY bar_open_time_ms, occurred_at, event_id LIMIT ?")
    args.append(limit + 1)

    with closing(_connect(path)) as db:
        rows = db.execute(" ".join(sql), args).fetchall()
    events = [
        {
            "event_id": r[0],
            "event_type": r[1],
            "schema_version": r[2],
            "occurred_at": r[3],
            "strategy_instance_id": r[4],
            "bar_open_time_ms": r[5],
            "body": json.loads(r[6]),
        }
        for r in rows[:limit]
    ]
    return {"events": events, "truncated": len(rows) > limit}


def list_strategy_instances(path: Path) -> dict[str, Any]:
    with closing(_connect(path)) as db:
        rows = db.execute(
            "SELECT strategy_instance_id, COUNT(*), MIN(bar_open_time_ms), "
            "MAX(bar_open_time_ms), MAX(occurred_at) FROM events "
            "WHERE strategy_instance_id IS NOT NULL "
            "GROUP BY strategy_instance_id ORDER BY strategy_instance_id"
        ).fetchall()
    return {
        "strategy_instances": [
            {
                "strategy_instance_id": r[0],
                "event_count": r[1],
                "first_bar_open_time_ms": r[2],
                "last_bar_open_time_ms": r[3],
                "last_occurred_at": r[4],
            }
            for r in rows
        ]
    }
