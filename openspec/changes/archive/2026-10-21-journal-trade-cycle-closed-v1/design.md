## Context

Facts from `journal_service` main (d3efbea) and Runtime (73d7acf):

- `events` has nullable `trade_cycle_id` and `bar_open_time_ms` and the index `events_instance_cycle (strategy_instance_id, trade_cycle_id)` (`storage.py:15-31`).
- `parse_line` accepts only `live_entry_evaluated` and `entry_package_applied` (`parser.py:16`) and treats a non-integer `payload.bar_open_time_ms` as malformed (`parser.py:87-89`).
- The Runtime line is `{event_type: "trade_cycle_closed", schema_version: 2, strategy_instance_id, event_id, occurred_at, payload: {trade_cycle_id, bar_open_time_ms, reason, order_id, order_link_id, parent_order_link_id}}`.
  - `occurred_at` is the UTC wall-clock time of writing the line (`datetime.now(UTC).isoformat()`), written only after the closed state was saved.
  - `bar_open_time_ms` is the committed bar being processed, or null when the pending-close resolver closed the cycle outside bar processing.
  - `reason` is `stop_loss`, `take_profit` or `runtime_signal`.
- `GET /v1/events` filters by instance, `event_type` and bar range, orders by `bar_open_time_ms, occurred_at, event_id`, and does not return `trade_cycle_id` (`query.py:30-78`).

## Decisions

### D1. Meaning

`trade_cycle_closed` means Runtime saved a closure of the cycle that ABI proved. `occurred_at` is the moment Runtime recorded that closure, not the exchange execution time of the closing order, and the Journal does not present it as such. Exchange execution facts (time, price, quantity) are a later, separate source.

### D2. Structural contract

Accept `trade_cycle_closed` with `schema_version >= 2`, requiring non-empty strings `event_id`, `occurred_at`, `strategy_instance_id` and `payload.trade_cycle_id`, a `payload` object, and `payload.bar_open_time_ms` that is an integer or null. Missing or of another type is malformed. `reason`, `order_id`, `order_link_id` and `parent_order_link_id` are neither validated nor interpreted; the line is stored unchanged as `body`. The other two types keep requiring an integer bar.

### D3. Columns

| Field | Stored in |
|---|---|
| `strategy_instance_id` | `events.strategy_instance_id` |
| `payload.trade_cycle_id` | `events.trade_cycle_id` |
| `payload.bar_open_time_ms` (int or null) | `events.bar_open_time_ms` |
| `reason`, `order_id`, `order_link_id`, `parent_order_link_id` | `events.body` only |

### D4. Query

- `trade_cycle_id` is an optional exact-match filter combined with the existing ones; with `strategy_instance_id` it uses `events_instance_cycle`.
- Every returned event carries `trade_cycle_id` (null when the row has none).
- Ordering is unchanged. A row with a null bar sorts before rows with a bar (SQLite NULL order), and any `from_bar_ms` or `to_bar_ms` excludes it, because it has no bar to compare. Without bar bounds it is returned.
- Consequence: a bar-window query does not return a closure written by the pending-close resolver; a query by `trade_cycle_id` does. That path only runs after a lost Close response, so it is rare. The Journal does not invent a bar for it.

## Risks / Trade-offs

- Lines of this type already in `runtime.jsonl` before the deploy were skipped and are not re-read; the cursor stays where it is.
- Runtime finds a closure while processing the next committed bar, so `occurred_at` can be up to one 5m bar later than the exchange event. Accepted for V1 (D1).
