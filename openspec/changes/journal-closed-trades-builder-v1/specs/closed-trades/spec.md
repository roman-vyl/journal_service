## ADDED Requirements

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
