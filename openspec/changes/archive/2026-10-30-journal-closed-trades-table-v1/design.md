## Table `closed_trades`

Key: (`strategy_instance_id`, `trade_cycle_id`). Prices, quantities and money are decimal text (exactly as computed in decimal arithmetic, never float). Times are UTC milliseconds. A field whose input is missing is null, never an estimate.

`s` below is `+1` for a long and `-1` for a short. "Entry executions" are the Bybit `Trade` executions of the cycle's entry orders; "exit executions" are those of its close, stop-loss and take-profit orders (from ABI's exchange journal). Funding is not counted.

### Block 1. What trade

| Column | Meaning | Source |
|---|---|---|
| `strategy_instance_id` | strategy | Runtime |
| `trade_cycle_id` | cycle | Runtime |
| `symbol` | coin, e.g. `BTCUSDT` | ABI |
| `side` | `long` or `short` (entry order side `Buy` / `Sell`) | ABI |
| `close_reason` | `stop_loss`, `take_profit` or `runtime_signal` (dashboard Close button is `runtime_signal` too) | Runtime `trade_cycle_closed` |
| `close_event_id` | id of that Runtime event | Runtime |
| `closing_order_id` | Bybit order that closed the trade | Runtime `trade_cycle_closed` |
| `status` | `incomplete` or `complete` (filled by a later change) | Journal |

### Block 2. Entry, fact

| Column | Meaning / formula | Source |
|---|---|---|
| `opened_at_ms` | time of the first entry execution | ABI |
| `entry_avg_price` | Σ(price·qty) / Σ qty over entry executions | ABI |
| `entry_qty` | Σ qty, coins | ABI |
| `entry_notional_usdt` | `entry_avg_price · entry_qty` | computed |
| `entry_fill_count` | number of entry executions | ABI |
| `entry_fee_usdt` | Σ fee (positive = paid, negative = rebate) | ABI |

### Block 3. Exit, fact

| Column | Meaning / formula | Source |
|---|---|---|
| `closed_at_ms` | time of the last exit execution | ABI |
| `exit_avg_price` | Σ(price·qty) / Σ qty over exit executions | ABI |
| `exit_qty` | Σ qty, coins | ABI |
| `exit_fill_count` | number of exit executions | ABI |
| `exit_fee_usdt` | Σ fee | ABI |
| `duration_ms` | `closed_at_ms − opened_at_ms` | computed |

### Block 4. Plan

| Column | Meaning | Source |
|---|---|---|
| `planned_entry_price` | `trigger_price` of the cycle's last `entry_package_applied` | Runtime |
| `planned_initial_stop` | `stop_loss` of the same event | Runtime |
| `planned_initial_take` | `take_profit` of the same event | Runtime |
| `last_stop` | `confirmed_protection.stop_price` of the cycle's last `protection_applied`, else `planned_initial_stop` | Runtime |
| `last_take` | same for take, else `planned_initial_take` | Runtime |

### Block 5. Result

| Column | Formula |
|---|---|
| `gross_pnl_usdt` | `s · (exit_avg_price − entry_avg_price) · exit_qty` |
| `fees_usdt` | `entry_fee_usdt + exit_fee_usdt` |
| `net_pnl_usdt` | `gross_pnl_usdt − fees_usdt` |
| `price_return_pct` | `s · (exit_avg_price / entry_avg_price − 1) · 100` |
| `net_return_pct` | `net_pnl_usdt / entry_notional_usdt · 100` |
| `risk_usdt` | `|entry_avg_price − planned_initial_stop| · exit_qty` |
| `r_multiple` | `net_pnl_usdt / risk_usdt`; null if risk is 0 or plan missing |
| `entry_slippage_pct` | `s · (entry_avg_price − planned_entry_price) / planned_entry_price · 100`; positive = worse than plan |
| `exit_slippage_pct` | `s · (planned_exit − exit_avg_price) / planned_exit · 100`; `planned_exit` = `last_stop` for `stop_loss`, `last_take` for `take_profit`, null for `runtime_signal`; positive = worse |

### Block 6. Service columns

`created_at_ms`, `completed_at_ms`, `attempts`, `last_attempt_at_ms`, `last_error`: how and when the row was assembled (used by the later change that fills the table).

### Check on real data

Demo trade of 2026-10-25 (BTC short, closed by stop, cycle with entry order `abi-ep-e94a570a5f50ca2340d9`): entry 80496.1 × 3.818, fee 169.03376039; exit 80750 × 3.818, fee 169.566925 → `gross_pnl_usdt` −969.3902, `fees_usdt` 338.60068539, `net_pnl_usdt` −1307.99088539 (Bybit showed −969 price, −339 fees, −1308).

### Migration

Schema 1 → 2 in one transaction: `CREATE TABLE closed_trades (...)` with primary key (`strategy_instance_id`, `trade_cycle_id`), indexes on `closed_at_ms` and on `status`, then `user_version = 2`. Version 2 opens unchanged; other versions refuse to start, as today.
