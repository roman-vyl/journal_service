## Context

Facts from the code on `main` (5a366f2) and from Runtime (strategy_runtime #23, e750e5f):

- `events` already has nullable `trade_cycle_id` and `bar_open_time_ms`; `storage.py` writes whatever `EventRow` holds.
- `parse_line` skips every `event_type` other than `live_entry_evaluated`, and requires `payload.bar_open_time_ms`.
- The Runtime line is `{event_type: "entry_package_applied", schema_version: 2, strategy_instance_id, event_id, occurred_at, payload: {trade_cycle_id, bar_open_time_ms, trigger_price, stop_loss, take_profit, quantity, order_link_id, order_id}}`. The four values and both ids may be null.
- The read API filters and orders by `bar_open_time_ms`, and does not return `trade_cycle_id`.

## Decisions

### D1. Meaning

`entry_package_applied` means ABI confirmed that the cycle's entry order was applied and Runtime recorded that confirmation. It is not proof that the Runtime state transition completed: Runtime writes the record before its own state checks. The Journal stores it as such and adds no meaning.

### D2. Same structural contract, one more type

Accept `entry_package_applied` with `schema_version >= 2`, requiring non-empty `event_id`, `occurred_at`, `strategy_instance_id` and `payload.trade_cycle_id` (strings), an integer `payload.bar_open_time_ms`, and a `payload` object. Malformed lines are counted and skipped as today. The four values and `order_link_id`/`order_id` are not validated or interpreted; the line is stored unchanged as `body`.

### D3. Columns

| Field | Stored in |
|---|---|
| `strategy_instance_id` | `events.strategy_instance_id` |
| `payload.trade_cycle_id` | `events.trade_cycle_id` |
| `payload.bar_open_time_ms` | `events.bar_open_time_ms` |
| `order_link_id`, `order_id`, four order values | `events.body` only |

### D4. Correlation

`live_entry_evaluated` and `entry_package_applied` of the same bar processing share (`strategy_instance_id`, `bar_open_time_ms`). The pair groups events of one bar processing; it is not a unique id of an evaluation. `trade_cycle_id`, `order_link_id` and `order_id` lead from the applied record to the cycle and the Bybit order. The Journal does not join or derive anything here; the read API already returns both types for a bar range.

## Risks / Trade-offs

- Lines written by Runtime #22 before #23 have no `bar_open_time_ms`; they are counted as malformed and skipped. Only a demo stack running #22 could have written them.
- Existing lines of this type that were already skipped are not re-read; the cursor stays where it is, so only lines appended after the deploy are ingested. Re-reading the file from the start would be a separate, explicit step.
