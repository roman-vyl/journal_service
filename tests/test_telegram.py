"""Delivery checkpoints, failure recovery and Telegram transport contract."""

import hashlib
import json
import sqlite3
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

import pytest

from journal_service.parser import EventRow, parse_line
from journal_service.storage import Cursor, Store
from journal_service.telegram import (
    DeliveryError,
    Publisher,
    TelegramClient,
    TelegramConfig,
    _strategy_details,
    format_trade,
)
from tests.support import applied, closed, dump, live_entry


def ingest(path: Path, *events: dict) -> None:
    store = Store(path)
    try:
        rows = [parse_line(dump(event).encode()).row for event in events]
        assert all(row is not None for row in rows)
        store.commit_batch(source="runtime", rows=rows, cursor=Cursor(1, 1, 0), ingested_at_ms=1)
    finally:
        store.close()
    # Seed completed builder output; financial assembly is covered by test_trades.
    with sqlite3.connect(path) as journal:
        for event in events:
            if event["event_type"] == "trade_cycle_closed":
                journal.execute(
                    "INSERT OR REPLACE INTO closed_trades "
                    "(strategy_instance_id, trade_cycle_id, close_reason, close_event_id, "
                    "closing_order_id, status, created_at_ms, attempts) "
                    "VALUES (?, ?, ?, ?, ?, 'complete', 1, 1)",
                    (
                        event["strategy_instance_id"],
                        event["payload"]["trade_cycle_id"],
                        event["payload"]["reason"],
                        event["event_id"],
                        event["payload"]["order_id"],
                    ),
                )


def test_delivery_survives_restart_and_reads_late_insertions(tmp_path: Path) -> None:
    config = TelegramConfig(tmp_path / "journal.db", tmp_path / "telegram.db", "secret", "123")
    ingest(config.journal_path, live_entry("signal"), applied("entry"), closed("historical"))
    client = MagicMock(spec=TelegramClient)
    publisher = Publisher(config, client)
    with sqlite3.connect(config.state_path) as state:
        assert not publisher.poll_once(state)
        client.send.assert_not_called()
    ingest(config.journal_path, closed("close"))
    with sqlite3.connect(config.state_path) as state:
        assert publisher.poll_once(state)
    text = client.send.call_args.args[0]
    assert "Причина закрытия: Стоп-лосс" in text and "100.5" in text
    assert "cycle-1" not in text
    client.reset_mock()
    # Newly inserted closure has an older producer timestamp, but must still be delivered.
    ingest(config.journal_path, closed("late", occurred_at="2020-01-01T00:00:00Z"))
    with sqlite3.connect(config.state_path) as state:
        assert Publisher(config, client).poll_once(state)
        assert not publisher.poll_once(state)
    client.send.assert_called_once()
    assert "01.01.2020 03:00:00 МСК" in client.send.call_args.args[0]


@pytest.mark.parametrize("entry", [False, True])
def test_failure_does_not_advance_progress(tmp_path: Path, entry: bool) -> None:
    config = TelegramConfig(tmp_path / "journal.db", tmp_path / "telegram.db", "secret", "123")
    ingest(config.journal_path)
    client = MagicMock(spec=TelegramClient)
    client.send.side_effect = DeliveryError(5)
    publisher = Publisher(config, client)
    with sqlite3.connect(config.state_path) as state:
        assert not publisher.poll_once(state)
        client.send.assert_not_called()
    ingest(config.journal_path, applied("entry") if entry else closed("close", bar=None))
    with sqlite3.connect(config.state_path) as state:
        with pytest.raises(DeliveryError):
            publisher.poll_once(state)
        client.send.side_effect = None
        assert publisher.poll_once(state)
        assert not publisher.poll_once(state)
    assert client.send.call_count == 2


def test_entries_are_scoped_to_source_instance_and_cycle(tmp_path: Path) -> None:
    config = TelegramConfig(tmp_path / "journal.db", tmp_path / "telegram.db", "secret", "123")
    ingest(
        config.journal_path,
        applied("other", instance="other", trigger_price="99999"),
    )
    client = MagicMock(spec=TelegramClient)
    with sqlite3.connect(config.state_path) as state:
        assert not Publisher(config, client).poll_once(state)
    ingest(config.journal_path, closed("close"))
    with sqlite3.connect(config.state_path) as state:
        Publisher(config, client).poll_once(state)
    assert "99999" not in client.send.call_args.args[0]


def test_transport_and_rate_limit() -> None:
    response = MagicMock()
    response.__enter__.return_value.read.return_value = b'{"ok":true,"result":{"message_id":1}}'
    with patch("journal_service.telegram.urlopen", return_value=response) as send:
        TelegramClient("secret", "123").send("message")
    request = send.call_args.args[0]
    assert json.loads(request.data) == {"chat_id": "123", "text": "message"}
    error = HTTPError(
        "https://secret", 429, "limit", {}, BytesIO(b'{"ok":false,"parameters":{"retry_after":20}}')
    )
    with (
        patch("journal_service.telegram.urlopen", side_effect=error),
        pytest.raises(DeliveryError) as caught,
    ):
        TelegramClient("secret", "123").send("message")
    assert caught.value.retry_after == 20
    assert "secret" not in str(caught.value)


def test_message_limit_and_config(tmp_path: Path) -> None:
    event = closed("close", reason="😀" * 5000)
    assert len(format_trade(event, []).encode("utf-16-le")) <= 8192
    with pytest.raises(ValueError):
        TelegramConfig(tmp_path / "same", tmp_path / "same", "secret", "123")
    with pytest.raises(ValueError):
        TelegramConfig.from_env({})


def test_initial_boundary_is_persistent_and_per_chat(tmp_path: Path) -> None:
    config = TelegramConfig(tmp_path / "journal.db", tmp_path / "telegram.db", "secret", "123")
    ingest(config.journal_path, closed("historical"))
    client = MagicMock(spec=TelegramClient)
    with sqlite3.connect(config.state_path) as state:
        assert not Publisher(config, client).poll_once(state)
    # An event arriving after initialization is delivered even if the worker restarted.
    ingest(config.journal_path, closed("new"))
    other = TelegramConfig(config.journal_path, config.state_path, "secret", "456")
    with sqlite3.connect(config.state_path) as state:
        assert not Publisher(other, client).poll_once(state)
        client.send.assert_not_called()
        assert Publisher(config, client).poll_once(state)
        assert not Publisher(config, client).poll_once(state)
    client.send.assert_called_once()
    assert "Сделка закрыта" in client.send.call_args.args[0]


def test_entry_and_close_are_delivered_in_order_across_restart(tmp_path: Path) -> None:
    config = TelegramConfig(tmp_path / "journal.db", tmp_path / "telegram.db", "secret", "123")
    ingest(config.journal_path, applied("historical-entry"), closed("historical-close"))
    client = MagicMock(spec=TelegramClient)
    with sqlite3.connect(config.state_path) as state:
        assert not Publisher(config, client).poll_once(state)
    client.send.assert_not_called()
    ingest(config.journal_path, live_entry("signal"), applied("new-entry"), closed("new-close"))
    with sqlite3.connect(config.state_path) as state:
        assert Publisher(config, client).poll_once(state)
    entry_text = client.send.call_args.args[0]
    assert "Заявка на вход выставлена" in entry_text
    assert "Исполнение пока не подтверждено" in entry_text
    assert "100.5" in entry_text and "cycle-1" not in entry_text
    assert "new-entry" not in entry_text
    with sqlite3.connect(config.state_path) as state:
        assert Publisher(config, client).poll_once(state)
        assert not Publisher(config, client).poll_once(state)
    assert client.send.call_count == 2
    assert "Сделка закрыта" in client.send.call_args.args[0]
    assert "new-close" not in client.send.call_args.args[0]


@pytest.mark.parametrize("bar", [1000, None])
def test_open_notification_retries_and_survives_restart(tmp_path: Path, bar: int | None) -> None:
    config = TelegramConfig(tmp_path / "journal.db", tmp_path / "telegram.db", "secret", "123")
    ingest(config.journal_path)
    client = MagicMock(spec=TelegramClient)
    with sqlite3.connect(config.state_path) as state:
        assert not Publisher(config, client).poll_once(state)
    event = applied("opened")
    event["event_type"] = "trade_cycle_opened"
    event["payload"] = {
        "trade_cycle_id": "cycle-1",
        "bar_open_time_ms": bar,
        "first_fill_at_ms": 1793000000000,
        "average_entry_price": "100.6",
        "entry_order_link_id": "entry-link",
        "entry_order_id": "entry-order",
    }
    # Seed the journal's storage contract directly: this tests only the Telegram adapter.
    store = Store(config.journal_path)
    try:
        store.commit_batch(
            source="runtime",
            rows=[
                EventRow(
                    "opened",
                    "trade_cycle_opened",
                    2,
                    event["occurred_at"],
                    event["strategy_instance_id"],
                    "cycle-1",
                    bar,
                    dump(event),
                )
            ],
            cursor=Cursor(1, 1, 0),
            ingested_at_ms=1,
        )
    finally:
        store.close()
    ingest(config.journal_path, closed("closed-after-open"))
    client.send.side_effect = DeliveryError()
    with sqlite3.connect(config.state_path) as state, pytest.raises(DeliveryError):
        Publisher(config, client).poll_once(state)
    client.send.side_effect = None
    with sqlite3.connect(config.state_path) as state:
        assert Publisher(config, client).poll_once(state)
    text = client.send.call_args.args[0]
    assert text.startswith("Сделка открыта")
    assert "100.6" in text and "26.10.2026 10:33:20 МСК" in text
    assert "1793000000000" not in text and "entry-order" not in text
    assert "исполнение не подтверждено" not in text
    with sqlite3.connect(config.state_path) as state:
        assert Publisher(config, client).poll_once(state)
        assert not Publisher(config, client).poll_once(state)
    assert "Сделка закрыта" in client.send.call_args.args[0]
    assert client.send.call_count == 3


def test_readable_message_hides_ids_and_unknown_fields() -> None:
    event = applied("technical-event", internal_debug="secret-debug")
    text = format_trade(event, [])
    assert "Монета: нет данных" in text
    assert "16.10.2026 15:40:30 МСК" in text
    assert "Цена входной заявки: 100.5" in text
    for technical in (
        "abc",
        "technical-event",
        "cycle-1",
        "abi-link-1",
        "bybit-order-1",
        "secret-debug",
        "bar_open_time_ms",
        "order_id",
    ):
        assert technical not in text


def test_strategy_catalog_and_financial_result(tmp_path: Path) -> None:
    identity = {
        "strategy_id": "ema_pullback",
        "ticker": "BTCUSDT.P",
        "base_timeframe": "5m",
        "raw_spec": {
            "anchor_stack": {"anchor": {"period": 200}},
            "setups": [
                {
                    "component_id": "anchor_stack_width_setup",
                    "params": {
                        "width_lookback_bars": 80,
                        "min_current_width_atr": 3,
                        "min_recent_width_atr": 4,
                    },
                }
            ],
        },
    }
    digest = hashlib.sha256(
        json.dumps(
            identity, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True
        ).encode()
    ).hexdigest()[:24]
    instance = "ema_pullback:" + digest
    (tmp_path / "strategy.json").write_text(json.dumps({**identity, "enabled": False}))
    details = _strategy_details(tmp_path, instance)
    assert _strategy_details(tmp_path, "other") == {}
    text = format_trade(
        closed("hidden"), [], details, {"net_return_pct": "1.23456", "r_multiple": "2.3456"}
    )
    for expected in (
        "Монета: BTCUSDT.P",
        "Якорь: 200",
        "Лукбэк ширины: 80",
        "Ширина стека: 3 ATR",
        "Результат после комиссий: +1,23%",
        "Результат в рисках: +2,35 R",
    ):
        assert expected in text
    assert "Ширина стека за лукбэк" not in text
    assert digest not in text
    text = format_trade(
        closed("hidden"), [], details, {"net_return_pct": "-0.532", "r_multiple": None}
    )
    assert "-0,53%" in text and "Результат в рисках: нет данных" in text


def test_close_waits_for_completed_trade_metrics(tmp_path: Path) -> None:
    config = TelegramConfig(tmp_path / "journal.db", tmp_path / "telegram.db", "secret", "123")
    ingest(config.journal_path)
    client = MagicMock(spec=TelegramClient)
    with sqlite3.connect(config.state_path) as state:
        assert not Publisher(config, client).poll_once(state)
    ingest(config.journal_path, closed("close"))
    with sqlite3.connect(config.journal_path) as journal:
        journal.execute("DELETE FROM closed_trades")
    with sqlite3.connect(config.state_path) as state:
        assert not Publisher(config, client).poll_once(state)
    client.send.assert_not_called()
    with sqlite3.connect(config.journal_path) as journal:
        journal.execute(
            "INSERT INTO closed_trades (strategy_instance_id, trade_cycle_id, close_reason, "
            "close_event_id, closing_order_id, status, created_at_ms, attempts) "
            "VALUES (?, ?, 'stop_loss', 'close', 'order', 'incomplete', 1, 0)",
            ("ema_pullback:abc", "cycle-1"),
        )
    with sqlite3.connect(config.state_path) as state:
        assert not Publisher(config, client).poll_once(state)
    with sqlite3.connect(config.journal_path) as journal:
        journal.execute(
            "UPDATE closed_trades SET status='complete', net_return_pct='-0.53', r_multiple='-1.26'"
        )
    with sqlite3.connect(config.state_path) as state:
        assert Publisher(config, client).poll_once(state)
        assert not Publisher(config, client).poll_once(state)
    client.send.assert_called_once()
    text = client.send.call_args.args[0]
    assert "Результат после комиссий: -0,53%" in text
    assert "Результат в рисках: -1,26 R" in text
