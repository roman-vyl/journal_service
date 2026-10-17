## 1. Query module

- [ ] 1.1 `query.py`: per-request read-only connection (`PRAGMA query_only = ON`), `events_for_instance(...)` and `list_strategy_instances()` returning plain dicts; `body` parsed from the stored text.
- [ ] 1.2 Parameter validation (required id, integers, limit 1..5000 default 1000, `from_bar_ms <= to_bar_ms`), `truncated` via `limit + 1`.

## 2. HTTP

- [ ] 2.1 Routes `GET /v1/events` and `GET /v1/strategy-instances` next to `/health` in the existing server; JSON errors 400, unknown path 404; `/health` unchanged.

## 3. Tests

- [ ] 3.1 Range inclusivity, ordering, other instances excluded, null and non-null `desired_entry` returned unchanged, bar evaluated twice returns both, missing bar absent.
- [ ] 3.2 Limit default, max, `truncated`, invalid parameters (400), unknown path (404).
- [ ] 3.3 `/v1/strategy-instances` counts and bar ranges, empty database.
- [ ] 3.4 Query during a tailer batch: batch stored, cursor advanced, no write by the query connection.
- [ ] 3.5 `ruff check .`, `ruff format --check .`, `mypy`, `pytest`, `openspec validate --all --strict` green.

## 4. Docs

- [ ] 4.1 README: the two routes and examples.
