## 1. journal_service

- [ ] 1.1 `config.py`: `JOURNAL_ABI_BASE_URL` (optional, empty = not configured), `JOURNAL_TRADES_INTERVAL_S` (default 60, positive).
- [ ] 1.2 `abi_client.py`: one GET of the per-cycle route, 5 s timeout, percent-encoded path, result or error code per design D3.4; standard library only.
- [ ] 1.3 `trades.py`: detection (D2), assembly and formulas (D3), retry (D4); complete rows never updated.
- [ ] 1.4 `main.py`: builder thread with stop on shutdown; `health.py`: `closed_trades` block (D5).
- [ ] 1.5 Tests: real 6072511f short (gross −969.3902, fees 338.60068539, net −1307.99088539), long, several entry fills, partial SL plus close, plan missing, `runtime_signal` exit slippage null, Funding ignored, ABI not configured / 503 / timeout / truncated / bad JSON, exit appears on a later pass, complete row unchanged by later passes and restarts, second `trade_cycle_closed` ignored, backfill of old closures, ingestion continues while ABI is down, health block.
- [ ] 1.6 README; `ruff`, `mypy`, `pytest`, `openspec validate --all --strict`.

## 2. Rollout (on owner's word only)

- [ ] 2.1 PR and merge on the owner's word.
- [ ] 2.2 bbb_stack: `JOURNAL_ABI_BASE_URL` and network path from the Journal container to ABI (separate change), deploy on «деплой».
- [ ] 2.3 Demo check: the next closed trade becomes `complete` with prices and fees equal to Bybit's.
