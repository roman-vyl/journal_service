## 1. journal_service

- [x] 1.1 `parser.py`: add `TRADE_CYCLE_OPENED = "trade_cycle_opened"` to the accepted, cycle and nullable-bar sets per D2 and D3; nothing else changes.
- [x] 1.2 Parser tests: stored row with integer bar and with null bar (type, instance, `trade_cycle_id`, bar, `body` equal to the line); missing or non-string `payload.trade_cycle_id` malformed; missing or non-integer non-null bar malformed; `schema_version` 1 skipped; other types unchanged.
- [x] 1.3 Query test: one cycle with `entry_package_applied`, `trade_cycle_opened` and `trade_cycle_closed` returned by `trade_cycle_id`; recovery row with null bar first.
- [x] 1.4 End-to-end: the real Runtime `JsonlProcessingJournal.trade_cycle_opened` lines (with a bar and with null) from strategy_runtime 22e010f through the real tailer into `events`, then the cycle query. Checked 2026-10-18 with Runtime 22e010f: 4 lines (applied, opened with a bar, closed, opened with null bar and null `entry_order_id`) became 4 rows (0 skipped, 0 malformed); the cycle query returned applied, opened and closed in order, the recovery opening came first in the instance query, bodies equal to the lines.
- [x] 1.5 `ruff`, `mypy`, `pytest`, `openspec validate --all --strict` green.
