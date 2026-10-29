## Context

- `events` (source `runtime`) already holds per cycle: `entry_package_applied` (`trigger_price`, `stop_loss`, `take_profit`), `protection_applied` (`confirmed_protection.stop_price`, `.take_price`), `trade_cycle_closed` (`reason`, `order_id` of the closing order).
- ABI `GET /v1/strategy-instances/{sid}/trade-cycles/{cid}/exchange-journal` returns `orders[]` of `{ link: { role, order_id, ... }, events: [...], truncated }` plus a top-level `truncated`. Roles: `entry`, `close`, `stop_loss`, `take_profit`. An execution event: `fact_kind: "execution"`, `exec_type`, `order_id`, `raw` with Bybit strings `execPrice`, `execQty`, `execFee`, `execTime`, `side`, `symbol`. An order event: `fact_kind: "order_state"`, `order_status`, `raw.side`.
- Columns and formulas: `journal-closed-trades-table-v1` design.md (unchanged here).

## Decisions

### D1. One builder thread, one pass per interval

Every `JOURNAL_TRADES_INTERVAL_S` seconds (default 60) the builder runs one pass: detect, then assemble every `incomplete` row. It has its own read-write connection; SQLite WAL lets the tailer keep writing. Any exception in a pass is logged and the next pass runs; the tailer thread is never affected.

### D2. Detection

```
SELECT first trade_cycle_closed per (strategy_instance_id, trade_cycle_id)
WHERE no closed_trades row exists for the pair
```
For each pair: `INSERT OR IGNORE` a row with `status = 'incomplete'`, `close_reason = payload.reason`, `close_event_id = event_id`, `closing_order_id = payload.order_id`, `attempts = 0`, `created_at_ms = now`. Closures stored before this change are found the same way.

### D3. Assembly of one row

1. Runtime part from `events` of this pair: last `entry_package_applied` → planned entry/stop/take; last `protection_applied` → last stop/take (else initial).
2. ABI part: one `GET` (timeout 5 s, path values percent-encoded). Executions counted: `fact_kind = execution` and `exec_type = Trade`. Entry = orders with role `entry`; exit = roles `close`, `stop_loss`, `take_profit`. `symbol` and `side` from the entry order (`Buy` → `long`, `Sell` → `short`).
3. Completion: at least one entry execution AND the order with `order_id = closing_order_id` has an `order_state` with `order_status = Filled` AND at least one execution. Then every column is computed with the table change's formulas (Python `Decimal`, stored with `str()`), `status = complete`, `completed_at_ms = now`, in one transaction guarded by `WHERE status = 'incomplete'`.
4. Otherwise: only `attempts + 1`, `last_attempt_at_ms`, `last_error` change. `last_error` values: `abi_not_configured`, `abi_unavailable` (connection error or timeout), `abi_http_<code>`, `abi_bad_response`, `abi_truncated`, `no_entry_execution`, `closing_order_not_filled`.

### D4. Retry

Every pass retries every `incomplete` row; no deadline and no back-off (rows are few; one GET each per minute). A `complete` row is never selected again.

### D5. Health

`/health` gains `closed_trades: { abi_configured, complete, incomplete, last_pass_at_ms, last_error }`, where `last_error` is the error of the most recent failed attempt or null. Health stays `200` when ABI is down.

## Risks / Trade-offs

- A trade whose exit never reaches ABI stays `incomplete` forever and shows its reason; nothing is dropped silently.
- With several exit orders (e.g. partial SL then close) completion waits only for the order Runtime named as closing; earlier exit fills are already in ABI by then.
- Until bbb_stack passes `JOURNAL_ABI_BASE_URL`, rows stay `incomplete` with `abi_not_configured`.
