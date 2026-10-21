## Why

Runtime writes `trade_cycle_closed` to `runtime.jsonl` after it has durably saved a proven closure of a trade cycle (strategy_runtime, branch `claude/runtime-trade-cycle-closure`, 73d7acf). The frontend needs this fact to draw an exit marker: `occurred_at` gives the position on the time axis and `payload.reason` the label. The Journal parser does not accept this type, rejects lines whose `payload.bar_open_time_ms` is null, and `GET /v1/events` cannot select the events of one trade cycle.

## What Changes

- The parser also accepts `trade_cycle_closed` (`schema_version >= 2`) into the existing `events` table, with `trade_cycle_id` from `payload.trade_cycle_id` and `bar_open_time_ms` from `payload.bar_open_time_ms`, which for this type may be null.
- `GET /v1/events` gets an optional `trade_cycle_id` filter and returns `trade_cycle_id` as a field of every event.
- Nothing else: no new table, column, index or migration; no trade-cycle table, status, position or reconstructed state; no interpretation of a missing event. No change in Runtime or ABI.

## Capabilities

### Modified Capabilities

- `event-ingest`: one more accepted event type, with a nullable bar.
- `event-query`: a `trade_cycle_id` filter and return field.

## Impact

`parser.py` (accepted type, nullable bar for it), `query.py` (filter, field) and their tests. `storage.py` already has nullable `trade_cycle_id` and `bar_open_time_ms` and the index `events_instance_cycle (strategy_instance_id, trade_cycle_id)`; it needs no change.
