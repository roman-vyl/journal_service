## Context

Audits of 2026-10-16 (thread "Trade Observatory"): Runtime keeps an append-only
state JSONL and a best-effort processing journal JSONL; ABI keeps a correlation
JSONL; none of them keeps a per-bar history of decisions and executions. Owner
direction (2026-10-16 16:09): every service knows the meaning of its own events
best, so it writes ready facts into its own processing journal; the Central Journal
is an almost dumb indexer.

```text
STRATEGY RUNTIME ──▶ runtime journal.jsonl ──▶ CENTRAL JOURNAL ◀── abi journal.jsonl ◀── ABI EXECUTOR
 (what Engine answered,                         ingest · store · query          (what was sent, what Bybit
  which bar, which strategy)                                                     confirmed, fill/cancel/protection)
```

## Decisions

### F1. Producers own meaning

Each event is self-contained and is produced by the service that knows its meaning
(Runtime: `live_entry_evaluated`, later `entry_reconciliation_requested`,
`open_trade_evaluated`; ABI later: `entry_order_requested`, `entry_order_confirmed`,
`entry_order_cancelled`, `entry_order_filled`, `protection_requested`,
`protection_confirmed`, `position_closed`). Execution events carry at least
`strategy_instance_id` and `trade_cycle_id`. The Central Journal never computes what
Engine wanted, never derives an ABI state and never reads internal snapshots
(Runtime state file, ABI correlation file).

### F2. Three duties only

1. Ingestion: read the append-only processing journals read-only, with a persisted
   cursor per source, and never store one event twice.
2. Storage: one table of events in SQLite, indexed by `source`, `event_id`,
   `strategy_instance_id`, `trade_cycle_id` (nullable), `bar_open_time_ms`
   (nullable), `occurred_at`, `event_type`; the event body is kept as received.
3. Query API (later change): "events of strategy X between A and B", later "events
   of strategy X, trade cycle Y".

No trading decisions, no interpretation of strategy rules, no state machines.

### F3. Observer, not participant

Trading services do not call the Central Journal, wait for it or read from it. If it
is down, trading continues and it catches up from the journal files on restart.

### F4. One database, one owner

`BBB_DATA_ROOT/journal/journal.sqlite3`, WAL mode. Only this service opens it for
writing; nobody else opens the file. Readers use the query API.

Canonical data layout (each directory is owned by exactly one service; there is no
`journal_service/` directory under the data root, `journal/` is this service's
namespace):

```text
BBB_DATA_ROOT/                      # /Users/mcroma/BBB_data on the Mac
├── strategy-runtime/
│   └── journal/
│       └── runtime.jsonl          # source, owned by Runtime, read-only here
└── journal/
    └── journal.sqlite3            # owned by the Central Journal
```

### F5. Append-only, idempotent

Events are stored at most once, keyed by (`source`, `event_id`); the cursor moves in
the same transaction as the rows; stored rows are never updated or deleted. Derived
views (an "effective" attempt of a repeated bar, trade cycle timelines) are later
queries over raw rows, never rewrites.

### F6. Grow by vertical slices

Each new event type is one small change across producer and Central Journal, proven
end to end before the next: Runtime `live_entry_evaluated`, then ABI
`entry_order_confirmed`, then cancel, protection, managed evaluation. The Central
Journal mostly just accepts one more `event_type` per slice.

### F7. Stack

Python 3.12, standard library `sqlite3`, one process, one small HTTP surface, Docker
image, deployed by bbb_stack like the other services.

## Risks / Trade-offs

- File sources inherit their producer's durability: a best-effort journal can lose
  an event before the Central Journal sees it.
- Each producer's line envelope is an interface; producers may add fields but must
  not change the meaning of existing ones.
