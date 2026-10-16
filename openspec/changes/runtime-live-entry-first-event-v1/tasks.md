## 1. Central Journal

- [x] 1.1 Skeleton: Python package, config (`JOURNAL_RUNTIME_SOURCE_PATH`, `JOURNAL_DB_PATH`, poll interval, port), Dockerfile.
- [x] 1.2 SQLite schema and migration on start (E3), WAL.
- [x] 1.3 Tailer with persisted cursor, complete lines only, file identity change and shrink handling (E2).
- [x] 1.4 Accept `live_entry_evaluated` with `schema_version >= 2` that passes the minimal indexable contract (design E1); do not validate `desired_entry`; extract index columns; keep the line as `body`; skip and count others; log malformed lines.
- [x] 1.5 Idempotent batch insert + cursor update in one transaction.
- [x] 1.6 `GET /health` (E4).
- [x] 1.7 Tests: null and non-null events; structurally invalid events (missing `strategy_instance_id`, missing or non-integer `bar_open_time_ms`, empty payload) skipped and counted; meaningless `desired_entry` stored unchanged; envelope `source` never reaches the `source` column; partial last line; restart resumes from cursor; duplicate `event_id` ignored; file replaced or truncated; unrelated events skipped.

## 2. bbb_stack (separate follow-up step, not part of the first code commit)

First prove locally: a ready `runtime.jsonl` → tailer → `events` → restart → no loss, no duplicates. Only then wire the service into the stack.

- [ ] 2.1 Compose service `journal-service`: read-only bind `BBB_DATA_ROOT/strategy-runtime/journal`, read-write bind `BBB_DATA_ROOT/journal`, health check, no dependency from any trading service on it.
- [ ] 2.2 Image pin in a separate PR after the service image exists.

## 3. Verification on the Mac (on owner's word only)

- [ ] 3.1 Confirm ABI runs dry-run or demo; handle the enabled `loadtest-*` specs as the owner decides.
- [ ] 3.2 Enable one strategy, wait for three real 5m bars.
- [ ] 3.3 `SELECT` from `events` where `event_type = 'live_entry_evaluated'` and that `strategy_instance_id`: three rows with three consecutive `bar_open_time_ms`, `body` equal to the lines in `runtime.jsonl`; `desired_entry` is `null` in a row whenever Engine returned no entry.
- [ ] 3.4 Stop the service during a bar, start it again: no gap, no duplicate.
