## 1. journal_service

- [ ] 1.1 `parser.py`: accept `entry_package_applied` per D2 and D3; `live_entry_evaluated` behaviour unchanged.
- [ ] 1.2 Tests: stored row (type, instance, `trade_cycle_id`, bar, `body` equal to the line including `order_link_id` and `order_id`); missing or non-string `payload.trade_cycle_id` malformed; missing or non-integer `payload.bar_open_time_ms` malformed; `schema_version` 1 skipped; null values and null ids stored unchanged; existing tests unchanged.
- [ ] 1.3 End-to-end: the real Runtime `JsonlProcessingJournal.entry_package_applied` line through the real tailer into `events`, and returned with `live_entry_evaluated` of the same bar by `GET /v1/events`.
- [ ] 1.4 `ruff`, `mypy`, `pytest`, `openspec validate --all --strict` green.
