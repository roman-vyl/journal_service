## Why

The first end-to-end event through the observability architecture. Strategy Runtime
now journals every successful Engine `live-entry` result as a self-contained
`live_entry_evaluated` event, including `desired_entry = null` (`strategy_runtime`
change `runtime-desired-entry-journal-v1`). Proving that one event travels from the
Runtime journal into Central Journal storage exactly once proves the pipe every
later event type will use.

## What Changes

- Source `runtime`: tail Runtime `journal/runtime.jsonl` read-only.
- Accept `event_type = live_entry_evaluated` with envelope `schema_version >= 2`;
  skip and count everything else.
- Generic table `events` (foundation F2), not a table dedicated to desired entries.
- `GET /health` only; no query API yet.
- bbb_stack: one new service with a read-only mount of
  `BBB_DATA_ROOT/strategy-runtime/journal` and a read-write mount of
  `BBB_DATA_ROOT/journal`.

## Out of Scope

ABI events, trade cycles, open-trade / managed evaluations, diagnostics, query API,
frontend, charts, choosing an "effective" attempt among repeated evaluations of one
bar.

## Capabilities

### New Capabilities

- `event-ingest`: read a producer journal and store accepted events in `events`
  exactly once.

## Impact

- This repository: first code (package, schema, tailer, health, tests, Dockerfile).
- bbb_stack: compose service; image pin in a separate PR.
- Needs `runtime-desired-entry-journal-v1` deployed to see real events.
