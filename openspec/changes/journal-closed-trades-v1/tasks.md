## 1. journal_service

- [ ] 1.1 `storage.py`: schema 2 migration (table `closed_trades`, two indexes); version 1 databases upgrade in place, version 2 opens unchanged, other versions refuse to start.
- [ ] 1.2 `config.py`: `JOURNAL_ABI_BASE_URL` (optional), `JOURNAL_TRADES_RETRY_S` (default 60, positive).
- [ ] 1.3 ABI client (GET per-cycle route, 5 s timeout, error classification per design D7).
- [ ] 1.4 Builder: create rows from stored `trade_cycle_closed` (including backfill), assemble per D3–D5, retry incomplete rows, never touch complete rows; own thread, failures logged, ingestion unaffected.
- [ ] 1.5 Read API `GET /v1/closed-trades` and `GET /v1/closed-trades/{sid}/{cid}`; `/health` builder block.
- [ ] 1.6 Tests: formulas on the real 6072511f short (entry 80496.1 × 3.818, SL exit 80750, fees 169.03376039 + 169.566925), long and short, partial entry, several exit fills, missing plan, ABI 503/timeout/truncated, exit not yet present then present, complete row never changes, second `trade_cycle_closed` ignored, migration from version 1.
- [ ] 1.7 README; `ruff`, `mypy`, `pytest`, `openspec validate --all --strict`.

## 2. Rollout (on owner's word only)

- [ ] 2.1 PR and merge only on the owner's word.
- [ ] 2.2 bbb_stack: give the Journal container `JOURNAL_ABI_BASE_URL` and network access to ABI (separate bbb_stack change), then deploy on «деплой».
- [ ] 2.3 Demo check: the next closed trade appears as `complete` with prices and fees equal to Bybit's.
