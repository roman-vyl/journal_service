# journal_service

BBB Central Journal: an indexer of facts that trading services publish about
themselves. Each service writes self-contained events to its own append-only
processing journal (Strategy Runtime: what Engine answered, for which strategy and
bar; later ABI: what was sent, what Bybit confirmed, fills, cancels, protection).
The Central Journal reads those files, stores the events once in its own SQLite
and, later, answers queries such as "events of strategy X between A and B".

It never interprets events, never reconstructs them from internal state snapshots,
never makes trading decisions, and never calls Strategy Engine, Strategy Runtime,
ABI or Market Data Service. No trading service depends on it.

Status: architecture only. No code yet.

- `openspec/changes/journal-service-foundation-v1`: purpose, boundaries, stack.
- `openspec/changes/runtime-live-entry-first-event-v1`: the first end-to-end event,
  Runtime `live_entry_evaluated` (including `desired_entry = null`).
  Producer side: `strategy_runtime` change `runtime-desired-entry-journal-v1`.
