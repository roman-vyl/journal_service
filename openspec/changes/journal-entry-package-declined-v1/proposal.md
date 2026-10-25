## Why

Since Runtime ad0d418 (strategy_runtime #36), deployed on demo on 2026-10-25, a declined ABI APPLY ends the entry attempt without a trade cycle. Runtime then writes `entry_package_declined` (severity `warning`) to `runtime.jsonl`. ABI d860511 answers `entry_package_declined` whenever the risk-sized quantity does not fit the Bybit limits, the stop is on the wrong side, or the margin mode is not allowed. Risk mode is on for demo (bbb_stack #71). The Journal parser does not accept this type and skips these lines, so a refused entry does not appear in the Journal history of the strategy.

## What Changes

- The parser also accepts `entry_package_declined` (`schema_version >= 2`) into the existing `events` table. `trade_cycle_id` comes from `payload.trade_cycle_id` and `bar_open_time_ms` from `payload.bar_open_time_ms`, which must be an integer.
- `risk_multiplier`, `decline_reason` and `decline_message` stay only in `body`. The Journal does not validate or interpret them.
- Nothing else changes: no new table, column, index or migration, and no query change. The existing `event_type` and `trade_cycle_id` filters already select these rows. Runtime, ABI and the frontend are not touched.

## Capabilities

### Modified Capabilities

- `event-ingest`: one more accepted event type.

## Impact

`parser.py` (accepted type, cycle type), parser tests, an end-to-end test with the real Runtime line, and the README status line. `storage.py` and `query.py` need no change.
