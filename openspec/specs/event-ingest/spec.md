# event-ingest Specification

## Purpose
Read-only ingest of the Runtime processing journal into the SQLite events table, with a persisted cursor, idempotent storage and a health endpoint.
## Requirements
### Requirement: Ingest Runtime live-entry events

The service MUST read the Runtime processing journal read-only and store every
`live_entry_evaluated` event with `schema_version >= 2` that passes the minimal
indexable contract as one row of `events` with the ingest source name
`source = 'runtime'`, the line kept unchanged as `body`, and `strategy_instance_id`,
`bar_open_time_ms` and `occurred_at` extracted for indexing. It MUST NOT validate or
interpret `desired_entry`.

#### Scenario: Non-null and null desired entry
- **WHEN** the journal contains `live_entry_evaluated` events with a desired entry and with `desired_entry = null`
- **THEN** each becomes one row, `trade_cycle_id` is null, and `body` equals the source line

#### Scenario: Unrelated or old events
- **WHEN** a line has another `event_type` or `schema_version` 1
- **THEN** it is skipped and counted, and ingestion continues

#### Scenario: Malformed complete line
- **WHEN** a complete line is not valid JSON, or a `live_entry_evaluated` line lacks any of `event_id`, `schema_version`, `occurred_at`, `strategy_instance_id` or `payload.bar_open_time_ms`, or one of them has the wrong structural type
- **THEN** it is logged, counted as malformed and skipped, and ingestion continues

#### Scenario: Structurally valid event with a meaningless desired entry
- **WHEN** a `live_entry_evaluated` line passes the structural check but `desired_entry` has unexpected content
- **THEN** it is stored with `body` unchanged, because the Central Journal does not validate or interpret `desired_entry`

#### Scenario: Envelope source differs from ingest source
- **WHEN** a Runtime line carries an envelope `source` such as `strategy_runtime.committed_bar_orchestrator`
- **THEN** the stored `source` column is the ingest source name `runtime`, and the envelope value stays only inside `body`

### Requirement: Exactly-once storage across restarts

The service MUST persist a cursor (file identity and byte offset after the last
complete line) in the same transaction as the rows it stored, and MUST insert rows
idempotently by (`source`, `event_id`).

#### Scenario: Partial last line
- **WHEN** the last line of the file has no trailing newline
- **THEN** it is not ingested until it is complete

#### Scenario: Restart
- **WHEN** the service restarts
- **THEN** it resumes from the stored cursor, with no missing and no duplicate rows

#### Scenario: File replaced or truncated
- **WHEN** the file identity changes or its size is below the stored offset
- **THEN** the service logs a warning, reads the current file from offset 0, and existing rows are not duplicated

#### Scenario: Same bar evaluated twice
- **WHEN** Runtime journals two `live_entry_evaluated` events for the same instance and bar
- **THEN** both are stored as separate rows

### Requirement: Health endpoint

The service MUST expose `GET /health` with status, cursor offset, last ingested
`occurred_at`, and skipped and malformed line counts, and no other HTTP endpoint in
this change.

#### Scenario: Health after ingestion
- **WHEN** the service has ingested events, skipped unrelated lines and met malformed ones
- **THEN** `GET /health` reports the cursor offset, the last ingested `occurred_at` and the skipped and malformed counts, and any other path answers 404

