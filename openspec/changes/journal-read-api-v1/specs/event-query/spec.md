## ADDED Requirements

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

### Requirement: Bounded answers
`limit` SHALL default to 1000 and SHALL NOT exceed 5000. The response SHALL contain
`truncated`, true when more matching events exist than were returned.

#### Scenario: More rows than the limit
- **WHEN** 1200 events match and `limit` is 1000
- **THEN** 1000 events are returned, the oldest bars first, and `truncated` is true

#### Scenario: Limit too large
- **WHEN** `limit` is 5001
- **THEN** the service answers HTTP 400 with an error message

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
