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


def applied(
    event_id: str,
    bar: int = 1000,
    *,
    cycle: Any = "cycle-1",
    instance: str = "ema_pullback:abc",
    **payload_changes: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "trade_cycle_id": cycle,
        "bar_open_time_ms": bar,
        "trigger_price": "100.5",
        "stop_loss": "99",
        "take_profit": "103.25",
        "quantity": "0.012",
        "order_link_id": "abi-link-1",
        "order_id": "bybit-order-1",
    }
    payload.update(payload_changes)
    return {
        "schema_version": 2,
        "event_id": event_id,
        "event_type": "entry_package_applied",
        "occurred_at": f"2026-10-16T12:{bar % 60:02d}:30Z",
        "source": "strategy_runtime.committed_bar_orchestrator",
        "severity": "info",
        "strategy_instance_id": instance,
        "payload": payload,
        "diagnostics": {},
    }


def closed(
    event_id: str,
    bar: int | None = 1000,
    *,
    cycle: Any = "cycle-1",
    instance: str = "ema_pullback:abc",
    occurred_at: str = "2026-10-16T12:45:02.417305+00:00",
    **payload_changes: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "trade_cycle_id": cycle,
        "bar_open_time_ms": bar,
        "reason": "stop_loss",
        "order_id": "bybit-sl-1",
        "order_link_id": None,
        "parent_order_link_id": "abi-link-1",
    }
    payload.update(payload_changes)
    return {
        "schema_version": 2,
        "event_id": event_id,
        "event_type": "trade_cycle_closed",
        "occurred_at": occurred_at,
        "source": "strategy_runtime.committed_bar_orchestrator",
        "severity": "info",
        "strategy_instance_id": instance,
        "payload": payload,
        "diagnostics": {},
    }


def opened(
    event_id: str,
    bar: int | None = 1000,
    *,
    cycle: Any = "cycle-1",
    instance: str = "ema_pullback:abc",
    occurred_at: str = "2026-10-16T12:40:01.112233+00:00",
    **payload_changes: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "trade_cycle_id": cycle,
        "bar_open_time_ms": bar,
        "first_fill_at_ms": 1760618400123,
        "average_entry_price": "67000.5",
        "entry_order_link_id": "abi-link-1",
        "entry_order_id": "bybit-entry-1",
    }
    payload.update(payload_changes)
    return {
        "schema_version": 2,
        "event_id": event_id,
        "event_type": "trade_cycle_opened",
        "occurred_at": occurred_at,
        "source": "strategy_runtime.committed_bar_orchestrator",
        "severity": "info",
        "strategy_instance_id": instance,
        "payload": payload,
        "diagnostics": {},
    }


def open_trade(
    event_id: str,
    bar: int = 1000,
    *,
    cycle: Any = "cycle-1",
    instance: str = "ema_pullback:abc",
    occurred_at: str | None = None,
    **payload_changes: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "instrument": "BTCUSDT.P",
        "timeframe": "5m",
        "bar_open_time_ms": bar,
        "trade_cycle_id": cycle,
        "side": "long",
        "desired_protection": {"stop_price": "99.50", "take_price": None},
        "close_signal": {"active": False, "reason": None, "component_id": None, "layer": None},
    }
    payload.update(payload_changes)
    return {
        "schema_version": 2,
        "event_id": event_id,
        "event_type": "open_trade_evaluated",
        "occurred_at": occurred_at or f"2026-10-16T12:{bar % 60:02d}:10Z",
        "source": "strategy_runtime.committed_bar_orchestrator",
        "severity": "info",
        "strategy_instance_id": instance,
        "payload": payload,
        "diagnostics": {},
    }


def protection(
    event_id: str,
    bar: int = 1000,
    *,
    cycle: Any = "cycle-1",
    instance: str = "ema_pullback:abc",
    occurred_at: str | None = None,
    **payload_changes: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "trade_cycle_id": cycle,
        "bar_open_time_ms": bar,
        "requested_protection": {"stop_price": "99.5", "take_price": None},
        "confirmed_protection": {"stop_price": "99.5", "take_price": None},
        "position_quantity": "0.012",
        "stop_order": {"order_id": "bybit-sl-1", "trigger_price": "99.5"},
        "take_order": {"order_id": "bybit-tp-1", "trigger_price": "150.8"},
    }
    payload.update(payload_changes)
    return {
        "schema_version": 2,
        "event_id": event_id,
        "event_type": "protection_applied",
        "occurred_at": occurred_at or f"2026-10-16T12:{bar % 60:02d}:20Z",
        "source": "strategy_runtime.committed_bar_orchestrator",
        "severity": "info",
        "strategy_instance_id": instance,
        "payload": payload,
        "diagnostics": {},
    }


def declined(
    event_id: str,
    bar: Any = 1000,
    *,
    cycle: Any = "cycle-1",
    instance: str = "ema_pullback:abc",
    occurred_at: str = "2026-10-16T12:45:02.417305+00:00",
    **payload_changes: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "trade_cycle_id": cycle,
        "bar_open_time_ms": bar,
        "risk_multiplier": "1",
        "decline_reason": "insufficient_balance_for_minimum_quantity",
        "decline_message": "quantity 0.0004 below minOrderQty 0.001",
    }
    payload.update(payload_changes)
    return {
        "schema_version": 2,
        "event_id": event_id,
        "event_type": "entry_package_declined",
        "occurred_at": occurred_at,
        "source": "strategy_runtime.committed_bar_orchestrator",
        "severity": "warning",
        "strategy_instance_id": instance,
        "payload": payload,
        "diagnostics": {},
    }


def dump(record: dict[str, Any]) -> str:
    return json.dumps(record, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def append(path: Path, *records: dict[str, Any] | str) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(record if isinstance(record, str) else dump(record))
            handle.write("\n")
