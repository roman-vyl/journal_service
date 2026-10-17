## ADDED Requirements

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
