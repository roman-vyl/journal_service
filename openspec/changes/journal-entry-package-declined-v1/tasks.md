## 1. journal_service

- [ ] 1.1 `parser.py`: add `entry_package_declined` to `INGESTED_EVENT_TYPES` and `CYCLE_EVENT_TYPES` (not to `NULLABLE_BAR_EVENT_TYPES`), per D2 and D3.
- [ ] 1.2 Parser tests:
  - a declined line is stored with type, instance, `trade_cycle_id`, bar and `body` equal to the line;
  - a missing or non-string `payload.trade_cycle_id` is malformed;
  - a null or missing bar is malformed;
  - `schema_version` 1 is skipped;
  - other types are unchanged.
- [ ] 1.3 End-to-end: the real Runtime `JsonlProcessingJournal.entry_package_declined` line goes through the real tailer into `events`. Then two queries:
  - `GET /v1/events?strategy_instance_id=…&from_bar_ms=…&to_bar_ms=…` returns it with `body` equal to the line;
  - the `trade_cycle_id` filter returns only it.
- [ ] 1.4 README status line lists the new type.
- [ ] 1.5 `ruff`, `mypy`, `pytest`, `openspec validate --all --strict` green.
