## 1. Query module

- [x] 1.1 `query.py`: per-request read-only connection (`PRAGMA query_only = ON`), `events_for_instance(...)` and `list_strategy_instances()` returning plain dicts; `body` parsed from the stored text.
- [x] 1.2 Parameter validation (required id, integers, limit 1..5000 default 1000, `from_bar_ms <= to_bar_ms`), `truncated` via `limit + 1`.

## 2. HTTP

- [x] 2.1 Routes `GET /v1/events` and `GET /v1/strategy-instances` next to `/health` in the existing server; JSON errors 400, unknown path 404; `/health` unchanged.

## 3. Tests

- [x] 3.1 Range inclusivity, ordering, other instances excluded, null and non-null `desired_entry` returned unchanged, bar evaluated twice returns both, missing bar absent.
- [x] 3.2 Limit default, max, `truncated`, invalid parameters (400), unknown path (404).
- [x] 3.3 `/v1/strategy-instances` counts and bar ranges, empty database.
- [x] 3.4 Query during a tailer batch: batch stored, cursor advanced, no write by the query connection.
- [x] 3.5 `ruff check .`, `ruff format --check .`, `mypy`, `pytest`, `openspec validate --all --strict` green.

## 4. Docs

- [x] 4.1 README: the two routes and examples.
- [x] 4.2 Stored-event contract checked against real data and the real producer code (2026-10-17): archived `runtime.jsonl` from Mac (Runtime 15e7fed/33be4e9) has 11 `live_entry_evaluated` lines, 10 with `desired_entry = null` and 1 with an object; `events` holds 11 rows with 11 distinct `event_id`, `body` byte-equal to each line, `bar_open_time_ms` = `payload.bar_open_time_ms`, `trade_cycle_id` NULL; prices are decimal strings with full precision (e.g. `planned_entry_price "2436.996757183465"`). No real bar was evaluated twice; that case is covered by an end-to-end run of the real Runtime `JsonlProcessingJournal` into the real Tailer (null, signal, same bar twice, skipped bar: 4 rows, bodies equal to lines, 20-digit price kept, skipped bar absent).
