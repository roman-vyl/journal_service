"""Structural parsing of one producer journal line.

The Central Journal indexes a few generic fields and keeps the line unchanged.
It does not validate or interpret producer semantics (e.g. ``desired_entry``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, TypeGuard

LIVE_ENTRY_EVALUATED: Final = "live_entry_evaluated"
ENTRY_PACKAGE_APPLIED: Final = "entry_package_applied"
TRADE_CYCLE_OPENED: Final = "trade_cycle_opened"
TRADE_CYCLE_CLOSED: Final = "trade_cycle_closed"
INGESTED_EVENT_TYPES: Final = frozenset(
    {LIVE_ENTRY_EVALUATED, ENTRY_PACKAGE_APPLIED, TRADE_CYCLE_OPENED, TRADE_CYCLE_CLOSED}
)
# Types whose payload names the trade cycle it belongs to.
CYCLE_EVENT_TYPES: Final = frozenset(
    {ENTRY_PACKAGE_APPLIED, TRADE_CYCLE_OPENED, TRADE_CYCLE_CLOSED}
)
# Types that may carry a null bar (resolved outside bar processing: a recovered
# first fill or a closure found by the pending-close resolver).
NULLABLE_BAR_EVENT_TYPES: Final = frozenset({TRADE_CYCLE_OPENED, TRADE_CYCLE_CLOSED})
MIN_SCHEMA_VERSION: Final = 2


class LineOutcome(StrEnum):
    ACCEPTED = "accepted"
    SKIPPED = "skipped"
    MALFORMED = "malformed"


@dataclass(frozen=True, slots=True)
class EventRow:
    event_id: str
    event_type: str
    schema_version: int
    occurred_at: str
    strategy_instance_id: str
    trade_cycle_id: str | None
    bar_open_time_ms: int | None
    body: str


@dataclass(frozen=True, slots=True)
class ParsedLine:
    outcome: LineOutcome
    row: EventRow | None = None
    reason: str = ""


def _is_int(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool)


def _non_empty_str(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _malformed(reason: str) -> ParsedLine:
    return ParsedLine(LineOutcome.MALFORMED, reason=reason)


def _skipped(reason: str) -> ParsedLine:
    return ParsedLine(LineOutcome.SKIPPED, reason=reason)


def parse_line(raw: bytes) -> ParsedLine:
    """Classify one complete line (without its trailing newline)."""

    try:
        body = raw.decode("utf-8")
        record = json.loads(body)
    except (UnicodeDecodeError, ValueError):
        return _malformed("not valid UTF-8 JSON")
    if not isinstance(record, dict):
        return _malformed("not a JSON object")

    event_type = record.get("event_type")
    if not isinstance(event_type, str) or event_type not in INGESTED_EVENT_TYPES:
        return _skipped("event type not ingested")
    schema_version = record.get("schema_version")
    if not _is_int(schema_version):
        return _malformed("schema_version is not an integer")
    if schema_version < MIN_SCHEMA_VERSION:
        return _skipped("schema_version below minimum")

    for name in ("event_id", "occurred_at", "strategy_instance_id"):
        if not _non_empty_str(record.get(name)):
            return _malformed(f"{name} is not a non-empty string")
    payload = record.get("payload")
    if not isinstance(payload, dict):
        return _malformed("payload is not an object")
    if "bar_open_time_ms" not in payload:
        return _malformed("payload.bar_open_time_ms is missing")
    bar_open_time_ms = payload["bar_open_time_ms"]
    bar_may_be_null = event_type in NULLABLE_BAR_EVENT_TYPES
    if not _is_int(bar_open_time_ms) and not (bar_may_be_null and bar_open_time_ms is None):
        return _malformed("payload.bar_open_time_ms is not an integer")
    trade_cycle_id: str | None = None
    if event_type in CYCLE_EVENT_TYPES:
        cycle = payload.get("trade_cycle_id")
        if not isinstance(cycle, str) or not cycle.strip():
            return _malformed("payload.trade_cycle_id is not a non-empty string")
        trade_cycle_id = cycle

    return ParsedLine(
        LineOutcome.ACCEPTED,
        row=EventRow(
            event_id=record["event_id"],
            event_type=event_type,
            schema_version=schema_version,
            occurred_at=record["occurred_at"],
            strategy_instance_id=record["strategy_instance_id"],
            trade_cycle_id=trade_cycle_id,
            bar_open_time_ms=bar_open_time_ms,
            body=body,
        ),
    )
