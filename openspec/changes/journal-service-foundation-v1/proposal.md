## Why

The trading stack (Strategy Engine, Strategy Runtime, ABI, Market Data Service) keeps
its own state and logs, each in its own format, and much of what happens on a live
bar is not kept at all. Observability features (Runtime Dashboard, Trade Inspector)
need one place that accumulates history without touching the trading path.

This change fixes the empty architecture of that place before any feature lands.

## What Changes

- New repository `journal_service` with an OpenSpec foundation and no code.
- The service's purpose, boundaries and stack are fixed as the `service-boundaries`
  capability. Concrete ingests are separate changes (first:
  `desired-entry-journal-ingest-v1`).

## Out of Scope

Any ingest, schema, read API, frontend, deployment, and any change to other services.

## Capabilities

### New Capabilities

- `service-boundaries`: what the Journal Service is, what it reads, what it owns,
  and what it must never do.

## Impact

- New repository only. bbb_stack and other services are unchanged.
