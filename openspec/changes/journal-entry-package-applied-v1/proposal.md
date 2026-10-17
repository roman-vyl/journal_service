## Why

Runtime now writes `entry_package_applied` to `runtime.jsonl` (strategy_runtime #22): the four values of the cycle's own entry order that ABI read back from Bybit during the apply. The Central Journal parser only accepts `live_entry_evaluated`, so these records never reach SQLite.

## What Changes

- The existing parser also accepts `entry_package_applied` (`schema_version >= 2`) and stores it in the existing `events` table, with `trade_cycle_id` taken from `payload.trade_cycle_id` and `bar_open_time_ms` null.
- Nothing else: no new table, no new column, no change to the tailer, cursor, query API or health endpoint. No change in ABI or Runtime.

## Capabilities

### Modified Capabilities

- `event-ingest`: one more accepted event type.

## Impact

`parser.py` (accepted type, `EventRow.bar_open_time_ms` optional, the extracted `trade_cycle_id`) and its tests. `storage.py` already has nullable `trade_cycle_id` and `bar_open_time_ms` columns and needs no change.
