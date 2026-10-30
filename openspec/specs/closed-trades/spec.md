# closed-trades Specification

## Purpose
Closed-trades journal: one row per closed trade (strategy instance and trade cycle), built from Runtime events and the ABI per-cycle route, with a read API. Rows are stored as facts and arithmetic over facts; a missing input stays empty.
## Requirements
### Requirement: Closed-trades table

The database SHALL contain a table `closed_trades` with primary key (`strategy_instance_id`, `trade_cycle_id`) and exactly the columns listed in this change's `design.md` (blocks 1–6), with the meaning, source and formula given there. Prices, quantities and money SHALL be stored as decimal text and times as UTC milliseconds. A column whose input is missing SHALL be null.

#### Scenario: New database
- **WHEN** the service creates a new database
- **THEN** it has schema version 2 with the `events` and `closed_trades` tables

#### Scenario: Upgrade keeps events
- **WHEN** the service opens a version 1 database holding events and a cursor
- **THEN** it adds an empty `closed_trades` table, sets version 2, and every event row and the cursor are unchanged

### Requirement: Formulas are fixed by this change

Any later change that fills `closed_trades` SHALL compute its columns with the formulas of this change's `design.md`, in decimal arithmetic. A formula SHALL be changed only by a new change approved by the owner.

#### Scenario: Real Demo short closed by stop
- **WHEN** a short trade has one entry execution `80496.1` × `3.818` with fee `169.03376039` and one stop-loss execution `80750` × `3.818` with fee `169.566925`
- **THEN** `gross_pnl_usdt` is `-969.3902`, `fees_usdt` is `338.60068539` and `net_pnl_usdt` is `-1307.99088539`

#### Scenario: Several fills
- **WHEN** the entry has executions 1 @ 100 and 3 @ 104
- **THEN** `entry_avg_price` is `103`, `entry_qty` is `4` and `entry_fill_count` is `2`

### Requirement: Closed trades are detected from stored closures

The service SHALL run a closed-trades builder, separate from event ingestion, every `JOURNAL_TRADES_INTERVAL_S` seconds (default 60). Each pass SHALL create one `incomplete` row for every (`strategy_instance_id`, `trade_cycle_id`) that has a stored `trade_cycle_closed` event and no `closed_trades` row, taking `close_reason`, `close_event_id` and `closing_order_id` from the first such event. Later `trade_cycle_closed` events of the same pair SHALL be ignored. A failure of the builder SHALL NOT stop or delay event ingestion.

#### Scenario: New closure
- **WHEN** a `trade_cycle_closed` of instance S and cycle C is ingested
- **THEN** within one interval a row (S, C) exists with `status` `incomplete`

#### Scenario: Closures stored before the builder existed
- **WHEN** the service starts with stored closures and no rows
- **THEN** the first pass creates one row per closed pair

#### Scenario: Cycle ended without a fill
- **WHEN** a cycle has `entry_cycle_ended` and no `trade_cycle_closed`
- **THEN** it gets no row

### Requirement: Incomplete rows are assembled from Runtime events and ABI

For every `incomplete` row each pass SHALL read the pair's Runtime events from `events` and send one `GET` to ABI's per-cycle exchange-journal route with a 5 s timeout. Only executions with `exec_type` `Trade` SHALL count: entry executions from orders with role `entry`, exit executions from roles `close`, `stop_loss` and `take_profit`. The row SHALL become `complete` when there is at least one entry execution and the order whose `order_id` equals `closing_order_id` has an `order_state` with `order_status` `Filled` and at least one execution; then every column SHALL be written with the formulas of `journal-closed-trades-table-v1` in one transaction, with `completed_at_ms`. Otherwise only `attempts`, `last_attempt_at_ms` and `last_error` SHALL change, and the row SHALL be retried on every later pass without a deadline.

#### Scenario: Real Demo short closed by stop
- **WHEN** ABI returns one entry execution `80496.1` × `3.818` fee `169.03376039` (`side` `Sell`) and a `Filled` stop-loss order named by the closure with one execution `80750` × `3.818` fee `169.566925`
- **THEN** the row is `complete`, `side` `short`, `gross_pnl_usdt` `-969.3902`, `fees_usdt` `338.60068539`, `net_pnl_usdt` `-1307.99088539`

#### Scenario: Exit arrives on a later pass
- **WHEN** the first pass finds the entry execution but the closing order is not yet `Filled`
- **THEN** the row stays `incomplete` with `last_error` `closing_order_not_filled`, and a later pass completes it

#### Scenario: ABI unavailable or not configured
- **WHEN** ABI does not answer within 5 s, answers non-200, returns `truncated: true`, or no ABI address is configured
- **THEN** the row stays `incomplete` with the matching `last_error`, and ingestion of Runtime events continues

#### Scenario: Funding ignored
- **WHEN** ABI returns a `Funding` execution for the cycle
- **THEN** it changes no price, quantity, fee or profit

#### Scenario: Complete row never changes
- **WHEN** a row is `complete` and later passes or restarts happen
- **THEN** the row is not selected and stays identical

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

