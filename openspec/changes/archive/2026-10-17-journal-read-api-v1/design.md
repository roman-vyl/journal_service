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
in milliseconds. `limit` is optional and has no default and no maximum: without it the answer holds every stored event of the range. Any invalid value is HTTP
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
`truncated` is false unless the client passed `limit` and more matching rows exist (the service then reads `limit + 1` rows). `body` is the stored text parsed, never
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

## Stored-event contract (what the database holds and where each field comes from)

Database: one SQLite file (`journal.sqlite3`, WAL), table `events`, primary key
(`source`, `event_id`). Columns: `source` (always `runtime`), `event_id`, `event_type`,
`schema_version`, `occurred_at` (ISO text), `strategy_instance_id`, `trade_cycle_id` (null for
live-entry events), `bar_open_time_ms` (INTEGER, copied from `payload.bar_open_time_ms`),
`body` (the Runtime journal line as TEXT, unchanged), `ingested_at_ms`. Indexes:
(`strategy_instance_id`, `bar_open_time_ms`), (`strategy_instance_id`, `occurred_at`),
(`strategy_instance_id`, `trade_cycle_id`), (`event_type`, `occurred_at`). Table `ingest_cursor`
holds the file identity and byte offset. This change adds no table, column or index.

Producer: Runtime writes one `live_entry_evaluated` line per evaluated live-entry bar
(`strategy_runtime/utility/processing_journal/jsonl_adapter.py`, `live_entry_evaluated`). The
`desired_entry` object is the Engine live-entry answer after Runtime's ABI codec
(`runtime/abi/entry_package_codec.py`), which carries prices as decimal strings.

| Need | Column or path in `body` | Type | Written by |
|---|---|---|---|
| strategy | `strategy_instance_id` (column and `body.strategy_instance_id`) | text | Runtime |
| bar | `bar_open_time_ms` (column and `body.payload.bar_open_time_ms`) | integer, ms | Runtime |
| market | `body.payload.instrument`, `body.payload.timeframe` | text | Runtime |
| no signal | `body.payload.desired_entry` is `null` | null | Runtime |
| side | `body.payload.desired_entry.side` | text | Engine via Runtime |
| desired entry | `body.payload.desired_entry.planned_entry_price` | decimal text | Engine via Runtime |
| initial stop | `body.payload.desired_entry.initial_stop_price` | decimal text | Engine via Runtime |
| initial take | `body.payload.desired_entry.initial_take_price` | decimal text | Engine via Runtime |
| plan bar | `body.payload.desired_entry.source_plan_bar_open_time_ms` | integer, ms | Engine via Runtime |

The journal service does not read or convert any `desired_entry` field; readers take them from
`body` as shown. A bar with no stored event is "not evaluated", which differs from a stored
event with `desired_entry = null` ("evaluated, no signal").

## Risks

- A wide range returns every event of the range (about 8640 bars for 30 days of 5m, more if a
  bar is evaluated twice); V1 accepts this and the client may pass `limit` to bound it.
- `body` can be large if Runtime later adds fields; the response is the stored line as is.
