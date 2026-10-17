## Context

`events` (source, event_id, event_type, schema_version, occurred_at, strategy_instance_id,
trade_cycle_id, bar_open_time_ms, body, ingested_at_ms) has indexes on
(strategy_instance_id, bar_open_time_ms) and (strategy_instance_id, occurred_at). Runtime can
journal one bar more than once (`Same bar evaluated twice` is stored as two rows). The HTTP
server is a stdlib `ThreadingHTTPServer` in `health.py`; the tailer owns the writing connection.

## Decisions

### Q1. Routes

- `GET /v1/events?strategy_instance_id=<id>[&event_type=<type>][&from_bar_ms=<int>][&to_bar_ms=<int>][&limit=<int>]`
- `GET /v1/strategy-instances`

`strategy_instance_id` is required. `event_type` defaults to no filter (only
`live_entry_evaluated` exists today). `from_bar_ms` and `to_bar_ms` are inclusive bar open times
in milliseconds. `limit` defaults to 1000 and may not exceed 5000. Any invalid value is HTTP
400 `{"error": "<message>"}`.

### Q2. Response of `/v1/events`

```json
{
  "events": [
    {
      "event_id": "...", "event_type": "live_entry_evaluated", "schema_version": 2,
      "occurred_at": "...", "strategy_instance_id": "...", "bar_open_time_ms": 0,
      "body": { "...": "the stored line parsed as JSON, unchanged" }
    }
  ],
  "truncated": false
}
```

Order: `bar_open_time_ms` ascending, then `occurred_at` ascending, then `event_id`. All rows
are returned, including several rows for one bar; choosing among them is the client's job. The
service reads `limit + 1` rows to set `truncated`. `body` is the stored text parsed, never
re-derived: the service does not look inside `payload`, so `desired_entry = null` and a
non-null entry are returned the same way.

### Q3. Response of `/v1/strategy-instances`

```json
{ "strategy_instances": [
  { "strategy_instance_id": "...", "event_count": 0,
    "first_bar_open_time_ms": 0, "last_bar_open_time_ms": 0, "last_occurred_at": "..." } ] }
```

Grouped by `strategy_instance_id` over rows with a non-null `strategy_instance_id`, sorted by
id. Counts all stored events of the instance (today all are evaluations).

### Q4. Read access

Every request opens its own short-lived SQLite connection with `PRAGMA query_only = ON`
and closes it; no request holds a transaction across a poll of the tailer. The database
stays in WAL mode so reads do not block the writer. The tailer remains the only writer, so the
"single owner" boundary is kept: the owning process serves the reads.

### Q5. Not here

No CORS, no auth (local network, as the rest of the stack; the frontend uses its dev proxy), no
caching, no pagination token beyond `from_bar_ms`/`truncated`.

## Risks

- A burst of stored events for one instance with a wide range returns up to 5000 rows; the
  client asks for a bounded window (30 days of 5m bars is 8640 bars, so the client pages by
  `from_bar_ms` when `truncated` is true).
- `body` can be large if Runtime later adds fields; the response is the stored line as is.
