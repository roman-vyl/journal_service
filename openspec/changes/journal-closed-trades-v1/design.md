## Context

- Runtime events already stored in `events` (source `runtime`): `entry_package_applied` (`trigger_price`, `stop_loss`, `take_profit`, `quantity`), `protection_applied` (`confirmed_protection.stop_price`, `confirmed_protection.take_price`), `trade_cycle_opened`, `trade_cycle_closed` (`reason` ∈ `stop_loss` | `take_profit` | `runtime_signal`, `order_id` of the closing order). The dashboard Close button is journaled as `runtime_signal` too.
- ABI per-cycle route returns `orders[]`, each `{ link: { role: entry | close | stop_loss | take_profit, order_id, ... }, events: [...], truncated }`. An execution event has `fact_kind = execution`, `exec_type`, `exchange_time_ms` and `raw` with Bybit strings `execPrice`, `execQty`, `execFee`, `execTime`, `side`, `symbol`. An order event has `fact_kind = order_state`, `order_status`, `raw.side`.

## Decisions

### D1. Two entities, one process

The collector (tailer + `events`) is unchanged. A separate builder thread owns `closed_trades`. The builder reads `events` and ABI; it never writes `events`. If the builder fails or ABI is down, ingestion of Runtime events continues.

### D2. What becomes a row

Every stored `trade_cycle_closed` gives one row keyed by (`strategy_instance_id`, `trade_cycle_id`). A second `trade_cycle_closed` for the same pair is ignored. Rows are also created at start-up for closures already stored (backfill), so trades closed before this change appear too. Cycles that ended without a fill (`entry_cycle_ended`) never get a row.

### D3. Executions taken from ABI

Only `fact_kind = execution` with `exec_type = Trade` count. Entry executions: orders whose link role is `entry` (all generations). Exit executions: orders whose role is `close`, `stop_loss` or `take_profit`. Funding and unlinked executions are ignored.

### D4. Completion rule (no volume reconciliation)

A row is `complete` when ABI returns at least one entry execution and the closing order named by `trade_cycle_closed.payload.order_id` has an order state `Filled` and at least one execution. Otherwise the row stays `incomplete` and is retried every `JOURNAL_TRADES_RETRY_S` seconds (default 60), with no deadline. A `complete` row is never recomputed or changed.

### D5. Formulas

All arithmetic in decimal (Python `Decimal`), stored as decimal text, no float. `s = +1` for long (entry side `Buy`), `-1` for short (`Sell`).

| Field | Formula |
|---|---|
| `entry_avg_price` | Σ(execPrice·execQty) / Σ execQty over entry executions |
| `exit_avg_price` | same over exit executions |
| `entry_qty`, `exit_qty` | Σ execQty |
| `entry_notional_usdt` | `entry_avg_price · entry_qty` |
| `entry_fill_count`, `exit_fill_count` | number of executions |
| `entry_fee_usdt`, `exit_fee_usdt` | Σ execFee (Bybit sign: positive = paid, negative = rebate) |
| `gross_pnl_usdt` | `s · (exit_avg_price − entry_avg_price) · exit_qty` |
| `fees_usdt` | `entry_fee_usdt + exit_fee_usdt` |
| `net_pnl_usdt` | `gross_pnl_usdt − fees_usdt` |
| `price_return_pct` | `s · (exit_avg_price / entry_avg_price − 1) · 100` |
| `net_return_pct` | `net_pnl_usdt / entry_notional_usdt · 100` |
| `risk_usdt` | `|entry_avg_price − planned_initial_stop| · exit_qty` |
| `r_multiple` | `net_pnl_usdt / risk_usdt` (null if risk is 0 or the plan is missing) |
| `entry_slippage_pct` | `s · (entry_avg_price − planned_entry_price) / planned_entry_price · 100`; positive = worse than plan |
| `exit_slippage_pct` | `s · (planned_exit_price − exit_avg_price) / planned_exit_price · 100`; positive = worse; `planned_exit_price` = last stop for `stop_loss`, last take for `take_profit`, null for `runtime_signal` |
| `opened_at_ms` / `closed_at_ms` | first entry `execTime` / last exit `execTime` |
| `duration_ms` | `closed_at_ms − opened_at_ms` |

Plan values: `planned_entry_price`, `planned_initial_stop`, `planned_initial_take` from the last `entry_package_applied` of the cycle; `last_stop`, `last_take` from the last `protection_applied.confirmed_protection` of the cycle, else equal to the initial ones. A missing input gives null in every field that needs it, never a guess.

### D6. Table

```
closed_trades (
  strategy_instance_id TEXT NOT NULL,
  trade_cycle_id       TEXT NOT NULL,
  status               TEXT NOT NULL,          -- incomplete | complete
  close_event_id       TEXT NOT NULL,          -- Runtime trade_cycle_closed event_id
  close_reason         TEXT NOT NULL,
  closing_order_id     TEXT NOT NULL,
  symbol               TEXT, side TEXT,        -- long | short
  opened_at_ms INTEGER, closed_at_ms INTEGER, duration_ms INTEGER,
  entry_avg_price TEXT, entry_qty TEXT, entry_notional_usdt TEXT, entry_fill_count INTEGER, entry_fee_usdt TEXT,
  exit_avg_price TEXT, exit_qty TEXT, exit_fill_count INTEGER, exit_fee_usdt TEXT,
  planned_entry_price TEXT, planned_initial_stop TEXT, planned_initial_take TEXT, last_stop TEXT, last_take TEXT,
  gross_pnl_usdt TEXT, fees_usdt TEXT, net_pnl_usdt TEXT, price_return_pct TEXT, net_return_pct TEXT,
  risk_usdt TEXT, r_multiple TEXT, entry_slippage_pct TEXT, exit_slippage_pct TEXT,
  attempts INTEGER NOT NULL, last_attempt_at_ms INTEGER, last_error TEXT,
  created_at_ms INTEGER NOT NULL, completed_at_ms INTEGER,
  PRIMARY KEY (strategy_instance_id, trade_cycle_id)
)
INDEX closed_trades_closed_at (closed_at_ms), INDEX closed_trades_status (status)
```

Migration 1 → 2 adds only this table in one transaction; `user_version` 2.

### D7. ABI client

`GET {JOURNAL_ABI_BASE_URL}/v1/strategy-instances/{sid}/trade-cycles/{cid}/exchange-journal`, timeout 5 s, path values percent-encoded. `200` → use; `503`, `5xx`, timeout, connection error → stay `incomplete`, keep `last_error`; `truncated: true` anywhere → stay `incomplete` with `last_error = abi_truncated`. No other ABI route, no write, no Bybit call.

### D8. Read API

- `GET /v1/closed-trades?strategy_instance_id=&from_closed_ms=&to_closed_ms=&status=&limit=` → `{ "trades": [...], "truncated": bool }`, ordered by `closed_at_ms` then `close_event_id`; incomplete rows without `closed_at_ms` are ordered by `created_at_ms` and returned only without time bounds.
- `GET /v1/closed-trades/{strategy_instance_id}/{trade_cycle_id}` → one row or `404`.
- Each trade is the row as stored, decimals as strings; `attempts`, `last_attempt_at_ms` and `last_error` included so an incomplete row explains itself.

## Risks / Trade-offs

- If ABI's journal never gets the exit (e.g. data lost and not refillable), the row stays `incomplete` forever and is visible as such; no silent drop.
- `gross_pnl` uses `exit_qty`; with a partial exit and no reconciliation the number covers only what was exited. Accepted for this stage.
- Without the ABI base URL in bbb_stack the builder only creates `incomplete` rows; wiring is a separate change.
