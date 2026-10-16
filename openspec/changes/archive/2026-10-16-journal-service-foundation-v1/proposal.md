## Why

Observability features (Runtime Dashboard, Trade Inspector) need one place that
holds the history of what happened in live trading. Reconstructing that history
from internal state and correlation snapshots of each service would make the
journal understand every service's semantics. Instead, each service states its own
facts as self-contained events in its own processing journal, and one small service
indexes them.

This change fixes that empty architecture before the first event lands.

## What Changes

- New repository `journal_service` with an OpenSpec foundation and no code.
- The service's purpose, boundaries and stack are fixed as the `service-boundaries`
  capability. Each new event type arrives through its own small change (first:
  `runtime-live-entry-first-event-v1`).

## Out of Scope

Any concrete event type, schema migration code, query API, frontend, deployment, and
any change to other services.

## Capabilities

### New Capabilities

- `service-boundaries`: what the Central Journal is, what it reads, what it owns,
  and what it must never do.

## Impact

- New repository only. bbb_stack and other services are unchanged.
