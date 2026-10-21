## ADDED Requirements

### Requirement: Events of one trade cycle

`GET /v1/events` SHALL accept an optional `trade_cycle_id` and, when it is given, return only events of the instance whose stored `trade_cycle_id` equals it, combined with the other filters and in the same order. Every returned event SHALL also carry `trade_cycle_id`, null when the row has none. The service SHALL NOT derive a cycle status or infer anything from a missing event.

#### Scenario: Entry and closure of one cycle
- **WHEN** an instance has `entry_package_applied` and `trade_cycle_closed` for cycle C and events of other cycles
- **THEN** a query with `trade_cycle_id` C returns exactly the two events of C, each with `trade_cycle_id` C

#### Scenario: Events without a cycle
- **WHEN** a query has no `trade_cycle_id` and the instance has `live_entry_evaluated` events
- **THEN** they are returned with `trade_cycle_id` null

#### Scenario: Closure without a bar
- **WHEN** a stored `trade_cycle_closed` has a null `bar_open_time_ms`
- **THEN** it is returned by a query without `from_bar_ms` and `to_bar_ms`, before the events with a bar, and is not returned when either bound is given
