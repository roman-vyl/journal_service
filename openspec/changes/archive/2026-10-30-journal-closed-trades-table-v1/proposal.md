## Why

The owner wants a closed-trades journal: one row per closed trade with real entry and exit prices, fees, profit and R. Before anything fills it, the owner approves the table itself and what each field means. This change defines only that table.

Decisions already taken by the owner (2026-10-29, thread "Спроектировать центральный журнал сделок"): one row = one Runtime trade cycle (strategy instance + trade cycle) in which the position was opened, fully or partly; the row is assembled from Runtime events (plan, close reason) and ABI's exchange journal (real executions), and ABI facts are not copied, only the assembled row is stored.

## What Changes

- New capability `closed-trades`: table `closed_trades`, its columns and the meaning, source and formula of every column.
- `service-boundaries`: the "indexed, not interpreted" rule stays for `events`; `closed_trades` is allowed as the only derived table.
- Database schema version 1 → 2: adds the empty table, nothing else changes; existing rows untouched.

## Not in this change (later changes, each on the owner's word)

Filling the table (reading ABI, when a row is built, `incomplete`/`complete`, retries), the read API, health, the bbb_stack wiring to ABI, MFE/MAE, funding, % of deposit, strategy display name.

## Capabilities

### New Capabilities

- `closed-trades`: the table and the meaning of its columns.

### Modified Capabilities

- `service-boundaries`: one derived table allowed.

## Impact

`storage.py` (migration to schema 2) and its tests. No new endpoint, no ABI call, no change in Runtime, ABI or the frontend.
