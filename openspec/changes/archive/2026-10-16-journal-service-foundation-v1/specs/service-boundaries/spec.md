## ADDED Requirements

### Requirement: The Central Journal never affects trading

The service MUST NOT call Strategy Engine, Strategy Runtime, ABI or Market Data
Service, MUST NOT write to any file another service owns, and no trading service may
depend on it being available.

#### Scenario: Central Journal is down
- **WHEN** the service is stopped
- **THEN** every trading service keeps working unchanged, and on restart the service ingests what the journals accumulated in the meantime

### Requirement: Events are indexed, not interpreted

The service MUST store producer events as received and MUST NOT derive events from
another service's internal state or correlation snapshots, compute what Engine
wanted, or determine an order or position state.

#### Scenario: A new fact is needed
- **WHEN** a feature needs a fact that no producer journals yet
- **THEN** the producing service is changed to journal it, and the Central Journal only learns to accept the new `event_type`

### Requirement: Sources are read-only processing journals

Every source MUST be a producer's append-only processing journal accessed read-only,
with a persisted cursor per source.

#### Scenario: Source mount
- **WHEN** the service is deployed
- **THEN** each source journal directory is mounted read-only into its container

### Requirement: Single owner of the journal database

The service MUST be the only process that opens its SQLite database, which MUST run
in WAL mode.

#### Scenario: Another service needs journal data
- **WHEN** another service or the frontend needs journal data
- **THEN** it obtains it from this service's API, not by opening the database file

### Requirement: Append-only idempotent storage

The service MUST store each event at most once, keyed by (`source`, `event_id`),
MUST advance the source cursor in the same transaction as the stored rows, and MUST
NOT update or delete stored rows.

#### Scenario: Same event read twice
- **WHEN** an event is read again after a restart or file replacement
- **THEN** no second row is stored
