# journal_service

BBB Journal Service: a read-only observer of the trading stack. It reads journal
files that other services already write (first: the Strategy Runtime processing
journal), and accumulates selected events in its own SQLite database for later
read models (Runtime Dashboard, Trade Inspector).

It sits beside the trading path, never on it: it does not call Strategy Engine,
Strategy Runtime, ABI or Market Data Service, and no trading service depends on it.

Status: architecture only. No code yet.

- `openspec/changes/journal-service-foundation-v1` — purpose, boundaries, stack.
- `openspec/changes/desired-entry-journal-ingest-v1` — first ingest: every
  Runtime `live_entry_evaluated` event (including `desired_entry = null`).
  Runtime side: `strategy_runtime` change `runtime-desired-entry-journal-v1`.
