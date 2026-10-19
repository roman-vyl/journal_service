## 1. journal_service

- [ ] 1.1 `parser.py`: add `OPEN_TRADE_EVALUATED = "open_trade_evaluated"` and `PROTECTION_APPLIED = "protection_applied"` to the accepted and cycle sets (not the nullable-bar set) per D2 and D3; nothing else changes.
- [ ] 1.2 Parser tests, for each type: stored row (type, instance, `trade_cycle_id`, bar, `body` equal to the line, `take_price: null` kept in `body`); missing or non-string `payload.trade_cycle_id` malformed; missing, null or non-integer bar malformed; `schema_version` 1 skipped; other types unchanged.
- [ ] 1.3 Query test: one cycle with `entry_package_applied`, `trade_cycle_opened`, two `open_trade_evaluated`, one `protection_applied` and `trade_cycle_closed` returned by `trade_cycle_id` in bar order.
- [ ] 1.4 End-to-end: real Runtime `JsonlProcessingJournal.open_trade_evaluated` / `protection_applied` lines from strategy_runtime PR #27 through the real tailer into `events`, then the cycle query.
- [ ] 1.5 `ruff`, `mypy`, `pytest`, `openspec validate --all --strict` green.

## 2. Rollout (on owner's word only)

- [ ] 2.1 PR, merge, deploy only on the owner's word, after Runtime PR #27 and ABI PR #25.
