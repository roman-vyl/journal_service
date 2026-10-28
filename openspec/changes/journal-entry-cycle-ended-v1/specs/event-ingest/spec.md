## ADDED Requirements

### Requirement: Ingest Runtime entry-cycle-ended events

The service MUST also store every `entry_cycle_ended` event with `schema_version >= 2` from the Runtime processing journal as one row of `events`. In that row:
- `source` is `'runtime'` and `body` is the line unchanged;
- `trade_cycle_id` is taken from `payload.trade_cycle_id`;
- `bar_open_time_ms` is taken from `payload.bar_open_time_ms`, an integer or null;
- `strategy_instance_id` and `occurred_at` are extracted for indexing.

`reason` MUST stay only in `body`. The service MUST NOT validate or interpret it, MUST NOT derive a trade-cycle status from it, and MUST NOT add tables or columns.

#### Scenario: Cycle ended during bar processing
- **WHEN** the journal contains an `entry_cycle_ended` line with `trade_cycle_id`, an integer `bar_open_time_ms` and a `reason`
- **THEN** it becomes one row with `trade_cycle_id` and `bar_open_time_ms` set and `body` equal to the source line

#### Scenario: Cycle ended outside a bar
- **WHEN** the line has `payload.bar_open_time_ms: null`
- **THEN** it becomes one row with a null `bar_open_time_ms`, and the `trade_cycle_id` filter returns it

#### Scenario: Unknown reason
- **WHEN** the line carries a `reason` the service has never seen
- **THEN** it is stored with `body` unchanged

#### Scenario: Malformed entry-cycle-ended line
- **WHEN** an `entry_cycle_ended` line meets any of these conditions:
  - it lacks `event_id`, `occurred_at`, `strategy_instance_id` or a non-empty string `payload.trade_cycle_id`;
  - `payload.bar_open_time_ms` is missing, or is neither an integer nor null;
  - `payload` is not an object
- **THEN** it is logged, counted as malformed and skipped, and ingestion continues

#### Scenario: Old schema
- **WHEN** an `entry_cycle_ended` line has `schema_version` 1
- **THEN** it is skipped and counted
