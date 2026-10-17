## Context

Facts from the code on `main` (5a366f2) and from Runtime `main` (01d62ef):

- `events` already has nullable `trade_cycle_id` and `bar_open_time_ms`; `storage.py` writes whatever `EventRow` holds.
- `parse_line` skips every `event_type` other than `live_entry_evaluated`, and requires `payload.bar_open_time_ms`.
- The Runtime line is `{event_type: "entry_package_applied", schema_version: 2, strategy_instance_id, event_id, occurred_at, payload: {trade_cycle_id, trigger_price, stop_loss, take_profit, quantity}}`. It has no bar.
- The read API filters and orders by `bar_open_time_ms`, and does not return `trade_cycle_id`.

## Decisions

### D1. Same structural contract, one more type

Accept `entry_package_applied` with `schema_version >= 2`, requiring non-empty `event_id`, `occurred_at`, `strategy_instance_id` and `payload.trade_cycle_id` (strings), and a `payload` object. Malformed lines are counted and skipped as today. The four values are not validated or interpreted; the line is stored unchanged as `body`.

### D2. Columns

`trade_cycle_id` = `payload.trade_cycle_id`. `bar_open_time_ms` = null: the event has no bar and the Central Journal does not derive one. `EventRow.bar_open_time_ms` becomes optional; `live_entry_evaluated` keeps requiring it.

### D3. Known effect on the read API (not changed here)

`GET /v1/events` with `from_bar_ms` or `to_bar_ms` does not return these events (null bar). Without a range they are returned first, because SQLite orders null first. They are reachable by `event_type=entry_package_applied`. Returning `trade_cycle_id` and querying by cycle is a separate step on the owner's word.

## Risks / Trade-offs

Rows stored before this change are unaffected. Existing lines of this type that were already skipped are not re-read; the cursor stays where it is, so only lines appended after the deploy are ingested. Re-reading the file from the start would be a separate, explicit step.
