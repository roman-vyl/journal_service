import json
from typing import Any

import pytest

from journal_service.parser import LineOutcome, parse_line
from tests.support import ENTRY, applied, closed, dump, live_entry


def parse(record: dict[str, Any]) -> LineOutcome:
    return parse_line(dump(record).encode()).outcome


def test_null_and_non_null_desired_entry_are_accepted_with_body_unchanged() -> None:
    for desired in (None, ENTRY):
        line = dump(live_entry("e1", 1000, desired_entry=desired))
        parsed = parse_line(line.encode())
        assert parsed.outcome is LineOutcome.ACCEPTED
        assert parsed.row is not None
        assert parsed.row.body == line
        assert parsed.row.event_id == "e1"
        assert parsed.row.bar_open_time_ms == 1000
        assert parsed.row.trade_cycle_id is None


def test_meaningless_desired_entry_is_stored_unchanged() -> None:
    line = dump(live_entry("e1", desired_entry={"anything": [1, 2, "x"]}))
    parsed = parse_line(line.encode())
    assert parsed.outcome is LineOutcome.ACCEPTED
    assert parsed.row is not None
    assert parsed.row.body == line


@pytest.mark.parametrize(
    "record",
    [
        live_entry("e1", event_type="committed_bar_orchestration_started"),
        live_entry("e1", schema_version=1),
        {"event_type": "strategy_cycle_dispatch_succeeded", "schema_version": 1},
        {"no_event_type": True},
    ],
)
def test_unrelated_or_old_events_are_skipped(record: dict[str, Any]) -> None:
    assert parse(record) is LineOutcome.SKIPPED


def _without(key: str) -> dict[str, Any]:
    record = live_entry("e1")
    del record[key]
    return record


def _payload(**changes: Any) -> dict[str, Any]:
    record = live_entry("e1")
    record["payload"].update(changes)
    return record


def _payload_without(key: str) -> dict[str, Any]:
    record = live_entry("e1")
    del record["payload"][key]
    return record


@pytest.mark.parametrize(
    "record",
    [
        _without("event_id"),
        _without("occurred_at"),
        _without("strategy_instance_id"),
        _without("schema_version"),
        _without("payload"),
        live_entry("", 1000),
        live_entry("e1", occurred_at=""),
        live_entry("e1", strategy_instance_id="  "),
        live_entry("e1", strategy_instance_id=5),
        live_entry("e1", schema_version="2"),
        live_entry("e1", schema_version=True),
        live_entry("e1", payload={}),
        live_entry("e1", payload=[1]),
        _payload_without("bar_open_time_ms"),
        _payload(bar_open_time_ms="1000"),
        _payload(bar_open_time_ms=True),
        _payload(bar_open_time_ms=1000.5),
        _payload(bar_open_time_ms=None),
    ],
)
def test_structurally_invalid_live_entry_is_malformed(record: dict[str, Any]) -> None:
    assert parse(record) is LineOutcome.MALFORMED


@pytest.mark.parametrize("raw", [b"not json", b"[1,2]", b'"text"', b"123", b"\xff\xfe{}", b""])
def test_non_json_object_lines_are_malformed(raw: bytes) -> None:
    assert parse_line(raw).outcome is LineOutcome.MALFORMED


def test_envelope_source_is_not_part_of_the_row() -> None:
    line = dump(live_entry("e1"))
    parsed = parse_line(line.encode())
    assert parsed.row is not None
    assert "source" not in {f for f in parsed.row.__slots__}
    assert json.loads(parsed.row.body)["source"] == "strategy_runtime.committed_bar_orchestrator"


def test_entry_package_applied_is_stored_with_cycle_and_bar_and_body_unchanged() -> None:
    line = dump(applied("a1", 1300, cycle="cycle-7"))
    parsed = parse_line(line.encode())
    assert parsed.outcome is LineOutcome.ACCEPTED
    assert parsed.row is not None
    assert parsed.row.event_type == "entry_package_applied"
    assert parsed.row.strategy_instance_id == "ema_pullback:abc"
    assert parsed.row.trade_cycle_id == "cycle-7"
    assert parsed.row.bar_open_time_ms == 1300
    assert parsed.row.body == line
    payload = json.loads(parsed.row.body)["payload"]
    assert payload["order_link_id"] == "abi-link-1"
    assert payload["order_id"] == "bybit-order-1"


@pytest.mark.parametrize(
    "changes",
    [
        {"trigger_price": None, "stop_loss": None, "take_profit": None, "quantity": None},
        {"order_link_id": None, "order_id": None},
        {"trigger_price": "not a number", "order_id": 42},
    ],
)
def test_entry_package_applied_values_and_ids_are_not_validated(changes: dict[str, Any]) -> None:
    line = dump(applied("a1", **changes))
    parsed = parse_line(line.encode())
    assert parsed.outcome is LineOutcome.ACCEPTED
    assert parsed.row is not None
    assert parsed.row.body == line


def _applied_without(key: str) -> dict[str, Any]:
    record = applied("a1")
    del record["payload"][key]
    return record


@pytest.mark.parametrize(
    "record",
    [
        _applied_without("trade_cycle_id"),
        applied("a1", cycle=None),
        applied("a1", cycle=""),
        applied("a1", cycle=7),
        _applied_without("bar_open_time_ms"),
        applied("a1", bar_open_time_ms=None),
        applied("a1", bar_open_time_ms="1000"),
        {**applied("a1"), "event_id": ""},
        {**applied("a1"), "occurred_at": None},
        {**applied("a1"), "strategy_instance_id": "  "},
        {**applied("a1"), "payload": []},
    ],
)
def test_structurally_invalid_entry_package_applied_is_malformed(record: dict[str, Any]) -> None:
    assert parse(record) is LineOutcome.MALFORMED


def test_entry_package_applied_with_old_schema_is_skipped() -> None:
    assert parse({**applied("a1"), "schema_version": 1}) is LineOutcome.SKIPPED


@pytest.mark.parametrize("bar", [1300, None])
def test_trade_cycle_closed_is_stored_with_cycle_and_bar_and_body_unchanged(
    bar: int | None,
) -> None:
    line = dump(closed("c1", bar, cycle="cycle-7"))
    parsed = parse_line(line.encode())
    assert parsed.outcome is LineOutcome.ACCEPTED
    assert parsed.row is not None
    assert parsed.row.event_type == "trade_cycle_closed"
    assert parsed.row.strategy_instance_id == "ema_pullback:abc"
    assert parsed.row.trade_cycle_id == "cycle-7"
    assert parsed.row.bar_open_time_ms == bar
    assert parsed.row.body == line


@pytest.mark.parametrize(
    "changes",
    [
        {"reason": "take_profit"},
        {"reason": "runtime_signal", "order_link_id": "abi-close-1", "parent_order_link_id": None},
        {"reason": "anything", "order_id": 42},
    ],
)
def test_trade_cycle_closed_reason_and_ids_are_not_validated(changes: dict[str, Any]) -> None:
    line = dump(closed("c1", **changes))
    parsed = parse_line(line.encode())
    assert parsed.outcome is LineOutcome.ACCEPTED
    assert parsed.row is not None
    assert parsed.row.body == line


def _closed_without(key: str) -> dict[str, Any]:
    record = closed("c1")
    del record["payload"][key]
    return record


@pytest.mark.parametrize(
    "record",
    [
        _closed_without("trade_cycle_id"),
        closed("c1", cycle=None),
        closed("c1", cycle=""),
        closed("c1", cycle=7),
        _closed_without("bar_open_time_ms"),
        closed("c1", "1000"),
        closed("c1", True),
        closed("c1", 1000.5),
        {**closed("c1"), "event_id": ""},
        {**closed("c1"), "occurred_at": None},
        {**closed("c1"), "strategy_instance_id": "  "},
        {**closed("c1"), "payload": []},
    ],
)
def test_structurally_invalid_trade_cycle_closed_is_malformed(record: dict[str, Any]) -> None:
    assert parse(record) is LineOutcome.MALFORMED


def test_trade_cycle_closed_with_old_schema_is_skipped() -> None:
    assert parse({**closed("c1"), "schema_version": 1}) is LineOutcome.SKIPPED


def test_null_bar_stays_malformed_for_the_other_types() -> None:
    record = live_entry("e1")
    record["payload"]["bar_open_time_ms"] = None
    assert parse(record) is LineOutcome.MALFORMED
    assert parse(applied("a1", bar_open_time_ms=None)) is LineOutcome.MALFORMED
