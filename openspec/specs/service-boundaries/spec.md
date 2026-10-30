# service-boundaries Specification

## Purpose
Purpose, boundaries and stack of the Central Journal: an indexer of facts that producer services write into their own processing journals.
## Requirements
### Requirement: The Central Journal never affects trading

The service MUST NOT call Strategy Engine, Strategy Runtime or Market Data Service. Toward ABI it MAY only send `GET` requests to `/v1/strategy-instances/{strategy_instance_id}/trade-cycles/{trade_cycle_id}/exchange-journal`; it MUST NOT call any other ABI route. It MUST NOT write to any file another service owns, and no trading service may depend on it being available.

#### Scenario: Central Journal is down
- **WHEN** the service is stopped
- **THEN** every trading service keeps working unchanged, and on restart the service ingests what the journals accumulated in the meantime and resumes building incomplete trades

#### Scenario: Only the per-cycle read route
- **WHEN** the service talks to ABI
- **THEN** every request is a `GET` to the per-cycle exchange-journal route, and no order, cancel, close, protection or recovery route is called

### Requirement: Events are indexed, not interpreted

The `events` table MUST hold producer events as received. The service MUST NOT derive events from another service's internal state or correlation snapshots, compute what Engine wanted, or determine an order or position state. The only derived data the service MAY keep is the `closed_trades` table of the `closed-trades` capability; it MUST NOT write derived data into `events`.

#### Scenario: A new fact is needed
- **WHEN** a feature needs a fact that no producer journals yet
- **THEN** the producing service is changed to journal it, and the Central Journal only learns to accept the new `event_type`

#### Scenario: Derived data stays out of events
- **WHEN** closed-trade data exists
- **THEN** it is only in `closed_trades`, and `events` holds producer lines only

### Requirement: Sources are read-only processing journals

Every source of the `events` table MUST be a producer's append-only processing journal accessed read-only, with a persisted cursor per source. ABI exchange facts are read per trade cycle through ABI's read API and MUST NOT be stored; only the assembled `closed_trades` row is stored.

#### Scenario: Source mount
- **WHEN** the service is deployed
- **THEN** each source journal directory is mounted read-only into its container

#### Scenario: ABI facts are not copied
- **WHEN** the service reads a trade cycle from ABI
- **THEN** no ABI event or link is stored anywhere in the database; only that cycle's `closed_trades` row changes

### Requirement: Single owner of the journal database

The service MUST be the only process that opens its SQLite database, which MUST run
in WAL mode.

#### Scenario: Another service needs journal data
- **WHEN** another service or the frontend needs journal data
- **THEN** it obtains it from this service's API, not by opening the database file

### Requirement: Append-only idempotent storage

The service MUST store each event at most once, keyed by (`source`, `event_id`), MUST advance the source cursor in the same transaction as the stored rows, and MUST NOT update or delete stored `events` rows. A `closed_trades` row MAY be updated only while its `status` is `incomplete`; once `complete` it MUST NOT be updated or deleted.

#### Scenario: Same event read twice
- **WHEN** an event is read again after a restart or file replacement
- **THEN** no second row is stored

#### Scenario: Complete trade is frozen
- **WHEN** a `closed_trades` row is `complete`
- **THEN** no later pass, restart or new ABI data changes it

