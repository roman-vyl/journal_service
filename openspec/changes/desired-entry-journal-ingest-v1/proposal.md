## Why

Strategy Runtime now journals every successful Engine `live-entry` result as a
`live_entry_evaluated` event (`strategy_runtime` change
`runtime-desired-entry-journal-v1`), including `desired_entry = null`. These lines
need to accumulate somewhere durable and queryable, outside the trading path.

## What Changes

- The Journal Service tails Runtime `journal/runtime.jsonl` read-only and stores
  every `live_entry_evaluated` event (schema_version >= 2) in table
  `live_entry_observations`.
- `GET /health` only.
- bbb_stack: one new service with a read-only mount of
  `BBB_DATA_ROOT/strategy-runtime/journal` and a read-write mount of
  `BBB_DATA_ROOT/journal`.

## Out of Scope

ABI, orders, trade cycles, open-trade / managed evaluations, diagnostics, frontend,
charts, read API beyond health, journal state machines, choosing an "effective"
attempt among repeated evaluations of one bar.

## Capabilities

### New Capabilities

- `desired-entry-ingest`: ingest `live_entry_evaluated` events into
  `live_entry_observations`.

## Impact

- This repository: first code (package, schema, tailer, health, tests, Dockerfile).
- bbb_stack: compose service; image pin in a separate PR.
- Depends on `runtime-desired-entry-journal-v1` being deployed.
