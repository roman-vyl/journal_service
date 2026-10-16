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
    bar_open_time_ms: int
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
    if event_type != LIVE_ENTRY_EVALUATED:
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
    bar_open_time_ms = payload.get("bar_open_time_ms")
    if not _is_int(bar_open_time_ms):
        return _malformed("payload.bar_open_time_ms is not an integer")

    return ParsedLine(
        LineOutcome.ACCEPTED,
        row=EventRow(
            event_id=record["event_id"],
            event_type=LIVE_ENTRY_EVALUATED,
            schema_version=schema_version,
            occurred_at=record["occurred_at"],
            strategy_instance_id=record["strategy_instance_id"],
            trade_cycle_id=None,
            bar_open_time_ms=bar_open_time_ms,
            body=body,
        ),
    )
