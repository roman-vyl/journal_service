## Why

Runtime writes `entry_package_applied` to `runtime.jsonl` (strategy_runtime #22, extended by #23): the bar of the evaluation that produced the apply, the four values of the cycle's own entry order that ABI read back from Bybit, and that order's `order_link_id` and `order_id`. The Central Journal parser only accepts `live_entry_evaluated`, so these records never reach SQLite.

## What Changes

- The existing parser also accepts `entry_package_applied` (`schema_version >= 2`) and stores it in the existing `events` table, with `trade_cycle_id` from `payload.trade_cycle_id` and `bar_open_time_ms` from `payload.bar_open_time_ms`.
- `order_link_id`, `order_id` and the four order values stay only in `body` (the unchanged source line).
- Nothing else: no new table, no new column, no change to the tailer, cursor, query API or health endpoint. No change in ABI or Runtime.

## Capabilities

### Modified Capabilities

- `event-ingest`: one more accepted event type.

## Impact

`parser.py` (accepted type, the extracted `trade_cycle_id`) and its tests. `storage.py` already has nullable `trade_cycle_id` and `bar_open_time_ms` columns and needs no change.
