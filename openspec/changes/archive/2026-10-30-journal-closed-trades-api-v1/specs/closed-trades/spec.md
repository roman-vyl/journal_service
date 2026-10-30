## ADDED Requirements

### Requirement: List of closed trades

The service SHALL expose `GET /v1/closed-trades` with optional `strategy_instance_id`,
`from_closed_ms`, `to_closed_ms`, `status` and `limit`. It SHALL return
`{"trades": [...], "truncated": bool}`, where each trade is one `closed_trades` row as stored.
Rows SHALL be ordered by `closed_at_ms`, then `close_event_id`; rows with no `closed_at_ms`
SHALL come first, ordered by `created_at_ms`, then `close_event_id`.

#### Scenario: All trades
- **WHEN** the table holds three complete rows and one incomplete row and no parameter is given
- **THEN** all four rows are returned, the incomplete row first, then the complete rows by close time, and `truncated` is false

#### Scenario: One strategy instance
- **WHEN** `strategy_instance_id` is given
- **THEN** only rows of that instance are returned

#### Scenario: Close period
- **WHEN** `from_closed_ms` and `to_closed_ms` are given
- **THEN** only rows whose `closed_at_ms` is within the inclusive range are returned, and rows with no `closed_at_ms` are not returned

#### Scenario: Status filter
- **WHEN** `status=incomplete` is given
- **THEN** only incomplete rows are returned, each with `attempts`, `last_attempt_at_ms` and `last_error`

#### Scenario: Limit
- **WHEN** 5 rows match and `limit` is 2
- **THEN** the first 2 rows in order are returned and `truncated` is true

#### Scenario: Empty table
- **WHEN** no row is stored
- **THEN** `trades` is empty and `truncated` is false

### Requirement: One closed trade

The service SHALL expose `GET /v1/closed-trades/{strategy_instance_id}/{trade_cycle_id}`
returning `{"trade": {...}}` with the stored row, or HTTP 404 with `{"error": "closed trade
not found"}` when no row exists for that pair.

#### Scenario: Known trade
- **WHEN** the row for the real Demo short `6072511f` is complete
- **THEN** the response carries `net_pnl_usdt` `"-1307.99088539"`, `gross_pnl_usdt` `"-969.3902"` and `status` `complete`

#### Scenario: Unknown trade
- **WHEN** no row exists for the pair
- **THEN** HTTP 404

### Requirement: Trade rows are returned as stored

Every column of `closed_trades` SHALL be a key of the returned trade object under its column
name. Decimal values SHALL keep their stored text, integers SHALL stay integers and empty values
SHALL be `null`. The read endpoints SHALL NOT round, recompute, aggregate or add fields.

#### Scenario: Decimal text
- **WHEN** a stored `r_multiple` is a long decimal text such as the real short's `-1.3780585…`
- **THEN** the response carries exactly the stored string, every digit kept

### Requirement: Invalid closed-trade requests

A non-integer `from_closed_ms`, `to_closed_ms` or `limit`, a `limit` below 1, `from_closed_ms`
greater than `to_closed_ms`, a `status` other than `complete` or `incomplete`, or an empty
`strategy_instance_id` SHALL be answered with HTTP 400 and `{"error": "<message>"}`. A path
under `/v1/closed-trades/` that is not exactly two non-empty segments SHALL be answered with
HTTP 404.

#### Scenario: Bad status
- **WHEN** `status=open` is given
- **THEN** HTTP 400 with an error message

#### Scenario: Three segments
- **WHEN** `GET /v1/closed-trades/a/b/c`
- **THEN** HTTP 404

### Requirement: Closed-trade reads change nothing

Closed-trade requests SHALL use read-only database access, SHALL NOT write, and SHALL NOT
delay the tailer or the trade builder.

#### Scenario: Read during a builder pass
- **WHEN** a list request runs while the builder completes a row
- **THEN** the request answers with the rows as they were or as they are after the update, and the builder's update is not blocked
