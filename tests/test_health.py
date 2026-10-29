import json
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from threading import Thread

import pytest

from journal_service.health import build_server
from journal_service.stats import IngestStats


@pytest.fixture
def base_url_and_stats(tmp_path: Path) -> Iterator[tuple[str, IngestStats]]:
    stats = IngestStats(cursor_offset=10, last_occurred_at="2026-10-16T12:00:00Z")
    server = build_server("127.0.0.1", 0, "runtime", stats, tmp_path / "j.sqlite3")
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", stats
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_health_reports_cursor_last_event_and_counters(
    base_url_and_stats: tuple[str, IngestStats],
) -> None:
    base_url, stats = base_url_and_stats
    stats.record_batch(
        cursor_offset=250,
        stored=2,
        skipped=3,
        malformed=1,
        last_occurred_at="2026-10-16T12:05:00Z",
    )

    with urllib.request.urlopen(f"{base_url}/health", timeout=2) as response:
        assert response.status == 200
        body = json.loads(response.read())

    assert body == {
        "status": "ok",
        "sources": {
            "runtime": {
                "cursor_offset": 250,
                "last_ingested_occurred_at": "2026-10-16T12:05:00Z",
            }
        },
        "stored_count": 2,
        "skipped_count": 3,
        "malformed_count": 1,
    }


@pytest.mark.parametrize("path", ["/", "/events", "/health/ready", "/v2/events"])
def test_no_other_endpoint_exists(base_url_and_stats: tuple[str, IngestStats], path: str) -> None:
    base_url, _ = base_url_and_stats
    with pytest.raises(urllib.error.HTTPError) as error:
        urllib.request.urlopen(f"{base_url}{path}", timeout=2)
    assert error.value.code == 404


def test_health_reports_the_closed_trades_builder(tmp_path: Path) -> None:
    from journal_service.storage import Store
    from journal_service.trades import TradesStats

    db_path = tmp_path / "j.sqlite3"
    Store(db_path).close()
    trades = TradesStats(abi_configured=False)
    trades.record_pass(1234, ["abi_not_configured"])
    server = build_server("127.0.0.1", 0, "runtime", IngestStats(), db_path, trades)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/health"
        with urllib.request.urlopen(url, timeout=2) as response:
            assert response.status == 200
            body = json.loads(response.read())
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    assert body["closed_trades"] == {
        "abi_configured": False,
        "complete": 0,
        "incomplete": 0,
        "last_pass_at_ms": 1234,
        "last_error": "abi_not_configured",
    }
    assert body["status"] == "ok"
