"""HTTP surface: GET /health and the read API (GET /v1/events, GET /v1/strategy-instances,
GET /v1/closed-trades, GET /v1/closed-trades/{strategy_instance_id}/{trade_cycle_id})."""

from __future__ import annotations

import json
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, unquote, urlsplit

from journal_service.query import InvalidQuery, events_for_instance, list_strategy_instances
from journal_service.stats import IngestStats
from journal_service.trades import TradesStats, closed_trade_counts
from journal_service.trades_query import closed_trade, list_closed_trades

_TRADES_PATH = "/v1/closed-trades"


def _trades_block(trades: TradesStats, db_path: Path) -> dict[str, Any]:
    last_pass_at_ms, last_error = trades.snapshot()
    try:
        counts: dict[str, int | None] = dict(closed_trade_counts(db_path))
    except sqlite3.Error:
        counts = {"complete": None, "incomplete": None}
    return {
        "abi_configured": trades.abi_configured,
        "complete": counts["complete"],
        "incomplete": counts["incomplete"],
        "last_pass_at_ms": last_pass_at_ms,
        "last_error": last_error,
    }


def build_server(
    host: str,
    port: int,
    source: str,
    stats: IngestStats,
    db_path: Path,
    trades: TradesStats | None = None,
) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            url = urlsplit(self.path)
            if url.path == "/v1/events" or url.path == "/v1/strategy-instances":
                self._read_api(url.path, dict(parse_qsl(url.query)))
                return
            if url.path == _TRADES_PATH:
                self._trades_list(dict(parse_qsl(url.query, keep_blank_values=True)))
                return
            if url.path.startswith(_TRADES_PATH + "/"):
                self._trade_one(url.path[len(_TRADES_PATH) + 1 :])
                return
            if self.path != "/health":
                self._respond(404, {"error": "not found"})
                return
            snapshot = stats.snapshot()
            body: dict[str, Any] = {
                "status": "ok",
                "sources": {
                    source: {
                        "cursor_offset": snapshot.cursor_offset,
                        "last_ingested_occurred_at": snapshot.last_occurred_at,
                    }
                },
                "stored_count": snapshot.stored_count,
                "skipped_count": snapshot.skipped_count,
                "malformed_count": snapshot.malformed_count,
            }
            if trades is not None:
                body["closed_trades"] = _trades_block(trades, db_path)
            self._respond(200, body)

        def _read_api(self, path: str, params: dict[str, str]) -> None:
            try:
                if path == "/v1/events":
                    self._respond(200, events_for_instance(db_path, params))
                else:
                    self._respond(200, list_strategy_instances(db_path))
            except InvalidQuery as error:
                self._respond(400, {"error": str(error)})

        def _trades_list(self, params: dict[str, str]) -> None:
            try:
                self._respond(200, list_closed_trades(db_path, params))
            except InvalidQuery as error:
                self._respond(400, {"error": str(error)})

        def _trade_one(self, rest: str) -> None:
            parts = [unquote(part) for part in rest.split("/")]
            if len(parts) != 2 or not all(parts):
                self._respond(404, {"error": "not found"})
                return
            row = closed_trade(db_path, parts[0], parts[1])
            if row is None:
                self._respond(404, {"error": "closed trade not found"})
                return
            self._respond(200, {"trade": row})

        def _respond(self, status: int, body: dict[str, Any]) -> None:
            payload = json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: Any) -> None:
            return

    return ThreadingHTTPServer((host, port), Handler)
