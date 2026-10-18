## 1. journal_service

- [x] 1.1 `parser.py`: accept `trade_cycle_closed` per D2 and D3; `EventRow.bar_open_time_ms` becomes `int | None`; the other two types unchanged.
- [x] 1.2 Parser tests: stored row with integer bar and with null bar (type, instance, `trade_cycle_id`, bar, `body` equal to the line); missing or non-string `payload.trade_cycle_id` malformed; missing or non-integer non-null bar malformed; `schema_version` 1 skipped; null bar for the other two types still malformed.
- [x] 1.3 `query.py`: optional `trade_cycle_id` filter and `trade_cycle_id` field per D4; tests for filter by cycle, field on every event, null-bar row returned without bar bounds and excluded with them, existing tests unchanged.
- [x] 1.4 End-to-end: the real Runtime `JsonlProcessingJournal.trade_cycle_closed` lines (with a bar and with null) through the real tailer into `events`, then `GET /v1/events?strategy_instance_id=…&trade_cycle_id=…` returns the cycle's `entry_package_applied` and `trade_cycle_closed`. Checked 2026-10-18 with Runtime 73d7acf: 4 lines (two applied, one closure with a bar, one with null) became 4 rows (0 skipped, 0 malformed); each cycle query returned its applied record and its closure with bodies equal to the lines, the null-bar closure first.
- [x] 1.5 `ruff`, `mypy`, `pytest`, `openspec validate --all --strict` green.
