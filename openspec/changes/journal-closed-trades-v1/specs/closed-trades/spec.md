## ADDED Requirements

### Requirement: One row per closed trade

The service SHALL keep a table `closed_trades` with exactly one row per (`strategy_instance_id`, `trade_cycle_id`) for which a Runtime `trade_cycle_closed` event is stored in `events`. The first stored `trade_cycle_closed` of the pair creates the row; later ones for the same pair are ignored. Rows SHALL also be created for `trade_cycle_closed` events stored before this capability existed. A cycle without `trade_cycle_closed` (for example one ended by `entry_cycle_ended`) SHALL NOT get a row.

#### Scenario: Closure creates a row
- **WHEN** a `trade_cycle_closed` for instance S and cycle C is stored
- **THEN** a row (S, C) exists with `status` `incomplete`, `close_reason` and `closing_order_id` from the event payload

#### Scenario: Backfill
- **WHEN** the service starts with closures already stored and no `closed_trades` rows
- **THEN** one row per closed pair is created

#### Scenario: Cycle without a fill
- **WHEN** a cycle has `entry_package_applied` and `entry_cycle_ended` but no `trade_cycle_closed`
- **THEN** it has no row

### Requirement: Exchange part read from ABI per cycle

For an `incomplete` row the service SHALL request ABI's `GET /v1/strategy-instances/{sid}/trade-cycles/{cid}/exchange-journal` with a 5 s timeout. Only events with `fact_kind` `execution` and `exec_type` `Trade` SHALL count. Entry executions are those of orders whose link `role` is `entry`; exit executions are those of orders whose `role` is `close`, `stop_loss` or `take_profit`. Other executions SHALL be ignored. A non-`200` answer, a timeout, a connection error or any `truncated: true` SHALL leave the row `incomplete` with `last_error` set and `attempts` increased.

#### Scenario: ABI unavailable
- **WHEN** ABI answers `503` or does not answer within 5 s
- **THEN** the row stays `incomplete`, `last_error` names the failure, and ingestion of Runtime events continues

#### Scenario: Funding is ignored
- **WHEN** ABI returns a `Funding` execution
- **THEN** it does not change prices, quantities, fees or profit

### Requirement: Completion rule

A row SHALL become `complete` when ABI returns at least one entry execution and the order whose `order_id` equals the row's `closing_order_id` has an `order_state` with `order_status` `Filled` and at least one execution. Until then the service SHALL retry the row every `JOURNAL_TRADES_RETRY_S` seconds (default 60) without a deadline. On completion the service SHALL write all fields and `completed_at_ms` in one transaction; a `complete` row SHALL NOT change afterwards. The service SHALL NOT compare entry and exit quantities in this capability.

#### Scenario: Exit arrives later
- **WHEN** the first attempt finds the entry fill but not the closing order's fill, and a later attempt finds it
- **THEN** the row is `incomplete` after the first attempt and `complete` after the later one

#### Scenario: Restart with incomplete rows
- **WHEN** the service restarts with `incomplete` rows
- **THEN** it retries them and leaves `complete` rows unchanged

### Requirement: Trade fields and formulas

On completion the row SHALL carry the fields and formulas of design D5, computed in decimal arithmetic and stored as decimal text: `symbol`, `side` (`long` when the entry side is `Buy`, `short` when `Sell`), `opened_at_ms`, `closed_at_ms`, `duration_ms`, entry and exit average prices, quantities, fill counts and fees, `entry_notional_usdt`, the plan values from the cycle's last `entry_package_applied` and last `protection_applied`, `gross_pnl_usdt`, `fees_usdt`, `net_pnl_usdt`, `price_return_pct`, `net_return_pct`, `risk_usdt`, `r_multiple`, `entry_slippage_pct` and `exit_slippage_pct`. A field whose input is missing SHALL be null; the service SHALL NOT substitute an estimate.

#### Scenario: Real Demo short closed by stop
- **WHEN** a short cycle has one entry execution `execPrice` `80496.1`, `execQty` `3.818`, `execFee` `169.03376039` and one stop-loss execution `execPrice` `80750`, `execQty` `3.818`, `execFee` `169.566925`
- **THEN** `side` is `short`, `gross_pnl_usdt` is `-969.3902`, `fees_usdt` is `338.60068539`, `net_pnl_usdt` is `-1307.99088539`

#### Scenario: Several fills
- **WHEN** the entry has executions 1 @ 100 and 3 @ 104
- **THEN** `entry_avg_price` is `103`, `entry_qty` is `4` and `entry_fill_count` is `2`

#### Scenario: Plan missing
- **WHEN** no `entry_package_applied` of the cycle is stored
- **THEN** plan fields, `risk_usdt`, `r_multiple` and both slippage fields are null and the other fields are filled

#### Scenario: Closed by Runtime
- **WHEN** `close_reason` is `runtime_signal`
- **THEN** `exit_slippage_pct` is null

### Requirement: Closed-trades read API

The service SHALL answer `GET /v1/closed-trades` with optional `strategy_instance_id`, `from_closed_ms`, `to_closed_ms` (inclusive bounds on `closed_at_ms`), `status` (`complete` or `incomplete`) and `limit` (≥ 1), returning `{ "trades": [...], "truncated": bool }` ordered by `closed_at_ms` then `close_event_id`, and `GET /v1/closed-trades/{strategy_instance_id}/{trade_cycle_id}` returning one trade or `404`. Each trade SHALL be the stored row with decimals as strings, including `status`, `attempts`, `last_attempt_at_ms` and `last_error`. Invalid parameters SHALL return `400`. Reads SHALL NOT change any row.

#### Scenario: Trades of one strategy in a period
- **WHEN** a client asks for `strategy_instance_id=S&from_closed_ms=A&to_closed_ms=B`
- **THEN** only rows of S with `A <= closed_at_ms <= B` are returned, oldest first

#### Scenario: Incomplete trade explains itself
- **WHEN** a client reads an `incomplete` trade
- **THEN** the answer shows `status` `incomplete`, `attempts` and `last_error`
