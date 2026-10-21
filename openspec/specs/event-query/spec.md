# event-query Specification

## Purpose
Read-only HTTP queries over the stored events: events of one strategy instance by bar range (whole range by default, optional limit) and the list of strategy instances with their evaluated bar range.
## Requirements
### Requirement: Events of one strategy instance by bar range
The service SHALL expose `GET /v1/events` with required `strategy_instance_id` and optional
`event_type`, `from_bar_ms`, `to_bar_ms` and `limit`. It SHALL return the stored events of that
instance whose `bar_open_time_ms` is within the inclusive range, ordered by `bar_open_time_ms`,
then `occurred_at`, then `event_id`. Each returned event SHALL carry `event_id`, `event_type`,
`schema_version`, `occurred_at`, `strategy_instance_id`, `bar_open_time_ms` and `body`, where
`body` is the stored source line parsed as JSON without any change.

#### Scenario: Range of bars
- **WHEN** an instance has events for bars 1 to 10 and the client asks `from_bar_ms` of bar 3 and `to_bar_ms` of bar 6
- **THEN** exactly the events of bars 3, 4, 5 and 6 are returned in bar order

#### Scenario: No signal and signal are both returned
- **WHEN** one stored event has `desired_entry = null` and another has a non-null `desired_entry`
- **THEN** both are returned with their `body` unchanged and the service does not interpret either

#### Scenario: Bar evaluated twice
- **WHEN** two events are stored for the same instance and bar
- **THEN** both are returned, ordered by `occurred_at`

#### Scenario: Missing bar
- **WHEN** no event is stored for a bar inside the requested range
- **THEN** nothing is returned for that bar and the response gives no sign that it was a "no signal" bar

#### Scenario: Other instances are not mixed in
- **WHEN** other strategy instances have events in the same bar range
- **THEN** none of them is returned

### Requirement: Whole range by default
Without `limit` the service SHALL return every stored event of the instance within the range, with no maximum count. `limit` is optional; when given, the service SHALL return at most `limit` events, oldest bars first. The response SHALL contain `truncated`, true only when `limit` was given and more matching events exist.

#### Scenario: Range larger than any former cap
- **WHEN** 12000 events match the range and `limit` is not given
- **THEN** all 12000 are returned in order and `truncated` is false

#### Scenario: Optional limit
- **WHEN** 1200 events match and `limit` is 1000
- **THEN** 1000 events are returned, the oldest bars first, and `truncated` is true

### Requirement: Invalid requests
A missing or empty `strategy_instance_id`, a non-integer `from_bar_ms`, `to_bar_ms` or `limit`,
a `limit` below 1, or `from_bar_ms` greater than `to_bar_ms` SHALL be answered with HTTP 400 and
`{"error": "<message>"}`. Unknown paths SHALL be answered with HTTP 404.

#### Scenario: Missing instance id
- **WHEN** `GET /v1/events` has no `strategy_instance_id`
- **THEN** HTTP 400 with an error message

### Requirement: Strategy instances with their evaluated bar range
The service SHALL expose `GET /v1/strategy-instances` returning, for every strategy instance
that has stored events, `strategy_instance_id`, `event_count`, `first_bar_open_time_ms`,
`last_bar_open_time_ms` and `last_occurred_at`, sorted by `strategy_instance_id`.

#### Scenario: Two instances
- **WHEN** instance A has 3 events and instance B has 5
- **THEN** both are listed with their own counts and bar ranges

#### Scenario: Empty database
- **WHEN** no event is stored
- **THEN** the list is empty

### Requirement: Reads do not disturb ingestion
Query requests SHALL use read-only database access, SHALL NOT write, and SHALL NOT delay or
change the tailer's storing of events or its cursor.

#### Scenario: Query during ingestion
- **WHEN** a query runs while the tailer stores a batch
- **THEN** the batch is stored, the cursor advances, and the query sees either the state before or after the batch

### Requirement: Query endpoints do not change what is indexed
Adding query endpoints SHALL NOT change which events are ingested, the stored rows, or
`GET /health`.

#### Scenario: Ingestion unchanged
- **WHEN** the query endpoints are present
- **THEN** only `live_entry_evaluated` events with `schema_version >= 2` are stored, as before

### Requirement: Stored-event contract is documented
The change SHALL document, in `design.md`, the `events` table columns and indexes, the shape of
`body`, and for each field a reader needs (strategy, bar, market, side, planned entry, initial
stop, initial take, no-signal marker) its path in `body`, its type, and which component writes it.

#### Scenario: Reader locates a projection field
- **WHEN** a reader needs the initial stop of an evaluated bar
- **THEN** the document names `body.payload.desired_entry.initial_stop_price`, its decimal-text type and its producer

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

