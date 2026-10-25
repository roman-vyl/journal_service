## Context

Facts from `journal_service` main (d7c0b7b) and Runtime main (ad0d418):

- `parse_line` accepts the types in `INGESTED_EVENT_TYPES`. It reads `trade_cycle_id` only for the types in `CYCLE_EVENT_TYPES`, and allows a null bar only for the types in `NULLABLE_BAR_EVENT_TYPES` (`parser.py:15-40`). Any other type is skipped and counted.
- Runtime writes the line through `JsonlProcessingJournal.entry_package_declined` (`jsonl_adapter.py:180-201`). The line has this shape:
  `{event_type: "entry_package_declined", schema_version: 2, severity: "warning", source, strategy_instance_id, event_id, occurred_at, payload: {trade_cycle_id, bar_open_time_ms, risk_multiplier, decline_reason, decline_message}, diagnostics: {}}`.
  - Runtime writes it only for a declined APPLY on a committed bar, so `bar_open_time_ms` is always an integer.
  - `trade_cycle_id` is the id Runtime minted for the attempt. No trade cycle is established under it.
  - `decline_reason` is opaque to Runtime: a string matching `[a-z][a-z0-9_]{0,63}`. ABI d860511 sends `insufficient_balance_for_minimum_quantity`, `quantity_above_exchange_maximum`, `invalid_stop_distance` or `margin_mode_not_supported`. `decline_message` is free text from ABI.

## Decisions

### D1. Meaning

`entry_package_declined` means Runtime received ABI's explicit refusal of an entry and ended the attempt without a trade cycle and without recovery. The Journal stores this fact. It does not turn it into a cycle status and does not draw any conclusion from it.

### D2. Structural contract

Accept `entry_package_declined` with `schema_version >= 2`. The line must have:
- non-empty strings `event_id`, `occurred_at`, `strategy_instance_id` and `payload.trade_cycle_id`;
- a `payload` object;
- an integer `payload.bar_open_time_ms`.

A missing field or a field of another type makes the line malformed, and a null bar counts as malformed too. `risk_multiplier`, `decline_reason` and `decline_message` are neither required nor validated. The line is stored unchanged as `body`.

### D3. Columns

| Field | Stored in |
|---|---|
| `strategy_instance_id` | `events.strategy_instance_id` |
| `payload.trade_cycle_id` | `events.trade_cycle_id` |
| `payload.bar_open_time_ms` | `events.bar_open_time_ms` |
| `risk_multiplier`, `decline_reason`, `decline_message` | `events.body` only |

### D4. Query

There is no change. A bar-range query of the instance returns the declined row on its bar, next to `live_entry_evaluated` of the same bar. A query by `trade_cycle_id` returns only this row, because no other event carries that id.

## Risks / Trade-offs

- Declined lines written to `runtime.jsonl` before this change is deployed were already skipped and are not re-read, because the cursor has moved past them. A full re-ingest is out of scope.
