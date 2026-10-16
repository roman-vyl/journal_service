## Context

Audits of 2026-10-16 (thread "Trade Observatory"): Runtime keeps an append-only
fsync'd state JSONL (a line only on change) and a best-effort processing journal
JSONL; ABI keeps a correlation JSONL; MDS keeps candles in SQLite and corrects them in
place. None of them keeps a per-bar history of strategy decisions.

The owner's direction: a central journal beside the trading path, fed by the
services, never consulted by trading; SQLite in WAL mode with a single owner; no
SQLite file shared between services.

## Decisions

### F1. Observer, not participant

The service only reads. Trading services do not call it, wait for it or read from
it. If it is down, trading continues and the service catches up from the source
files when it comes back.

### F2. Sources are files, read through read-only mounts

Each source is a file another service already writes (first: Runtime
`journal/runtime.jsonl`). The service never writes to a source, never calls the
producing service, and holds a persisted cursor per source. A push channel (outbox
plus HTTP) may replace a file source later; that is a separate decision.

### F3. One database, one owner

`BBB_DATA_ROOT/journal/journal.sqlite3`, WAL mode. Only this service opens it for
writing. Other services never open it; they will read through this service's API
when one exists.

### F4. Append-only, idempotent ingest

Every stored row carries the source event's id; ingest is idempotent by that id and
the cursor moves in the same transaction as the rows. Rows are never updated or
deleted by ingest. Derived views (an "effective" attempt, trade cycles) are computed
later on top of raw rows, never by rewriting them.

### F5. Stack

Python 3.12, standard library `sqlite3`, one process, one small HTTP surface, Docker
image, deployed by bbb_stack like the other services. Each ingest is added by its own
OpenSpec change.

## Risks / Trade-offs

- File sources inherit their producer's durability: a best-effort source can lose an
  event before the service sees it.
- Reading files couples the service to the producer's line format; each ingest change
  names the exact event shape it accepts.
