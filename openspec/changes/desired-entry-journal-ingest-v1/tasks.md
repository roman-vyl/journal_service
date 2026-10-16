## 1. Journal Service

- [ ] 1.1 Skeleton: Python package, config (`JOURNAL_SOURCE_PATH`, `JOURNAL_DB_PATH`, poll interval, port), Dockerfile.
- [ ] 1.2 SQLite schema and migration on start (I3), WAL.
- [ ] 1.3 Tailer with persisted cursor, complete lines only, file identity change and shrink handling (I2).
- [ ] 1.4 Parser: accept only `event_type = live_entry_evaluated` with `schema_version >= 2`; skip and count everything else; malformed lines logged, not fatal.
- [ ] 1.5 Idempotent batch insert + cursor update in one transaction.
- [ ] 1.6 `GET /health` (I4).
- [ ] 1.7 Tests: null and non-null rows; partial last line; restart resumes from cursor; duplicate `event_id` ignored; file replaced or truncated; unrelated events skipped.

## 2. bbb_stack

- [ ] 2.1 Compose service `journal-service`: read-only bind `BBB_DATA_ROOT/strategy-runtime/journal`, read-write bind `BBB_DATA_ROOT/journal`, health check, no dependency from any trading service on it.
- [ ] 2.2 Image pin in a separate PR after the service image exists.

## 3. Verification on the Mac (on owner's word only)

- [ ] 3.1 Confirm ABI runs dry-run or demo; handle the enabled `loadtest-*` specs as the owner decides.
- [ ] 3.2 Enable one strategy, wait for three real 5m bars.
- [ ] 3.3 Query SQLite: three rows for that `strategy_instance_id` with three consecutive `bar_open_time_ms`, values equal to the `live_entry_evaluated` lines in `runtime.jsonl`; a `null` row appears whenever Engine returned no entry.
- [ ] 3.4 Stop the Journal Service during a bar, start it again: no gap, no duplicate.
