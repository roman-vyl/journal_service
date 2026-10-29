## 1. journal_service

- [x] 1.1 `storage.py`: schema 2 migration creating the empty `closed_trades` table and its two indexes exactly as in design.md; version 1 upgrades in place, version 2 opens unchanged, other versions refuse to start.
- [x] 1.2 Tests: fresh database gets version 2 with both tables; a version 1 database with events upgrades and keeps every row and the cursor; reopening a version 2 database changes nothing.
- [x] 1.3 `ruff`, `mypy`, `pytest`, `openspec validate journal-closed-trades-table-v1 --strict`.

## 2. Rollout (on owner's word only)

- [ ] 2.1 PR and merge only on the owner's word. Filling the table is a separate change.
