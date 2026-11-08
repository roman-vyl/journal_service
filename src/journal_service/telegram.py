"""Read-only journal consumer publishing entry orders, openings and closures to Telegram."""

from __future__ import annotations

import fcntl
import hashlib
import json
import logging
import math
import os
import signal
import sqlite3
from collections.abc import Mapping
from contextlib import closing
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from threading import Event
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class TelegramConfig:
    journal_path: Path
    state_path: Path
    token: str = field(repr=False)
    chat_id: str
    poll_interval_s: float = 3.0
    specs_path: Path | None = None

    def __post_init__(self) -> None:
        if not self.token.strip() or not self.chat_id.strip():
            raise ValueError("Telegram token and chat ID must be non-empty")
        if not math.isfinite(self.poll_interval_s) or self.poll_interval_s <= 0:
            raise ValueError("Telegram poll interval must be finite and positive")
        if self.journal_path.resolve() == self.state_path.resolve():
            raise ValueError("Telegram state must be separate from the journal database")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> TelegramConfig:
        values = os.environ if env is None else env
        try:
            return cls(
                specs_path=(
                    Path(values["JOURNAL_TELEGRAM_SPECS_PATH"])
                    if values.get("JOURNAL_TELEGRAM_SPECS_PATH")
                    else None
                ),
                journal_path=Path(values["JOURNAL_DB_PATH"]),
                state_path=Path(
                    values.get("JOURNAL_TELEGRAM_STATE_PATH")
                    or str(Path(values["JOURNAL_DB_PATH"]).with_name("telegram-progress.sqlite3"))
                ),
                token=values["JOURNAL_TELEGRAM_BOT_TOKEN"],
                chat_id=values["JOURNAL_TELEGRAM_CHAT_ID"],
                poll_interval_s=float(values.get("JOURNAL_TELEGRAM_POLL_INTERVAL_S", "3")),
            )
        except KeyError as exc:
            raise ValueError(f"{exc.args[0]} is required") from None


class DeliveryError(Exception):
    """Sanitized transport failure; never includes a URL containing the token."""

    def __init__(self, retry_after: float = 3) -> None:
        super().__init__("Telegram delivery failed; message remains pending")
        self.retry_after = retry_after


class TelegramClient:
    def __init__(self, token: str, chat_id: str) -> None:
        self._url = f"https://api.telegram.org/bot{token}/sendMessage"
        self._chat_id = chat_id

    def send(self, text: str) -> None:
        request = Request(
            self._url,
            data=json.dumps({"chat_id": self._chat_id, "text": text}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=15) as response:
                result = json.loads(response.read())
        except HTTPError as exc:
            try:
                result = json.loads(exc.read())
            except (ValueError, OSError):
                raise DeliveryError() from None
        except (OSError, URLError, ValueError):
            raise DeliveryError() from None
        if not isinstance(result, dict) or result.get("ok") is not True:
            delay = result.get("parameters", {}) if isinstance(result, dict) else {}
            retry = delay.get("retry_after", 3) if isinstance(delay, dict) else 3
            if not isinstance(retry, (int, float)) or not math.isfinite(retry) or retry <= 0:
                retry = 3
            raise DeliveryError(float(retry))


def _moscow_time(value: Any, *, milliseconds: bool = False) -> str:
    try:
        if milliseconds:
            moment = datetime.fromtimestamp(int(value) / 1000, tz=UTC)
        else:
            moment = datetime.fromisoformat(str(value))
            if moment.tzinfo is None:
                return "время не указано"
        return moment.astimezone(ZoneInfo("Europe/Moscow")).strftime("%d.%m.%Y %H:%M:%S МСК")
    except (ValueError, TypeError, OverflowError, OSError):
        return "время не указано"


def _strategy_details(path: Path | None, instance: str) -> dict[str, Any]:
    """Match immutable deployment identity; read the catalog without importing Runtime."""
    if path is None:
        return {}
    for file in sorted(path.glob("*.json")):
        try:
            document = json.loads(file.read_text())
            identity = {
                key: document[key]
                for key in ("strategy_id", "ticker", "base_timeframe", "raw_spec")
            }
            canonical = json.dumps(
                identity, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True
            ).encode()
            digest = hashlib.sha256(canonical).hexdigest()[:24]
            if f"{document['strategy_id']}:{digest}" != instance:
                continue
            spec = document["raw_spec"]
            anchor = spec.get("anchor_stack", {}).get("anchor")
            details = {
                "instrument": document["ticker"],
                "anchor": anchor.get("period") if isinstance(anchor, dict) else anchor,
            }
            for setup in spec.get("setups", []):
                if setup.get("component_id") == "anchor_stack_width_setup":
                    params = setup.get("params", setup)
                    details.update(
                        {
                            key: params.get(key)
                            for key in (
                                "width_lookback_bars",
                                "min_current_width_atr",
                                "min_recent_width_atr",
                            )
                        }
                    )
            return details
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            _LOGGER.warning("Cannot read Telegram strategy metadata from %s", file.name)
    return {}


def _signed_number(value: Any, suffix: str) -> str:
    try:
        number = Decimal(str(value))
        if number.is_finite():
            return f"{number:+.2f}{suffix}".replace(".", ",")
    except InvalidOperation:
        pass
    return "нет данных"


def format_trade(
    event: dict[str, Any],
    entries: list[dict[str, Any]],
    strategy: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
) -> str:
    """Human-readable facts only; never expose technical identifiers or raw payloads."""
    kind = event["event_type"]
    is_entry = kind == "entry_package_applied"
    is_open = kind == "trade_cycle_opened"
    heading = "Заявка на вход выставлена" if is_entry else "Сделка закрыта"
    if is_open:
        heading = "Сделка открыта"
    payload = event["payload"]
    strategy = strategy or {}
    instrument = strategy.get("instrument") or payload.get("instrument")
    lines = [
        heading,
        f"Монета: {instrument or 'нет данных'}",
        f"Якорь: {strategy.get('anchor') or 'нет данных'}",
        f"Лукбэк ширины: {strategy.get('width_lookback_bars') or 'нет данных'}",
    ]
    current = strategy.get("min_current_width_atr")
    lines.append(f"Ширина стека: {current if current is not None else 'нет данных'} ATR")
    if not is_entry and not is_open:
        result = result or {}
        lines.extend(
            [
                f"Результат после комиссий: {_signed_number(result.get('net_return_pct'), '%')}",
                f"Результат в рисках: {_signed_number(result.get('r_multiple'), ' R')}",
            ]
        )
    if is_open and payload.get("first_fill_at_ms") is not None:
        lines.append(f"Время входа: {_moscow_time(payload['first_fill_at_ms'], milliseconds=True)}")
    else:
        lines.append(f"Время события: {_moscow_time(event['occurred_at'])}")
    if is_entry:
        lines.append("Заявка выставлена. Исполнение пока не подтверждено.")
    if is_open:
        lines.append("Подтверждено первое исполнение. Заявка могла исполниться частично.")
    labels = {
        "instrument": "Инструмент",
        "timeframe": "Таймфрейм",
        "side": "Направление",
        "trigger_price": "Цена входной заявки",
        "stop_loss": "Стоп-лосс",
        "take_profit": "Тейк-профит",
        "quantity": "Количество",
        "average_entry_price": "Средняя цена входа на момент подтверждения",
        "reason": "Причина закрытия",
    }
    reasons = {
        "stop_loss": "Стоп-лосс",
        "take_profit": "Тейк-профит",
        "close_signal": "Сигнал стратегии",
        "manual": "Закрыто вручную",
    }
    for title, facts in [
        *[("Параметры заявки на вход", entry["payload"]) for entry in entries],
        ("", payload),
    ]:
        if title:
            lines.extend(["", title + ":"])
        for key, label in labels.items():
            value = facts.get(key)
            if value is None:
                continue
            if key == "reason":
                value = reasons.get(str(value), "Причина не распознана")
            elif key == "side":
                value = {"long": "Покупка", "short": "Продажа"}.get(str(value), "Не указано")
            lines.append(f"{label}: {value}")
    text = "\n".join(lines)
    encoded = text.encode("utf-16-le")
    if len(encoded) > 8000:
        text = encoded[:7900].decode("utf-16-le", errors="ignore") + "\n… (сокращено)"
    return text


class Publisher:
    """Single worker; durable checkpoint is advanced only after successful delivery."""

    def __init__(self, config: TelegramConfig, client: TelegramClient) -> None:
        self.config = config
        self.client = client

    def poll_once(self, state: sqlite3.Connection) -> bool:
        state.execute(
            "CREATE TABLE IF NOT EXISTS progress "
            "(chat_id TEXT PRIMARY KEY, last_rowid INTEGER NOT NULL)"
        )
        row = state.execute(
            "SELECT last_rowid FROM progress WHERE chat_id = ?", (self.config.chat_id,)
        ).fetchone()
        cursor = 0 if row is None else row[0]
        uri = self.config.journal_path.resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(uri, uri=True, timeout=5)) as journal:
            if row is None:
                # Establish the subscription boundary once, including for an empty journal.
                # Later polls use this durable position even after a worker restart.
                boundary = journal.execute("SELECT COALESCE(MAX(rowid), 0) FROM events").fetchone()[
                    0
                ]
                with state:
                    state.execute(
                        "INSERT INTO progress VALUES (?, ?)", (self.config.chat_id, boundary)
                    )
                return False
            event = journal.execute(
                "SELECT rowid, source, body FROM events "
                "WHERE event_type IN "
                "('entry_package_applied', 'trade_cycle_opened', 'trade_cycle_closed') "
                "AND rowid > ? ORDER BY rowid LIMIT 1",
                (cursor,),
            ).fetchone()
            if event is None:
                return False
            record = json.loads(event[2])
            entries = []
            result = None
            if record["event_type"] == "trade_cycle_closed":
                entries = journal.execute(
                    "SELECT body FROM events WHERE source = ? AND strategy_instance_id = ? "
                    "AND trade_cycle_id = ? AND event_type = 'entry_package_applied' "
                    "ORDER BY rowid",
                    (event[1], record["strategy_instance_id"], record["payload"]["trade_cycle_id"]),
                ).fetchall()
            if (
                record["event_type"] == "trade_cycle_closed"
                and journal.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='closed_trades'"
                ).fetchone()
            ):
                journal.row_factory = sqlite3.Row
                trade = journal.execute(
                    "SELECT * FROM closed_trades WHERE strategy_instance_id = ? "
                    "AND trade_cycle_id = ?",
                    (record["strategy_instance_id"], record["payload"]["trade_cycle_id"]),
                ).fetchone()
                # The trade builder completes financial facts asynchronously.
                if trade is None or trade["status"] != "complete":
                    return False
                result = dict(trade)
        strategy = _strategy_details(self.config.specs_path, record["strategy_instance_id"])
        self.client.send(
            format_trade(record, [json.loads(entry[0]) for entry in entries], strategy, result)
        )
        with state:
            state.execute(
                "INSERT INTO progress VALUES (?, ?) ON CONFLICT(chat_id) DO UPDATE "
                "SET last_rowid = excluded.last_rowid",
                (self.config.chat_id, event[0]),
            )
        return True


def run(config: TelegramConfig, stop: Event | None = None) -> None:
    config.state_path.parent.mkdir(parents=True, exist_ok=True)
    if stop is None:
        stop = Event()
        signal.signal(signal.SIGTERM, lambda *_: stop.set())
        signal.signal(signal.SIGINT, lambda *_: stop.set())
    publisher = Publisher(config, TelegramClient(config.token, config.chat_id))
    with config.state_path.with_suffix(config.state_path.suffix + ".lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Telegram state is already used by another publisher") from None
        with closing(sqlite3.connect(config.state_path)) as state:
            while not stop.is_set():
                delay = config.poll_interval_s
                try:
                    publisher.poll_once(state)
                except DeliveryError as exc:
                    delay = max(delay, exc.retry_after)
                    _LOGGER.warning("Telegram delivery failed; retrying in %s seconds", delay)
                except (sqlite3.Error, ValueError, KeyError, TypeError):
                    _LOGGER.error("Cannot read journal or save Telegram progress; retrying")
                stop.wait(delay)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    run(TelegramConfig.from_env())


if __name__ == "__main__":
    main()
