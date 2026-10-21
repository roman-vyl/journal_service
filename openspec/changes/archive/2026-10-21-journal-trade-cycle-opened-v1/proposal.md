## Why

Runtime writes `trade_cycle_opened` to `runtime.jsonl` once per trade cycle, after it has durably saved the first confirmed fill of the entry (strategy_runtime main 22e010f, PR #25). It is the fact "the position is open" and closes the first observation gap between `entry_package_applied` and `trade_cycle_closed`. The Journal parser does not accept this type, so the line is skipped today.

## What Changes

- The parser also accepts `trade_cycle_opened` (`schema_version >= 2`) into the existing `events` table, with `trade_cycle_id` from `payload.trade_cycle_id` and `bar_open_time_ms` from `payload.bar_open_time_ms`, which for this type may be null (recovery path).
- The rest of the payload is stored only as the unchanged line in `body`.
- Nothing else: no new table, column, index or migration; no trade-cycle table, status, position, projection or state machine; no interpretation of any payload field or of a missing event. `GET /v1/events` needs no change: the existing `trade_cycle_id` filter and field already cover the new type. No change in Runtime or ABI.

## Capabilities

### Modified Capabilities

- `event-ingest`: one more accepted event type, with a nullable bar.

## Impact

`parser.py` (the type joins the accepted, cycle and nullable-bar sets) and its tests. `storage.py` and `query.py` unchanged.
