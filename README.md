# journal_service

BBB Central Journal: an indexer of facts that trading services publish about
themselves. Each service writes self-contained events to its own append-only
processing journal (Strategy Runtime: what Engine answered, for which strategy and
bar; later ABI: what was sent, what Bybit confirmed, fills, cancels, protection).
The Central Journal reads those files, stores the events once in its own SQLite
and, later, answers queries such as "events of strategy X between A and B".

It never interprets events, never reconstructs them from internal state snapshots,
never makes trading decisions, and never calls Strategy Engine, Strategy Runtime,
ABI or Market Data Service. No trading service depends on it.

Status: Runtime `live_entry_evaluated` ingest, `GET /health` and the read API below.
bbb_stack wiring is a separate later step.

Run locally:

```bash
pip install -e '.[dev]'
JOURNAL_RUNTIME_SOURCE_PATH=/path/to/runtime.jsonl \
JOURNAL_DB_PATH=/path/to/journal/journal.sqlite3 \
journal-service            # optional: JOURNAL_POLL_INTERVAL_S, JOURNAL_BATCH_SIZE, JOURNAL_HOST, JOURNAL_PORT (8097)
```

Read API (read-only, local network, no auth; `body` is the stored line parsed, unchanged):

```bash
curl 'http://127.0.0.1:8097/v1/events?strategy_instance_id=<id>&from_bar_ms=<ms>&to_bar_ms=<ms>'
curl 'http://127.0.0.1:8097/v1/strategy-instances'
```

`/v1/events` returns `{"events": [...], "truncated": bool}` ordered by bar, `occurred_at`, `event_id`
(bounds inclusive; without `limit` every event of the range is returned, `truncated` is true only when an optional `limit` cut the answer; invalid input is HTTP 400). A bar with no
stored event is absent from the answer; an event with `payload.desired_entry = null` means
"evaluated, no signal".

Checks: `ruff check .`, `ruff format --check .`, `mypy`, `pytest`.

- `openspec/changes/journal-service-foundation-v1`: purpose, boundaries, stack.
- `openspec/changes/runtime-live-entry-first-event-v1`: the first end-to-end event,
  Runtime `live_entry_evaluated` (including `desired_entry = null`).
  Producer side: `strategy_runtime` change `runtime-desired-entry-journal-v1`.
