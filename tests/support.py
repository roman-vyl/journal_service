"""Helpers that build Runtime-shaped journal lines."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ENTRY = {
    "side": "long",
    "source_plan_bar_open_time_ms": 900,
    "planned_entry_price": "100.5",
    "initial_stop_price": "99",
    "initial_take_price": "103.25",
    "locked_exit_profile": "runner",
}


def live_entry(
    event_id: str,
    bar: int = 1000,
    *,
    desired_entry: Any = None,
    instance: str = "ema_pullback:abc",
    **overrides: Any,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "schema_version": 2,
        "event_id": event_id,
        "event_type": "live_entry_evaluated",
        "occurred_at": f"2026-10-16T12:{bar % 60:02d}:00Z",
        "source": "strategy_runtime.committed_bar_orchestrator",
        "severity": "info",
        "strategy_instance_id": instance,
        "payload": {
            "instrument": "BTCUSDT.P",
            "timeframe": "5m",
            "bar_open_time_ms": bar,
            "desired_entry": desired_entry,
        },
        "diagnostics": {},
    }
    record.update(overrides)
    return record


def dump(record: dict[str, Any]) -> str:
    return json.dumps(record, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def append(path: Path, *records: dict[str, Any] | str) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(record if isinstance(record, str) else dump(record))
            handle.write("\n")
