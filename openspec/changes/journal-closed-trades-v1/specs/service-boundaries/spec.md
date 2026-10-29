## MODIFIED Requirements

### Requirement: The Central Journal never affects trading

The service MUST NOT call Strategy Engine, Strategy Runtime or Market Data Service. Toward ABI it MAY only send `GET` requests to ABI's exchange-journal read API; it MUST NOT call any other ABI route. It MUST NOT write to any file another service owns, and no trading service may depend on it being available.

#### Scenario: Central Journal is down
- **WHEN** the service is stopped
- **THEN** every trading service keeps working unchanged, and on restart the service ingests what the journals accumulated in the meantime and completes the trades it had not completed

#### Scenario: Only the exchange-journal read API
- **WHEN** the service talks to ABI
- **THEN** every request is a `GET` to a `/v1/strategy-instances/{sid}/trade-cycles/{cid}/exchange-journal` path, and no order, cancel, close, protection or recovery route is ever called

### Requirement: Events are indexed, not interpreted

The `events` table MUST hold producer events as received. The service MUST NOT derive events from another service's internal state or correlation snapshots, compute what Engine wanted, or determine an order or position state. The only derived data the service keeps is the `closed_trades` table of the `closed-trades` capability, built from stored Runtime events and ABI's exchange-journal read API; it MUST NOT write derived data into `events`.

#### Scenario: A new fact is needed
- **WHEN** a feature needs a fact that no producer journals yet
- **THEN** the producing service is changed to journal it, and the Central Journal only learns to accept the new `event_type`

#### Scenario: Trade metrics
- **WHEN** a closed trade's prices, fees and profit are needed
- **THEN** they are computed only into `closed_trades`, and `events` is not changed

### Requirement: Sources are read-only processing journals

Every source of the `events` table MUST be a producer's append-only processing journal accessed read-only, with a persisted cursor per source. ABI's exchange facts are read on demand through its read API for one trade cycle at a time and MUST NOT be copied into the database; only the assembled closed-trade row is stored.

#### Scenario: Source mount
- **WHEN** the service is deployed
- **THEN** each source journal directory is mounted read-only into its container

#### Scenario: ABI facts are not copied
- **WHEN** the service reads a trade cycle from ABI
- **THEN** no ABI event or link is stored; only the `closed_trades` row of that cycle is written

### Requirement: Append-only idempotent storage

The service MUST store each event at most once, keyed by (`source`, `event_id`), MUST advance the source cursor in the same transaction as the stored rows, and MUST NOT update or delete stored `events` rows. A `closed_trades` row MAY be updated only while its `status` is `incomplete`; once `complete` it MUST NOT be updated or deleted.

#### Scenario: Same event read twice
- **WHEN** an event is read again after a restart or file replacement
- **THEN** no second row is stored

#### Scenario: Complete trade is frozen
- **WHEN** a `closed_trades` row is `complete`
- **THEN** no later retry, restart or new ABI data changes it
