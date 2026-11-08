# journal_service

BBB Central Journal: an indexer of facts that trading services publish about
themselves. Each service writes self-contained events to its own append-only
processing journal (Strategy Runtime: what Engine answered, for which strategy and
bar; later ABI: what was sent, what Bybit confirmed, fills, cancels, protection).
The Central Journal reads those files, stores the events once in its own SQLite
and, later, answers queries such as "events of strategy X between A and B".

It never interprets events, never reconstructs them from internal state snapshots,
never makes trading decisions, and never calls Strategy Engine, Strategy Runtime,
ABI or Market Data Service. No trading service depends on it.

Status: ingest of Runtime `live_entry_evaluated`, `entry_package_applied`,
`entry_package_declined`, `entry_cycle_ended`, `trade_cycle_opened`, `open_trade_evaluated`,
`protection_applied` and `trade_cycle_closed`, `GET /health` and the read API below. Database schema 2 adds the `closed_trades` table: a builder thread fills it once per
`JOURNAL_TRADES_INTERVAL_S` (default 60) from stored `trade_cycle_closed` events and ABI's
per-cycle exchange-journal route at `JOURNAL_ABI_BASE_URL` (empty = rows stay `incomplete`
with `abi_not_configured`); `/health` shows its `closed_trades` block.
bbb_stack wiring is a separate later step.

Run locally:

```bash
pip install -e '.[dev]'
JOURNAL_RUNTIME_SOURCE_PATH=/path/to/runtime.jsonl \
JOURNAL_DB_PATH=/path/to/journal/journal.sqlite3 \
journal-service            # optional: JOURNAL_POLL_INTERVAL_S, JOURNAL_BATCH_SIZE, JOURNAL_HOST, JOURNAL_PORT (8097)
```

Read API (read-only, local network, no auth; `body` is the stored line parsed, unchanged):

```bash
curl 'http://127.0.0.1:8097/v1/events?strategy_instance_id=<id>&from_bar_ms=<ms>&to_bar_ms=<ms>'
curl 'http://127.0.0.1:8097/v1/strategy-instances'
```

`/v1/events` returns `{"events": [...], "truncated": bool}` ordered by bar, `occurred_at`, `event_id`
(bounds inclusive; without `limit` every event of the range is returned, `truncated` is true only when an optional `limit` cut the answer; invalid input is HTTP 400). A bar with no
stored event is absent from the answer; an event with `payload.desired_entry = null` means
"evaluated, no signal".

Closed trades (rows of `closed_trades` exactly as stored; decimals are strings):

```bash
curl 'http://127.0.0.1:8097/v1/closed-trades?strategy_instance_id=<id>&from_closed_ms=<ms>&to_closed_ms=<ms>&status=complete&limit=<n>'
curl 'http://127.0.0.1:8097/v1/closed-trades/<strategy_instance_id>/<trade_cycle_id>'
```

The list returns `{"trades": [...], "truncated": bool}`: incomplete rows (no close time yet)
first by creation, then by `closed_at_ms`, `close_event_id`. Every parameter is optional; the
close period is inclusive and skips incomplete rows. One trade returns `{"trade": {...}}` or
404. Invalid input is HTTP 400.

Checks: `ruff check .`, `ruff format --check .`, `mypy`, `pytest`.

- `openspec/changes/journal-service-foundation-v1`: purpose, boundaries, stack.
- `openspec/changes/runtime-live-entry-first-event-v1`: the first end-to-end event,
  Runtime `live_entry_evaluated` (including `desired_entry = null`).
  Producer side: `strategy_runtime` change `runtime-desired-entry-journal-v1`.

Telegram entry-order and closed-trade publisher:

```bash
JOURNAL_DB_PATH=/path/to/journal/journal.sqlite3 \
JOURNAL_TELEGRAM_STATE_PATH=/path/to/telegram/progress.sqlite3 \
JOURNAL_TELEGRAM_BOT_TOKEN='<BotFather token>' \
JOURNAL_TELEGRAM_CHAT_ID='<chat ID or @channel>' \
journal-telegram
# Alternatively: python -m journal_service.telegram
```

Create the bot with BotFather and add it to the destination chat/channel with
permission to post. For a private chat, start the bot first. Keep the token in
secret environment configuration. The publisher uses Telegram's
[sendMessage API](https://core.telegram.org/bots/api#sendmessage).

Run this as a separate process alongside the journal. It opens the journal database
read-only and writes only its own progress database. No runtime source path is
required. In Docker, override the image entrypoint with `journal-telegram`, disable
the journal HTTP healthcheck for this worker, and mount the journal directory
(including SQLite WAL/SHM files) and a persistent writable progress directory.

On the first successful poll, the publisher saves the current end of the journal
without sending historical trades. It then publishes only newly ingested
`entry_package_applied` and `trade_cycle_closed` events, in ingestion order.
Entry notifications confirm that an entry order was applied, not that it filled. On restart it resumes from the
saved position, including entry orders and closures ingested while the worker was stopped.
A closure message contains the recorded closure fields,
strategy, closure timestamp, and matching `entry_package_applied` fields when
available. Order parameters are labeled as such; they are not presented as actual
fills or calculated PnL. Missing facts are not reconstructed. Messages exceeding
the Telegram text limit are shortened.

`JOURNAL_TELEGRAM_POLL_INTERVAL_S` defaults to 3 seconds; at most one message is
sent per poll. Errors leave the event pending; flood-limit responses respect
Telegram's `retry_after`. SIGTERM/SIGINT stop the worker. A process lock prevents
concurrent workers using the same state file. Preserve that file across restarts;
use one state file per journal and one worker per destination. Progress is stored
per chat ID; a new destination starts at the current end of the journal as well.
Deleting/replacing the journal requires a new progress file.

Successful deliveries are checkpointed. Delivery is **at least once**: a timeout
or crash after Telegram accepts a message but before the checkpoint is saved can
cause a duplicate. Telegram does not provide an idempotency key for sendMessage.


Telegram messages use Russian labels and Moscow time and omit technical IDs.
Set `JOURNAL_TELEGRAM_SPECS_PATH` to a read-only mounted deployment catalog directory
containing the original deployment JSON files (including historical deployments).
The adapter matches the immutable strategy identity and shows the instrument,
anchor period, width lookback and current minimum stack width in ATR.
Missing metadata is displayed as unavailable, never inferred from the identity.
For `trade_cycle_opened`, the adapter shows the first confirmed fill time and
observed average entry price; a partial fill also opens a trade.
For closures, it reads `net_return_pct` and `r_multiple` from the journal's
`closed_trades` table. Percent is net PnL divided by entry notional, not account
return. These figures include recorded trading fees. If the table exists, the
closure stays pending until its row is complete; later messages also wait to
preserve ingestion order. If the table or a metric is absent, the message shows
“нет данных”. The adapter does not calculate financial results itself.
