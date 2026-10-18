## ADDED Requirements

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
