## Context

Runtime appends `live_entry_evaluated` lines to `journal/runtime.jsonl` (complete
lines, fsync, best effort; the existing file holds ~84 MB of older event types).
Runtime accepts duplicate bars by design, so one bar can be evaluated more than
once. Foundation decisions F1–F7 (`journal-service-foundation-v1`) apply.

## Decisions

### E1. Accepted line

Runtime envelope: `schema_version`, `event_id`, `event_type`, `occurred_at`,
`source`, `severity`, `strategy_instance_id`, `payload`, `diagnostics`. For
`live_entry_evaluated` the payload is `instrument`, `timeframe`, `bar_open_time_ms`,
`desired_entry` (`null` or `side`, `source_plan_bar_open_time_ms`,
`planned_entry_price`, `initial_stop_price`, `initial_take_price`,
`locked_exit_profile`; prices as exact decimal text). The Central Journal checks only
what it indexes; it does not validate trading meaning.

Minimal indexable contract. An event is accepted only if these are present with the
expected structural type: `event_id` (non-empty string), `event_type` (string),
`schema_version` (integer), `occurred_at` (non-empty string), `strategy_instance_id`
(non-empty string) and `payload.bar_open_time_ms` (integer). Anything else is a
malformed line: logged, counted, skipped. `desired_entry` is not validated and not
interpreted; it stays inside `body`.

Two different `source` values exist. The envelope field `source` inside a Runtime
line (e.g. `strategy_runtime.committed_bar_orchestrator`) is Runtime's own and is
kept only inside `body`. The `source` column and cursor key (`'runtime'`) name the
Central Journal's ingest source, i.e. which journal file the line came from; it never
comes from the envelope.

### E2. Tailer

- Persisted cursor per source: file identity (device + inode) and byte offset after
  the last complete line.
- Reads only complete lines (ending in `\n`); a partial last line waits.
- Other event types and `schema_version` 1 are skipped and counted; the cursor still
  advances. The old part of the file is scanned once.
- File identity change or size below the cursor: warning, restart at offset 0 of the
  current file; idempotency makes it safe.
- A malformed complete line is logged and skipped, never fatal.
- Poll interval 1 s.

### E3. Storage

```sql
CREATE TABLE events (
  source               TEXT    NOT NULL,   -- ingest source name, 'runtime'
  event_id             TEXT    NOT NULL,
  event_type           TEXT    NOT NULL,
  schema_version       INTEGER NOT NULL,
  occurred_at          TEXT    NOT NULL,
  strategy_instance_id TEXT,
  trade_cycle_id       TEXT,               -- null for live_entry_evaluated
  bar_open_time_ms     INTEGER,            -- payload.bar_open_time_ms when present
  body                 TEXT    NOT NULL,   -- the line exactly as read
  ingested_at_ms       INTEGER NOT NULL,
  PRIMARY KEY (source, event_id)
);
CREATE INDEX events_instance_time  ON events (strategy_instance_id, occurred_at);
CREATE INDEX events_instance_bar   ON events (strategy_instance_id, bar_open_time_ms);
CREATE INDEX events_instance_cycle ON events (strategy_instance_id, trade_cycle_id);
CREATE INDEX events_type_time      ON events (event_type, occurred_at);

CREATE TABLE ingest_cursor (
  source TEXT PRIMARY KEY, file_dev INTEGER, file_ino INTEGER, offset INTEGER
);
```

`INSERT OR IGNORE`; the rows and the cursor update of one batch are one
transaction. A repeated evaluation of the same bar is a separate row (own
`event_id`).

### E4. Service surface

`GET /health`: status, per-source cursor offset, last ingested `occurred_at`,
skipped and malformed line counts. Verification is a SQLite query.

## Risks / Trade-offs

- The source is best effort: an event Runtime failed to write never arrives.
- No rotation of the source file yet; E2 tolerates replacement and truncation.
- Verification enables a real strategy instance: ABI must be in dry-run or demo
  mode, and the 32 enabled `loadtest-*` specs handled first (owner's call).
