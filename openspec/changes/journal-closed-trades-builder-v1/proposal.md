## Why

`journal-closed-trades-table-v1` created the empty `closed_trades` table and fixed the meaning and formulas of its columns. This change fills it: the Journal finds closed trades, reads their executions from ABI and writes one row per trade.

Owner decisions (2026-10-29, thread "Спроектировать центральный журнал сделок"):
- One service, two entities: the event collector (unchanged) and the closed-trades builder. They do not call each other; the builder only reads the collector's database.
- ABI facts are not copied. For each trade the builder reads one cycle from ABI's read API and stores only the assembled row.
- A trade is a Runtime cycle with an opened position; the trigger is Runtime `trade_cycle_closed`; no volume reconciliation in this stage.
- A row starts `incomplete`, is retried until the exit execution is there, then becomes `complete` and never changes.
- Detection is by the builder looking into the database once a minute, not by a signal from the collector (accepted delay up to a minute).

## What Changes

- `closed-trades`: detection, assembly, completion rule and retry of rows.
- `service-boundaries`: the Journal MAY send `GET` to ABI's per-cycle exchange-journal route and nothing else; ABI facts are read, never stored; a `closed_trades` row may change only while `incomplete`.
- `event-ingest`: `/health` reports the builder.
- Config: `JOURNAL_ABI_BASE_URL` (optional; empty = the builder creates rows but does not call ABI, health says so), `JOURNAL_TRADES_INTERVAL_S` (default 60).

## Not in this change

The read API for trades and the front (next change), MFE/MAE, funding, % of deposit, strategy name, volume reconciliation, the bbb_stack wiring that gives the Journal container the ABI address (separate bbb_stack change on the owner's word).

## Capabilities

### Modified Capabilities

- `closed-trades`: filling the table.
- `service-boundaries`: ABI read access, no copy, mutable incomplete rows.
- `event-ingest`: health.

## Impact

New modules `abi_client.py` and `trades.py`, a builder thread in `main.py`, `config.py`, `health.py`, `storage.py` (row writes); tests with real ABI and Runtime shapes. No schema change. Runtime, ABI and the frontend are not changed.
