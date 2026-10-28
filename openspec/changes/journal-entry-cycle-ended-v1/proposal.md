## Why

Runtime change `runtime-entry-cycle-ended-event-v1` writes `entry_cycle_ended` to `runtime.jsonl` whenever an entry order's cycle ends without a fill (cancelled, disabled, resolver found it terminal without a fill, or exact absence after a corrective cancel). The Journal parser skips every type it does not list, so without this change the Journal history would still show the last `entry_package_applied` of that cycle as alive.

## What Changes

- The parser also accepts `entry_cycle_ended` (`schema_version >= 2`) into the existing `events` table. `trade_cycle_id` comes from `payload.trade_cycle_id`. `payload.bar_open_time_ms` is an integer, or `null` when Runtime ended the cycle outside bar processing (disable and both resolver reasons).
- `reason` stays only in `body`. The Journal does not validate or interpret it and derives no cycle status from it.
- Nothing else changes: no table, column, index or migration, no query change. The existing `event_type` and `trade_cycle_id` filters already select these rows. Runtime, ABI and the frontend are not touched by this change.

## Capabilities

### Modified Capabilities

- `event-ingest`: one more accepted event type, with a nullable bar.

## Impact

`parser.py` (accepted type, cycle type, nullable-bar type), parser tests, an end-to-end test with the real Runtime line, and the README status line. `storage.py` and `query.py` need no change. Rollout: deploy this change first, then the Runtime change.
