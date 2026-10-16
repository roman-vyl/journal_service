## Context

Runtime writes `live_entry_evaluated` events to `journal/runtime.jsonl` (append-only,
complete lines, fsync, best effort; existing file ~84 MB of older events). Runtime
accepts duplicate bars by design, so one bar can be evaluated more than once.
Foundation decisions F1–F5 (`journal-service-foundation-v1`) apply.

## Decisions

### I1. Accepted event shape (defined by Runtime)

Envelope unchanged (`schema_version`, `event_id`, `event_type`, `occurred_at`,
`source`, `severity`, `strategy_instance_id`, `payload`, `diagnostics`), with
`event_type = "live_entry_evaluated"` and:

```json
"payload": {
  "instrument": "BTCUSDT",
  "timeframe": "5m",
  "bar_open_time_ms": 1786564200000,
  "desired_entry": null
}
```

or `desired_entry` with exactly the decoded fields: `side`,
`source_plan_bar_open_time_ms`, `planned_entry_price`, `initial_stop_price`,
`initial_take_price`, `locked_exit_profile`. Prices stay exact decimal text.
The journal envelope `schema_version` goes from 1 to 2 so consumers can tell the
new event set apart; nothing in Runtime reads it.

### I2. Journal Service reads the file, never Runtime

- Tails `journal/runtime.jsonl` through a read-only mount, with a persisted cursor
  (`file identity` = device + inode, `byte offset` of the last complete line).
- Reads only complete lines (ending in `\n`); a partial last line is retried later.
- Lines with other event types or `schema_version` 1 are skipped; the cursor still
  advances. The existing ~84 MB file is scanned once.
- If the file identity changes or its size drops below the cursor, the service logs
  a warning and restarts from offset 0 of the new file; idempotency by `event_id`
  makes this safe.
- A malformed complete line is logged and skipped, never fatal.
- Poll interval: 1 s.

### I3. SQLite schema

One database file `BBB_DATA_ROOT/journal/journal.sqlite3`, WAL mode, one writer.

```sql
CREATE TABLE live_entry_observations (
  event_id                     TEXT PRIMARY KEY,
  strategy_instance_id         TEXT NOT NULL,
  instrument                   TEXT NOT NULL,
  timeframe                    TEXT NOT NULL,
  bar_open_time_ms             INTEGER NOT NULL,
  occurred_at                  TEXT NOT NULL,
  has_desired_entry            INTEGER NOT NULL,      -- 0 for null
  side                         TEXT,
  source_plan_bar_open_time_ms INTEGER,
  planned_entry_price          TEXT,
  initial_stop_price           TEXT,
  initial_take_price           TEXT,
  locked_exit_profile          TEXT,
  ingested_at_ms               INTEGER NOT NULL
);
CREATE INDEX live_entry_obs_instance_bar
  ON live_entry_observations (strategy_instance_id, bar_open_time_ms);

CREATE TABLE ingest_cursor (
  source TEXT PRIMARY KEY, file_dev INTEGER, file_ino INTEGER, offset INTEGER
);
```

Insert is `INSERT OR IGNORE` by `event_id`; the cursor update and the inserts of one
batch are one transaction. A repeated evaluation of the same bar is a separate row
(different `event_id`); choosing an "effective" one is out of scope.

### I4. Service surface

`GET /health` only (ok, last ingested `occurred_at`, cursor offset, skipped-line
count). No read API in this change; verification is a SQLite query.

## Risks / Trade-offs

- The source is best effort: an event Runtime failed to write is never seen here.
- No rotation of the source file yet; I2 tolerates replacement and truncation.
- Verification enables a real strategy instance: ABI must be in dry-run or demo
  mode, and the 32 enabled `loadtest-*` specs handled first (owner's call).

