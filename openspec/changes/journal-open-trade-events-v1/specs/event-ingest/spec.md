## ADDED Requirements

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
