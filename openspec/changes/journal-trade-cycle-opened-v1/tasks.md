## 1. journal_service

- [ ] 1.1 `parser.py`: add `TRADE_CYCLE_OPENED = "trade_cycle_opened"` to the accepted, cycle and nullable-bar sets per D2 and D3; nothing else changes.
- [ ] 1.2 Parser tests: stored row with integer bar and with null bar (type, instance, `trade_cycle_id`, bar, `body` equal to the line); missing or non-string `payload.trade_cycle_id` malformed; missing or non-integer non-null bar malformed; `schema_version` 1 skipped; other types unchanged.
- [ ] 1.3 Query test: one cycle with `entry_package_applied`, `trade_cycle_opened` and `trade_cycle_closed` returned by `trade_cycle_id`; recovery row with null bar first.
- [ ] 1.4 End-to-end: the real Runtime `JsonlProcessingJournal.trade_cycle_opened` lines (with a bar and with null) from strategy_runtime 22e010f through the real tailer into `events`, then the cycle query.
- [ ] 1.5 `ruff`, `mypy`, `pytest`, `openspec validate --all --strict` green.
