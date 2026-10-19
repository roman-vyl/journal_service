## Context

Facts from `journal_service` main (6fb0ce3) and strategy_runtime `claude/runtime-open-trade-journal-v1` (PR #27):

- `parse_line` accepts `live_entry_evaluated`, `entry_package_applied`, `trade_cycle_opened`, `trade_cycle_closed` (`parser.py:14-20`); cycle types require a non-empty string `payload.trade_cycle_id` (`CYCLE_EVENT_TYPES`); only `trade_cycle_opened` and `trade_cycle_closed` may have a null bar (`NULLABLE_BAR_EVENT_TYPES`).
- `events` has nullable `trade_cycle_id` and `bar_open_time_ms`; `GET /v1/events` filters by instance, bar window and `trade_cycle_id`.
- Runtime lines (envelope `{event_type, schema_version: 2, strategy_instance_id, event_id, occurred_at, payload}`):
  - `open_trade_evaluated` payload: `instrument`, `timeframe`, `bar_open_time_ms`, `trade_cycle_id`, `side`, `desired_protection {stop_price, take_price|null}` (Engine's own text), `close_signal {active, reason, component_id, layer}`. One per bar while a position is open, before ABI is called.
  - `protection_applied` payload: `trade_cycle_id`, `bar_open_time_ms`, `requested_protection {stop_price, take_price|null}`, `confirmed_protection {stop_price, take_price|null}`, `position_quantity`, `stop_order {order_id, trigger_price}`, `take_order {order_id, trigger_price}`. One per ABI-confirmed protection change; `take_order` is present even when `take_price` is null (the far take ABI keeps on the exchange).
  - Both always carry an integer `bar_open_time_ms` (written only inside bar processing) and a non-empty `trade_cycle_id`; both are best effort.

## Decisions

### D1. Full analogy with the pre-entry pair

| Pre-entry | Open position | Journal treatment |
|---|---|---|
| `live_entry_evaluated` | `open_trade_evaluated` | accepted, bar required |
| `entry_package_applied` | `protection_applied` | accepted, bar required, cycle type |

The only difference from the pre-entry pair: `open_trade_evaluated` belongs to an existing trade cycle, so it is a cycle type (its `trade_cycle_id` is indexed), while `live_entry_evaluated` has no cycle.

### D2. Structural contract

Same rule as `entry_package_applied`: `schema_version >= 2`, non-empty strings `event_id`, `occurred_at`, `strategy_instance_id` and `payload.trade_cycle_id`, a `payload` object, an integer `payload.bar_open_time_ms`. Missing or of another type is malformed; a null bar is malformed for both. No other payload field is validated or interpreted. The other types keep their rules.

### D3. Columns

| Field | Stored in |
|---|---|
| `strategy_instance_id` | `events.strategy_instance_id` |
| `payload.trade_cycle_id` | `events.trade_cycle_id` |
| `payload.bar_open_time_ms` | `events.bar_open_time_ms` |
| everything else, incl. `position_quantity`, `desired_protection`, `close_signal`, `requested_protection`, `confirmed_protection`, `stop_order`, `take_order` | `events.body` only |

The trade quantity (`position_quantity`) is the one new field compared with the pre-entry pair; like `entry_package_applied.quantity` it stays in `body` and gets no column.

### D4. Query

No change. A query by `trade_cycle_id` returns the whole cycle in bar order: `entry_package_applied`, `trade_cycle_opened`, then per bar `open_trade_evaluated` and any `protection_applied`, then `trade_cycle_closed`. Within one bar the existing order applies.

## Risks / Trade-offs

- Volume: one `open_trade_evaluated` row per bar per open position, the same order as `live_entry_evaluated`, which already runs every bar.
- Lines written before this deploy are skipped and not re-read; none exist until Runtime PR #27 and ABI PR #25 are deployed. Deploy order: Runtime and ABI together first, then Journal (or all three together).
- Because the writes are best-effort, a bar or a protection change can lack a row; the Journal infers nothing from its absence.
