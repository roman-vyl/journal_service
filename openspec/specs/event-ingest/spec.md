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
`occurred_at`, and skipped and malformed line counts. Other endpoints are only those of the
`event-query` capability.

#### Scenario: Health after ingestion
- **WHEN** the service has ingested events, skipped unrelated lines and met malformed ones
- **THEN** `GET /health` reports the cursor offset, the last ingested `occurred_at` and the skipped and malformed counts, and any path that is neither `/health` nor an `event-query` path answers 404

### Requirement: Ingest Runtime entry-package-applied events

The service MUST also store every `entry_package_applied` event with `schema_version >= 2` from the Runtime processing journal as one row of `events` with `source = 'runtime'`, the line kept unchanged as `body`, `trade_cycle_id` taken from `payload.trade_cycle_id`, `bar_open_time_ms` taken from `payload.bar_open_time_ms`, and `strategy_instance_id` and `occurred_at` extracted for indexing. `order_link_id`, `order_id`, `trigger_price`, `stop_loss`, `take_profit` and `quantity` MUST stay only in `body`; the service MUST NOT validate or interpret them and MUST NOT add tables or columns for them.

#### Scenario: Applied entry with order identity
- **WHEN** the journal contains an `entry_package_applied` line with `trade_cycle_id`, `bar_open_time_ms`, the four order values, `order_link_id` and `order_id`
- **THEN** it becomes one row with `trade_cycle_id` and `bar_open_time_ms` set and `body` equal to the source line

#### Scenario: Null values and ids
- **WHEN** the payload has any of the four values, `order_link_id` or `order_id` equal to null
- **THEN** the row is stored with `body` unchanged

#### Scenario: Same bar as the evaluation
- **WHEN** a `live_entry_evaluated` and an `entry_package_applied` line have the same `strategy_instance_id` and `bar_open_time_ms`
- **THEN** both rows carry that pair and a bar-range query returns both

#### Scenario: Malformed entry-package-applied line
- **WHEN** an `entry_package_applied` line lacks `event_id`, `occurred_at`, `strategy_instance_id`, a string `payload.trade_cycle_id` or an integer `payload.bar_open_time_ms`, or has `payload` that is not an object
- **THEN** it is logged, counted as malformed and skipped, and ingestion continues

#### Scenario: Old schema
- **WHEN** an `entry_package_applied` line has `schema_version` 1
- **THEN** it is skipped and counted

### Requirement: Ingest Runtime trade-cycle-opened events

The service MUST also store every `trade_cycle_opened` event with `schema_version >= 2` from the Runtime processing journal as one row of `events` with `source = 'runtime'`, the line kept unchanged as `body`, `trade_cycle_id` taken from `payload.trade_cycle_id`, `bar_open_time_ms` taken from `payload.bar_open_time_ms` (integer or null), and `strategy_instance_id` and `occurred_at` extracted for indexing. `first_fill_at_ms`, `average_entry_price`, `entry_order_link_id` and `entry_order_id` MUST stay only in `body`; the service MUST NOT validate or interpret them, MUST NOT derive a position, cycle status or projection from them, and MUST NOT add tables or columns.

#### Scenario: Opened on a committed bar
- **WHEN** the journal contains a `trade_cycle_opened` line with `trade_cycle_id` and an integer `bar_open_time_ms`
- **THEN** it becomes one row with `trade_cycle_id` and `bar_open_time_ms` set and `body` equal to the source line

#### Scenario: Opened during recovery
- **WHEN** a `trade_cycle_opened` line has `payload.bar_open_time_ms` equal to null and `payload.entry_order_id` equal to null
- **THEN** it becomes one row with `bar_open_time_ms` null and `body` equal to the source line

#### Scenario: Malformed trade-cycle-opened line
- **WHEN** a `trade_cycle_opened` line lacks `event_id`, `occurred_at`, `strategy_instance_id` or a non-empty string `payload.trade_cycle_id`, lacks `payload.bar_open_time_ms`, has a bar that is neither an integer nor null, or has `payload` that is not an object
- **THEN** it is logged, counted as malformed and skipped, and ingestion continues

#### Scenario: Old schema
- **WHEN** a `trade_cycle_opened` line has `schema_version` 1
- **THEN** it is skipped and counted

#### Scenario: Whole cycle by id
- **WHEN** an instance has `entry_package_applied`, `trade_cycle_opened` and `trade_cycle_closed` for cycle C
- **THEN** `GET /v1/events` with `trade_cycle_id` C returns those three events

### Requirement: Ingest Runtime trade-cycle-closed events

The service MUST also store every `trade_cycle_closed` event with `schema_version >= 2` from the Runtime processing journal as one row of `events` with `source = 'runtime'`, the line kept unchanged as `body`, `trade_cycle_id` taken from `payload.trade_cycle_id`, `bar_open_time_ms` taken from `payload.bar_open_time_ms` (integer or null), and `strategy_instance_id` and `occurred_at` extracted for indexing. `reason`, `order_id`, `order_link_id` and `parent_order_link_id` MUST stay only in `body`; the service MUST NOT validate or interpret them, MUST NOT treat `occurred_at` as an exchange execution time, and MUST NOT add tables, columns or derived trade-cycle state.

#### Scenario: Closure on a committed bar
- **WHEN** the journal contains a `trade_cycle_closed` line with `trade_cycle_id`, an integer `bar_open_time_ms` and `reason`
- **THEN** it becomes one row with `trade_cycle_id` and `bar_open_time_ms` set and `body` equal to the source line

#### Scenario: Closure without a bar
- **WHEN** a `trade_cycle_closed` line has `payload.bar_open_time_ms` equal to null
- **THEN** it becomes one row with `bar_open_time_ms` null and `body` equal to the source line

#### Scenario: Malformed trade-cycle-closed line
- **WHEN** a `trade_cycle_closed` line lacks `event_id`, `occurred_at`, `strategy_instance_id` or a string `payload.trade_cycle_id`, lacks `payload.bar_open_time_ms`, has a bar that is neither an integer nor null, or has `payload` that is not an object
- **THEN** it is logged, counted as malformed and skipped, and ingestion continues

#### Scenario: Null bar stays malformed for other types
- **WHEN** a `live_entry_evaluated` or `entry_package_applied` line has `payload.bar_open_time_ms` equal to null
- **THEN** it is counted as malformed and skipped, as before

#### Scenario: Old schema
- **WHEN** a `trade_cycle_closed` line has `schema_version` 1
- **THEN** it is skipped and counted

### Requirement: Ingest Runtime open-trade evaluations and confirmed protection

The service MUST also store every `open_trade_evaluated` and every `protection_applied` event with `schema_version >= 2` from the Runtime processing journal as one row of `events` with `source = 'runtime'`, the line kept unchanged as `body`, `trade_cycle_id` taken from `payload.trade_cycle_id`, `bar_open_time_ms` taken from `payload.bar_open_time_ms` (integer), and `strategy_instance_id` and `occurred_at` extracted for indexing. Every other payload field, including `position_quantity`, the protection levels, the close signal and the protective orders, MUST stay only in `body`; the service MUST NOT validate or interpret them, MUST NOT derive a position, protection state or projection from them, and MUST NOT add tables or columns.

#### Scenario: Open-trade evaluation
- **WHEN** the journal contains an `open_trade_evaluated` line with `trade_cycle_id` and an integer `bar_open_time_ms`
- **THEN** it becomes one row with `trade_cycle_id` and `bar_open_time_ms` set and `body` equal to the source line

#### Scenario: Confirmed protection with a disabled take
- **WHEN** a `protection_applied` line has `requested_protection.take_price` null and a `take_order` with an order id and trigger price
- **THEN** it becomes one row with `trade_cycle_id` and `bar_open_time_ms` set and `body` equal to the source line, both values kept

#### Scenario: Malformed line
- **WHEN** an `open_trade_evaluated` or `protection_applied` line lacks `event_id`, `occurred_at`, `strategy_instance_id` or a non-empty string `payload.trade_cycle_id`, lacks `payload.bar_open_time_ms`, has a bar that is not an integer (null included), or has `payload` that is not an object
- **THEN** it is logged, counted as malformed and skipped, and ingestion continues

#### Scenario: Old schema
- **WHEN** an `open_trade_evaluated` or `protection_applied` line has `schema_version` 1
- **THEN** it is skipped and counted

#### Scenario: Whole cycle by id
- **WHEN** an instance has `entry_package_applied`, `trade_cycle_opened`, `open_trade_evaluated`, `protection_applied` and `trade_cycle_closed` for cycle C
- **THEN** `GET /v1/events` with `trade_cycle_id` C returns all of them

