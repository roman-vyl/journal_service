## 1. journal_service

- [x] 1.1 `parser.py`: add `entry_cycle_ended` to `INGESTED_EVENT_TYPES`, `CYCLE_EVENT_TYPES` and `NULLABLE_BAR_EVENT_TYPES`.
- [x] 1.2 Parser tests: a line with an integer bar and a line with a null bar are stored with type, instance, `trade_cycle_id`, bar and `body` equal to the line; a missing or non-string `trade_cycle_id` is malformed; a missing or non-integer, non-null bar is malformed; `schema_version` 1 is skipped; other types unchanged.
- [ ] 1.3 End-to-end: a real Runtime `entry_cycle_ended` line (after the Runtime change is implemented) goes through the real tailer into `events`; the bar query and the `trade_cycle_id` filter return it.
- [x] 1.4 README status line lists the new type.
- [x] 1.5 `ruff`, `mypy`, `pytest`, `openspec validate --all --strict`.

## 2. Rollout (on owner's word only)

- [ ] 2.1 PR and merge only on the owner's word; deploy Journal first, then Runtime.
