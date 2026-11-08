"""End to end: a real process tails a ready journal, is stopped and restarted."""

import contextlib
import json
import os
import signal
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from tests.support import append, live_entry


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _health(port: int) -> dict[str, object]:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as response:
        return json.loads(response.read())  # type: ignore[no-any-return]


def _wait_for(port: int, stored: int) -> dict[str, object]:
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        try:
            body = _health(port)
            if body["stored_count"] == stored:
                return body
        except OSError:
            pass
        time.sleep(0.1)
    raise AssertionError("service did not reach the expected stored_count")


def _start(journal: Path, db: Path, port: int) -> subprocess.Popen[bytes]:
    env = {
        **os.environ,
        "JOURNAL_RUNTIME_SOURCE_PATH": str(journal),
        "JOURNAL_DB_PATH": str(db),
        "JOURNAL_POLL_INTERVAL_S": "0.1",
        "JOURNAL_HOST": "127.0.0.1",
        "JOURNAL_PORT": str(port),
    }
    return subprocess.Popen(
        [sys.executable, "-c", "from journal_service.main import main; main()"], env=env
    )


def test_stop_and_restart_keeps_every_event_exactly_once(tmp_path: Path) -> None:
    journal = tmp_path / "strategy-runtime" / "journal" / "runtime.jsonl"
    journal.parent.mkdir(parents=True)
    db = tmp_path / "journal" / "journal.sqlite3"
    append(journal, live_entry("e1", 1000), live_entry("e2", 1300, desired_entry=None))
    port = _free_port()

    first = _start(journal, db, port)
    try:
        _wait_for(port, 2)
    finally:
        first.send_signal(signal.SIGTERM)
        assert first.wait(timeout=15) == 0

    append(journal, live_entry("e3", 1600))
    second = _start(journal, db, port)
    try:
        body = _wait_for(port, 1)
    finally:
        second.send_signal(signal.SIGTERM)
        assert second.wait(timeout=15) == 0

    assert body["sources"]["runtime"]["cursor_offset"] == journal.stat().st_size  # type: ignore[index]
    connection = sqlite3.connect(db)
    try:
        ids = [row[0] for row in connection.execute("SELECT event_id FROM events ORDER BY rowid")]
    finally:
        connection.close()
    assert ids == ["e1", "e2", "e3"]


def test_telegram_starts_and_stops_in_journal_process(tmp_path: Path, monkeypatch) -> None:
    journal = tmp_path / "runtime.jsonl"
    db = tmp_path / "journal.sqlite3"
    append(journal, live_entry("signal"))
    monkeypatch.setenv("JOURNAL_TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("JOURNAL_TELEGRAM_CHAT_ID", "123")
    monkeypatch.delenv("JOURNAL_TELEGRAM_STATE_PATH", raising=False)
    port = _free_port()
    process = _start(journal, db, port)
    progress = db.with_name("telegram-progress.sqlite3")
    try:
        _wait_for(port, 1)
        deadline = time.monotonic() + 5
        subscribed = False
        while time.monotonic() < deadline:
            if progress.exists():
                with (
                    sqlite3.connect(progress) as state,
                    contextlib.suppress(sqlite3.OperationalError),
                ):
                    subscribed = (
                        state.execute("SELECT 1 FROM progress WHERE chat_id='123'").fetchone()
                        is not None
                    )
                if subscribed:
                    break
            time.sleep(0.05)
        assert subscribed, "Telegram did not start with the journal"
    finally:
        process.send_signal(signal.SIGTERM)
        assert process.wait(timeout=15) == 0
