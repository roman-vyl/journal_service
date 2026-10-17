## 1. journal_service

- [ ] 1.1 `parser.py`: accept `entry_package_applied` per D1 and D2; `EventRow.bar_open_time_ms` optional; `live_entry_evaluated` behaviour unchanged.
- [ ] 1.2 Tests: stored row (type, instance, `trade_cycle_id`, null bar, `body` equal to the line); missing or non-string `payload.trade_cycle_id` malformed; `schema_version` 1 skipped; values not validated; `live_entry_evaluated` still requires its bar; existing tests unchanged.
- [ ] 1.3 End-to-end: the real Runtime `JsonlProcessingJournal.entry_package_applied` line through the real tailer into `events`.
- [ ] 1.4 `ruff`, `mypy`, `pytest`, `openspec validate --all --strict` green.
