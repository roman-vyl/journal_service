## ADDED Requirements

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
