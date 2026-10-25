## ADDED Requirements

### Requirement: Ingest Runtime entry-package-declined events

The service MUST also store every `entry_package_declined` event with `schema_version >= 2` from the Runtime processing journal as one row of `events`. In that row:
- `source` is `'runtime'` and `body` is the line unchanged;
- `trade_cycle_id` is taken from `payload.trade_cycle_id`;
- `bar_open_time_ms` is taken from `payload.bar_open_time_ms`, an integer;
- `strategy_instance_id` and `occurred_at` are extracted for indexing.

`risk_multiplier`, `decline_reason` and `decline_message` MUST stay only in `body`. The service MUST NOT validate or interpret them, MUST NOT derive a trade-cycle status from them, and MUST NOT add tables or columns.

#### Scenario: Declined entry on a committed bar
- **WHEN** the journal contains an `entry_package_declined` line with `trade_cycle_id`, an integer `bar_open_time_ms`, `risk_multiplier`, `decline_reason` and `decline_message`
- **THEN** it becomes one row with `trade_cycle_id` and `bar_open_time_ms` set and `body` equal to the source line

#### Scenario: Unknown decline reason
- **WHEN** an `entry_package_declined` line carries a `decline_reason` the service has never seen
- **THEN** it is stored with `body` unchanged, because the reason is not interpreted

#### Scenario: Same bar as the evaluation
- **WHEN** a `live_entry_evaluated` and an `entry_package_declined` line have the same `strategy_instance_id` and `bar_open_time_ms`
- **THEN** a bar-range query of that instance returns both

#### Scenario: Malformed entry-package-declined line
- **WHEN** an `entry_package_declined` line meets any of these conditions:
  - it lacks `event_id`, `occurred_at`, `strategy_instance_id` or a non-empty string `payload.trade_cycle_id`;
  - `payload.bar_open_time_ms` is missing or not an integer, including null;
  - `payload` is not an object
- **THEN** it is logged, counted as malformed and skipped, and ingestion continues

#### Scenario: Old schema
- **WHEN** an `entry_package_declined` line has `schema_version` 1
- **THEN** it is skipped and counted
