"""The only HTTP surface of this change: GET /health."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from journal_service.stats import IngestStats


def build_server(host: str, port: int, source: str, stats: IngestStats) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
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
