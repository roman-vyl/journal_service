## ADDED Requirements

### Requirement: Ingest live-entry observations from the Runtime processing journal

The Journal Service MUST read the Runtime processing journal file read-only and store
every `live_entry_evaluated` event with `schema_version >= 2` as one row of
`live_entry_observations`, keyed by `event_id`.

#### Scenario: Non-null and null observations
- **WHEN** the file contains `live_entry_evaluated` events with a desired entry and with `desired_entry = null`
- **THEN** each becomes one row; a null event has `has_desired_entry = 0` and null price columns

#### Scenario: Unrelated or old events
- **WHEN** a line has another `event_type` or `schema_version` 1
- **THEN** it is skipped and counted, and ingestion continues

#### Scenario: Malformed complete line
- **WHEN** a complete line is not valid JSON or lacks required fields
- **THEN** it is logged and skipped, and ingestion continues

### Requirement: Exactly-once storage across restarts

The service MUST persist a cursor (file identity and byte offset of the last
complete line) in the same transaction as the rows it ingested, and MUST insert rows
idempotently by `event_id`.

#### Scenario: Partial last line
- **WHEN** the last line of the file has no trailing newline
- **THEN** it is not ingested until it is complete

#### Scenario: Restart
- **WHEN** the service restarts
- **THEN** it resumes from the stored cursor, with no missing and no duplicate rows

#### Scenario: File replaced or truncated
- **WHEN** the file identity changes or its size is below the stored offset
- **THEN** the service logs a warning, reads the current file from offset 0, and existing rows are not duplicated

### Requirement: No effect on trading

The service MUST NOT call Strategy Engine, Strategy Runtime, ABI or Market Data
Service, MUST NOT write to any Runtime file, and no trading service may depend on it.

#### Scenario: Journal Service is down
- **WHEN** the Journal Service is stopped
- **THEN** Runtime keeps trading and writing its journal; on restart the service ingests the backlog

### Requirement: Health endpoint

The service MUST expose `GET /health` with status, cursor offset, last ingested
`occurred_at` and skipped-line count, and no other HTTP endpoint in this change.
