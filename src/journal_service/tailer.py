"""Read-only tailer of one producer journal file with a persisted cursor."""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO

from journal_service.parser import EventRow, LineOutcome, parse_line
from journal_service.stats import IngestStats
from journal_service.storage import Cursor, Store

Clock = Callable[[], float]


class Tailer:
    def __init__(
        self,
        *,
        store: Store,
        source: str,
        path: Path,
        stats: IngestStats,
        batch_size: int = 1000,
        clock: Clock = time.time,
        logger: logging.Logger | None = None,
    ) -> None:
        self._store = store
        self._source = source
        self._path = path
        self._stats = stats
        self._batch_size = batch_size
        self._clock = clock
        self._logger = logger or logging.getLogger(__name__)
        self._missing_logged = False

    def poll_once(self) -> int:
        """Ingest every complete line that is not yet stored. Returns rows newly stored."""

        try:
            handle = self._path.open("rb")
        except FileNotFoundError:
            if not self._missing_logged:
                self._logger.warning("Journal source %s does not exist yet", self._path)
                self._missing_logged = True
            return 0
        self._missing_logged = False
        with handle:
            info = os.fstat(handle.fileno())
            offset = self._resume_offset(info.st_dev, info.st_ino, info.st_size)
            handle.seek(offset)
            stored_total = 0
            while True:
                batch = self._read_batch(handle, offset)
                if batch is None:
                    return stored_total
                rows, skipped, malformed, new_offset = batch
                cursor = Cursor(info.st_dev, info.st_ino, new_offset)
                stored = self._store.commit_batch(
                    source=self._source,
                    rows=rows,
                    cursor=cursor,
                    ingested_at_ms=int(self._clock() * 1000),
                )
                self._stats.record_batch(
                    cursor_offset=new_offset,
                    stored=stored,
                    skipped=skipped,
                    malformed=malformed,
                    last_occurred_at=rows[-1].occurred_at if rows else None,
                )
                stored_total += stored
                offset = new_offset

    def _resume_offset(self, dev: int, ino: int, size: int) -> int:
        cursor = self._store.get_cursor(self._source)
        if cursor is None:
            return 0
        if (cursor.file_dev, cursor.file_ino) != (dev, ino):
            self._logger.warning(
                "Journal source %s changed identity; re-reading from offset 0", self._path
            )
            return 0
        if size < cursor.offset:
            self._logger.warning(
                "Journal source %s is shorter than the stored cursor; re-reading from offset 0",
                self._path,
            )
            return 0
        return cursor.offset

    def _read_batch(
        self, handle: BinaryIO, offset: int
    ) -> tuple[list[EventRow], int, int, int] | None:
        """Read up to ``batch_size`` complete lines; ``None`` when nothing complete remains."""

        rows: list[EventRow] = []
        skipped = malformed = lines = 0
        position = offset
        while lines < self._batch_size:
            raw = handle.readline()
            if not raw.endswith(b"\n"):
                break  # end of file or a partial last line: wait for the producer
            position += len(raw)
            lines += 1
            parsed = parse_line(raw[:-1])
            if parsed.outcome is LineOutcome.ACCEPTED:
                assert parsed.row is not None
                rows.append(parsed.row)
            elif parsed.outcome is LineOutcome.SKIPPED:
                skipped += 1
            else:
                malformed += 1
                self._logger.warning(
                    "Malformed journal line at byte %d of %s: %s",
                    position - len(raw),
                    self._path,
                    parsed.reason,
                )
        if lines == 0:
            return None
        return rows, skipped, malformed, position
