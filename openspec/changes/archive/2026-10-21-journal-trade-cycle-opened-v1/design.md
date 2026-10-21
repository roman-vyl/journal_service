## Context

Facts from `journal_service` main (7e34bf5) and Runtime main (22e010f):

- `parse_line` accepts `live_entry_evaluated`, `entry_package_applied` and `trade_cycle_closed` (`parser.py:17-18`); cycle types require a non-empty string `payload.trade_cycle_id` (`CYCLE_EVENT_TYPES`, `parser.py:21`); only `trade_cycle_closed` may have a null bar (`NULLABLE_BAR_EVENT_TYPES`, `parser.py:23`).
- `events` has nullable `trade_cycle_id` and `bar_open_time_ms` and the index `events_instance_cycle` (`storage.py:15-31`). `GET /v1/events` already filters by `trade_cycle_id` and returns it on every event (`query.py:53-77`).
- The Runtime line is `{event_type: "trade_cycle_opened", schema_version: 2, strategy_instance_id, event_id, occurred_at, payload: {trade_cycle_id, bar_open_time_ms, first_fill_at_ms, average_entry_price, entry_order_link_id, entry_order_id}}`.
  - Written once per cycle, only on the transition to an open position, after the durable save; best-effort (a failed write is counted, never raised).
  - `bar_open_time_ms` is the committed bar being processed, or null when the uncertain-exchange-state resolver confirmed the fill during recovery.
  - `average_entry_price` is the value at observation time (a partial fill counts), not a final price; `entry_order_id` may be null.

## Decisions

### D1. Meaning

`trade_cycle_opened` means Runtime saved the first confirmed fill of the cycle's entry. `occurred_at` is when Runtime recorded it; `payload.first_fill_at_ms` is the exchange time Runtime received from ABI. The Journal presents neither more than that and does not decide whether the position is still open.

### D2. Structural contract

Same rule as `trade_cycle_closed`: `schema_version >= 2`, non-empty strings `event_id`, `occurred_at`, `strategy_instance_id` and `payload.trade_cycle_id`, a `payload` object, `payload.bar_open_time_ms` integer or null. Missing or of another type is malformed. `first_fill_at_ms`, `average_entry_price`, `entry_order_link_id` and `entry_order_id` are neither validated nor interpreted. The other types keep their rules.

### D3. Columns

| Field | Stored in |
|---|---|
| `strategy_instance_id` | `events.strategy_instance_id` |
| `payload.trade_cycle_id` | `events.trade_cycle_id` |
| `payload.bar_open_time_ms` (int or null) | `events.bar_open_time_ms` |
| `first_fill_at_ms`, `average_entry_price`, `entry_order_link_id`, `entry_order_id` | `events.body` only |

### D4. Query

No change. A query by `trade_cycle_id` returns the cycle's `entry_package_applied`, `trade_cycle_opened` and `trade_cycle_closed`. A null-bar row (recovery) sorts first and is excluded by any bar bound, as for `trade_cycle_closed`.

## Risks / Trade-offs

- Lines of this type already in `runtime.jsonl` before the deploy were skipped and are not re-read; the cursor stays where it is. Runtime 22e010f is not deployed yet, so none exist today.
- Because the write is best-effort, a cycle can lack `trade_cycle_opened`; the Journal infers nothing from its absence.
