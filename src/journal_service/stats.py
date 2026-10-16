"""Thread-safe ingest counters shared by the tailer and the health endpoint."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock


@dataclass(frozen=True, slots=True)
class StatsSnapshot:
    cursor_offset: int
    last_occurred_at: str | None
    stored_count: int
    skipped_count: int
    malformed_count: int


class IngestStats:
    """Counters since process start; cursor offset and last occurred_at resume from the DB."""

    def __init__(self, *, cursor_offset: int = 0, last_occurred_at: str | None = None) -> None:
        self._lock = Lock()
        self._cursor_offset = cursor_offset
        self._last_occurred_at = last_occurred_at
        self._stored = 0
        self._skipped = 0
        self._malformed = 0

    def record_batch(
        self,
        *,
        cursor_offset: int,
        stored: int,
        skipped: int,
        malformed: int,
        last_occurred_at: str | None,
    ) -> None:
        with self._lock:
            self._cursor_offset = cursor_offset
            self._stored += stored
            self._skipped += skipped
            self._malformed += malformed
            if last_occurred_at is not None:
                self._last_occurred_at = last_occurred_at

    def snapshot(self) -> StatsSnapshot:
        with self._lock:
            return StatsSnapshot(
                cursor_offset=self._cursor_offset,
                last_occurred_at=self._last_occurred_at,
                stored_count=self._stored,
                skipped_count=self._skipped,
                malformed_count=self._malformed,
            )
