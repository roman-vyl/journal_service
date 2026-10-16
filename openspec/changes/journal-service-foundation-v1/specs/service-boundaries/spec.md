## ADDED Requirements

### Requirement: The Journal Service never affects trading

The Journal Service MUST NOT call Strategy Engine, Strategy Runtime, ABI or Market
Data Service, MUST NOT write to any file another service owns, and no trading
service may depend on it being available.

#### Scenario: Journal Service is down
- **WHEN** the Journal Service is stopped
- **THEN** every trading service keeps working unchanged, and on restart the service ingests what its sources accumulated in the meantime

### Requirement: Sources are read-only

Every source MUST be accessed read-only, and the service MUST keep its own
persisted cursor per source.

#### Scenario: Source mount
- **WHEN** the service is deployed
- **THEN** each source directory is mounted read-only into its container

### Requirement: Single owner of the journal database

The service MUST be the only writer of its SQLite database, which MUST run in WAL
mode, and the database MUST NOT be shared with any other service.

#### Scenario: Another service needs journal data
- **WHEN** another service needs data from the journal
- **THEN** it obtains it from this service's API, not by opening the database file

### Requirement: Append-only idempotent storage

Ingest MUST store each source event at most once, keyed by the source event id, MUST
advance the source cursor in the same transaction as the stored rows, and MUST NOT
update or delete stored rows.

#### Scenario: Same event read twice
- **WHEN** a source event is read again after a restart or file replacement
- **THEN** no second row is stored
