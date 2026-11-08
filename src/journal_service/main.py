"""Process entry point: tailer thread plus the health server."""

from __future__ import annotations

import logging
import os
import signal
from threading import Event, Thread

from journal_service.abi_client import fetch_cycle
from journal_service.config import RUNTIME_SOURCE_NAME, Config
from journal_service.health import build_server
from journal_service.stats import IngestStats
from journal_service.storage import Store
from journal_service.tailer import Tailer
from journal_service.telegram import TelegramConfig
from journal_service.telegram import run as run_telegram
from journal_service.trades import TradeBuilder, TradesStats

_LOGGER = logging.getLogger("journal_service")


def _tail_forever(tailer: Tailer, stop: Event, interval_s: float) -> None:
    while not stop.is_set():
        try:
            tailer.poll_once()
        except Exception:
            _LOGGER.exception("Ingest poll failed; retrying")
        stop.wait(interval_s)


def _build_forever(builder: TradeBuilder, stop: Event, interval_s: float) -> None:
    while not stop.is_set():
        try:
            builder.run_pass()
        except Exception:
            _LOGGER.exception("Closed-trades pass failed; retrying")
        stop.wait(interval_s)


def run(config: Config) -> None:
    telegram_config = None
    if os.environ.get("JOURNAL_TELEGRAM_BOT_TOKEN") or os.environ.get("JOURNAL_TELEGRAM_CHAT_ID"):
        telegram_config = TelegramConfig.from_env()
    store = Store(config.db_path)
    cursor = store.get_cursor(RUNTIME_SOURCE_NAME)
    stats = IngestStats(
        cursor_offset=0 if cursor is None else cursor.offset,
        last_occurred_at=store.last_occurred_at(RUNTIME_SOURCE_NAME),
    )
    tailer = Tailer(
        store=store,
        source=RUNTIME_SOURCE_NAME,
        path=config.runtime_source_path,
        stats=stats,
        batch_size=config.batch_size,
    )
    stop = Event()
    worker = Thread(
        target=_tail_forever, args=(tailer, stop, config.poll_interval_s), name="tailer"
    )
    trades_stats = TradesStats(abi_configured=bool(config.abi_base_url))
    builder = TradeBuilder(config.db_path, config.abi_base_url, trades_stats, fetch_cycle)
    trades_worker = Thread(
        target=_build_forever,
        args=(builder, stop, config.trades_interval_s),
        name="closed-trades",
    )
    server = build_server(
        config.host, config.port, RUNTIME_SOURCE_NAME, stats, config.db_path, trades_stats
    )

    def shutdown(_signum: int, _frame: object) -> None:
        stop.set()
        Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    telegram_worker = (
        Thread(target=run_telegram, args=(telegram_config, stop), name="telegram")
        if telegram_config is not None
        else None
    )
    worker.start()
    trades_worker.start()
    if telegram_worker is not None:
        telegram_worker.start()
    try:
        server.serve_forever()
    finally:
        stop.set()
        worker.join()
        trades_worker.join()
        if telegram_worker is not None:
            telegram_worker.join()
        server.server_close()
        store.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    run(Config.from_env())
