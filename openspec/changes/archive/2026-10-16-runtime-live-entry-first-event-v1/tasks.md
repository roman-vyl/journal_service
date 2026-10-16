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

- [x] 2.1 Compose service `journal-service`: read-only bind `BBB_DATA_ROOT/strategy-runtime/journal`, read-write bind `BBB_DATA_ROOT/journal`, health check, no dependency from any trading service on it. (bbb_stack branch `claude/project-thread-kyrwe7`, no PR yet.)
- [x] 2.2 Image pin written to `deploy/images.env` on that branch (journal_service `42c51e2`); the pin PR is opened separately.

## 3. Verification on the Mac (on owner's word only)

Result, 2026-10-16: smoke passed.

- [x] 3.1 ABI ran in dry-run (`ABI_DRY_RUN=true`, live trading off, testnet, no Bybit key); the 32 `loadtest-*` specs set to `enabled: false`.
- [x] 3.2 One strategy enabled (`journal-smoke-eth-ema500`, ETHUSDT.P 5m); three real confirmed 5m bars (17:35, 17:40, 17:45 UTC) arrived through the MDS webhook, no manual webhooks.
- [x] 3.3 `events` holds three `live_entry_evaluated` rows for that `strategy_instance_id` with three consecutive `bar_open_time_ms`; `desired_entry` is `null` in all three (Engine returned no entry). Journal counters: stored 3, malformed 0; cursor at end of `runtime.jsonl`.
