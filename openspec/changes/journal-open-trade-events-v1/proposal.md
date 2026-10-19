## Why

Runtime now writes two more events to `runtime.jsonl` while a position is open (strategy_runtime `runtime-open-trade-journal-v1`, PR #27, with ABI `abi-protection-orders-identity-v1`, PR #25):

- `open_trade_evaluated`: Engine's open-trade answer on every bar of an open position (desired stop/take, close signal, side);
- `protection_applied`: every protection change ABI confirmed, with the requested and confirmed levels, the trade cycle's quantity and the ids and trigger prices of the stop and take orders on the exchange.

They are the open-position counterparts of `live_entry_evaluated` and `entry_package_applied`. The Journal parser does not accept them, so the lines are skipped today.

## What Changes

- The parser also accepts `open_trade_evaluated` and `protection_applied` (`schema_version >= 2`) into the existing `events` table, exactly like `live_entry_evaluated` and `entry_package_applied`, with `trade_cycle_id` from `payload.trade_cycle_id` and `bar_open_time_ms` from `payload.bar_open_time_ms` (always an integer for both).
- The rest of the payload, including `position_quantity` and the protective orders, is stored only as the unchanged line in `body`.
- Nothing else: no new table, column, index or migration; no position, protection state or projection; no interpretation of any payload field or of a missing event. `GET /v1/events` needs no change: the existing `trade_cycle_id` filter already returns both types with the rest of the cycle. No change in Runtime or ABI.

## Capabilities

### Modified Capabilities

- `event-ingest`: two more accepted event types, both cycle types with a required bar.

## Impact

`parser.py` (both types join the accepted and cycle sets, not the nullable-bar set) and its tests. `storage.py` and `query.py` unchanged. Deploy only after Runtime and ABI with the new events; until then there is nothing to ingest.
