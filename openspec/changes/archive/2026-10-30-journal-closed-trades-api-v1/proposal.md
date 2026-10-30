## Why

The closed-trades builder (`journal-closed-trades-builder-v1`) fills the `closed_trades` table,
but nothing can read it over HTTP yet. The front and any later report need the trade rows
exactly as stored.

## What Changes

- New read endpoints in the `closed-trades` capability:
  - `GET /v1/closed-trades`: list of trade rows, optional filters by strategy instance, close
    period and status, optional `limit`;
  - `GET /v1/closed-trades/{strategy_instance_id}/{trade_cycle_id}`: one trade row or 404.
- Rows are returned as stored: every column of `closed_trades`, decimals as strings, nothing
  computed at read time.
- `event-ingest` "Health endpoint" is modified so the closed-trades paths are allowed besides
  `/health` and the `event-query` paths.

## Non-Goals

No new columns, no aggregates (totals, win rate, equity curve), no paging cursor, no write
endpoints, no strategy display name (no source journals it). No change to the builder. The front
page is a separate change in research_frontend. No deploy without the owner's word.

## Impact

`src/journal_service/health.py`, a new read module for trade rows, tests, README,
`openspec/specs/closed-trades` and `openspec/specs/event-ingest` (on archive). Archive order:
`journal-closed-trades-table-v1`, then `journal-closed-trades-builder-v1`, then this change.
