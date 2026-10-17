"""HTTP surface: GET /health and the read API (GET /v1/events, GET /v1/strategy-instances)."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from journal_service.query import InvalidQuery, events_for_instance, list_strategy_instances
from journal_service.stats import IngestStats


def build_server(
    host: str, port: int, source: str, stats: IngestStats, db_path: Path
) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            url = urlsplit(self.path)
            if url.path == "/v1/events" or url.path == "/v1/strategy-instances":
                self._read_api(url.path, dict(parse_qsl(url.query)))
                return
            if self.path != "/health":
                self._respond(404, {"error": "not found"})
                return
            snapshot = stats.snapshot()
            self._respond(
                200,
                {
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
                },
            )

        def _read_api(self, path: str, params: dict[str, str]) -> None:
            try:
                if path == "/v1/events":
                    self._respond(200, events_for_instance(db_path, params))
                else:
                    self._respond(200, list_strategy_instances(db_path))
            except InvalidQuery as error:
                self._respond(400, {"error": str(error)})

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
