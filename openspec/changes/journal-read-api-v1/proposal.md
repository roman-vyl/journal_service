## Why

The Runtime Dashboard has to draw what Strategy Engine wanted (`desired_entry`) for each
Runtime strategy, bar by bar, from the moment the strategy was enabled. The Central Journal
already stores every `live_entry_evaluated` event, but it only answers `GET /health`.
Service boundaries say other services and the frontend get journal data from this
service's API, never from the database file.

## What Changes

- `GET /v1/events`: stored events of one strategy instance in a bar range, oldest bar first,
  each event returned as the unchanged source line plus its index fields.
- `GET /v1/strategy-instances`: per strategy instance, the first and last evaluated bar, the
  number of stored events and the last `occurred_at`.
- Reads use their own read-only access to the SQLite database; the tailer stays the only writer.
- `GET /health` is unchanged.

## Out of Scope

New event types (dispatch outcomes, ABI, diagnostics), interpreting or validating
`desired_entry`, choosing an "effective" evaluation among repeated evaluations of a bar,
authentication, CORS, writes, any change to ingestion, Strategy Runtime or Strategy Engine,
the frontend (separate change in `research_frontend`).

## Capabilities

### New Capabilities

- `event-query`: read stored events by strategy instance and bar range, and list strategy
  instances with their evaluated bar range.

### Modified Capabilities

- `event-ingest`: the health requirement no longer says "no other HTTP endpoint".

## Impact

- This repository: query module, two routes, tests, README. CI builds the image.
- bbb_stack: a new image pin in a separate PR; the existing port 8097 is reused.
- research_frontend: reaches the service through a dev proxy (separate change).
