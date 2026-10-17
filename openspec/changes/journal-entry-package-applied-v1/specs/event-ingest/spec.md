## ADDED Requirements

### Requirement: Ingest Runtime entry-package-applied events

The service MUST also store every `entry_package_applied` event with `schema_version >= 2` from the Runtime processing journal as one row of `events` with `source = 'runtime'`, the line kept unchanged as `body`, `trade_cycle_id` taken from `payload.trade_cycle_id`, and `strategy_instance_id` and `occurred_at` extracted for indexing. `bar_open_time_ms` MUST be null. It MUST NOT validate or interpret the values in the payload.

#### Scenario: Applied entry with four values
- **WHEN** the journal contains an `entry_package_applied` line with `trade_cycle_id`, `trigger_price`, `stop_loss`, `take_profit` and `quantity`
- **THEN** it becomes one row with `trade_cycle_id` set, `bar_open_time_ms` null and `body` equal to the source line

#### Scenario: Null stop-loss and take-profit
- **WHEN** the payload has `stop_loss` or `take_profit` equal to null
- **THEN** the row is stored with `body` unchanged

#### Scenario: Malformed entry-package-applied line
- **WHEN** an `entry_package_applied` line lacks `event_id`, `occurred_at`, `strategy_instance_id` or a string `payload.trade_cycle_id`, or has `payload` that is not an object
- **THEN** it is logged, counted as malformed and skipped, and ingestion continues

#### Scenario: Old schema
- **WHEN** an `entry_package_applied` line has `schema_version` 1
- **THEN** it is skipped and counted
