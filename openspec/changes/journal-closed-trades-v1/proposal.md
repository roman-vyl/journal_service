## Why

The Journal keeps every Runtime event, but it cannot answer the owner's main question about a finished trade: at what real prices did we enter and exit, how much did we pay in fees, how much did we earn, in money and in R. Runtime knows the plan and the reason of the close; the real executions live only in ABI's exchange journal, which since 2026-10-29 links every Bybit order to its strategy instance and trade cycle and serves them through a read-only API (`GET /v1/strategy-instances/{sid}/trade-cycles/{cid}/exchange-journal`).

Owner decisions (2026-10-29, thread "Спроектировать центральный журнал сделок"):
- One service, two entities: the **event collector** (what exists today: stores Runtime events as received, never computes) and the **closed-trades journal** (assembles one row per closed trade and computes its metrics).
- ABI exchange facts are NOT copied into the Journal database. When a trade closes, the Journal reads that cycle from ABI's API, assembles the trade and stores only the assembled row in its own table.
- A trade is one Runtime trade cycle (strategy instance + trade cycle) in which the position was opened, fully or partly.
- The trigger is Runtime's `trade_cycle_closed`. No volume reconciliation in this stage.
- A row is first stored `incomplete`; the Journal asks ABI again until the exit execution is there, then marks it `complete` and never changes it again.

## What Changes

- `service-boundaries`: the Journal MAY read ABI's exchange-journal read API (GET only). "Indexed, not interpreted" and "append-only" stay in force for the `events` table; the new `closed_trades` table is the only derived table, and its row may change exactly once, from `incomplete` to `complete`.
- New capability `closed-trades`: table `closed_trades`, build trigger, completion rule, the metric formulas, retry, read API `GET /v1/closed-trades` and `GET /v1/closed-trades/{strategy_instance_id}/{trade_cycle_id}`.
- `event-ingest`: `/health` additionally reports the closed-trades builder; the allowed paths include the closed-trades read API.
- Database schema version 1 → 2 (adds `closed_trades`, nothing else changes; existing rows untouched).
- Config: `JOURNAL_ABI_BASE_URL` (optional; without it rows stay `incomplete` and health says so), `JOURNAL_TRADES_RETRY_S` (default 60).

## Not in this change

MFE/MAE (needs candles), funding, return in % of the deposit, volume reconciliation and a "mismatch" flag, strategy display name (no source journals it yet; the front already maps the id to a name), the chart of the trade, bbb_stack wiring of the Journal container to ABI's network (separate bbb_stack change), Runtime and ABI changes (none needed).

## Capabilities

### New Capabilities

- `closed-trades`: one assembled row per closed trade and its read API.

### Modified Capabilities

- `service-boundaries`: ABI read API allowed; derived table allowed under the rules above.
- `event-ingest`: health and allowed paths.

## Impact

New modules for the ABI client, the trade builder and the closed-trades queries; `storage.py` migration to schema 2; `config.py`, `main.py` (builder thread), `health.py`; tests with real ABI and Runtime fixtures. Runtime, ABI and the frontend are not changed.
