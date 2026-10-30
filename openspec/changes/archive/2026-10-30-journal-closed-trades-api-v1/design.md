## Context

`closed_trades` (schema 2) has one row per strategy instance and trade cycle with a position
opened, filled by the builder. Rows start `incomplete` and become `complete` once; after that
they never change. The HTTP surface is the stdlib server in `health.py` with read-only database
connections for queries (`event-query`).

## Decisions

### D1. Two endpoints

- `GET /v1/closed-trades` with optional query parameters:
  - `strategy_instance_id`: only that instance;
  - `from_closed_ms`, `to_closed_ms`: inclusive bounds on `closed_at_ms`;
  - `status`: `complete` or `incomplete`;
  - `limit`: integer, at least 1.
  Response `{"trades": [...], "truncated": bool}`.
- `GET /v1/closed-trades/{strategy_instance_id}/{trade_cycle_id}`: response
  `{"trade": {...}}` or 404 `{"error": "closed trade not found"}`. Path segments are
  percent-decoded.

### D2. Order

Ascending `closed_at_ms`, then `close_event_id`. An `incomplete` row has no `closed_at_ms`
(null) until ABI gives the exit fill, so such rows come first and are ordered by
`created_at_ms`, then `close_event_id`. With `limit` the first rows in this order are returned
and `truncated` is true only when more rows match.

### D3. A row as stored

Every column of `closed_trades` is a key of the returned object under its column name.
Decimal columns keep their stored text (e.g. `"-1307.99088539"`), integers stay integers, empty
values are `null`. The service does not round, recompute or add fields.

### D4. Period filter and incomplete rows

`from_closed_ms` / `to_closed_ms` compare `closed_at_ms`; an incomplete row whose
`closed_at_ms` is null does not match a period filter. Without a period filter incomplete rows
are listed.

### D5. Invalid requests

HTTP 400 with `{"error": "<message>"}` for: a non-integer `from_closed_ms`, `to_closed_ms` or
`limit`; `limit` below 1; `from_closed_ms` greater than `to_closed_ms`; `status` other than
`complete` or `incomplete`; an empty `strategy_instance_id`. A path under `/v1/closed-trades/`
that is not exactly two non-empty segments answers 404.

### D6. Read-only

Queries open the database read-only, as `event-query` does, and never wait for or block the
tailer or the builder.
