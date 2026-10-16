"""SQLite storage: the single-owner events table and the ingest cursor."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from journal_service.parser import EventRow

_SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE events (
  source               TEXT    NOT NULL,
  event_id             TEXT    NOT NULL,
  event_type           TEXT    NOT NULL,
  schema_version       INTEGER NOT NULL,
  occurred_at          TEXT    NOT NULL,
  strategy_instance_id TEXT,
  trade_cycle_id       TEXT,
  bar_open_time_ms     INTEGER,
  body                 TEXT    NOT NULL,
  ingested_at_ms       INTEGER NOT NULL,
  PRIMARY KEY (source, event_id)
);
CREATE INDEX events_instance_time  ON events (strategy_instance_id, occurred_at);
CREATE INDEX events_instance_bar   ON events (strategy_instance_id, bar_open_time_ms);
CREATE INDEX events_instance_cycle ON events (strategy_instance_id, trade_cycle_id);
CREATE INDEX events_type_time      ON events (event_type, occurred_at);

CREATE TABLE ingest_cursor (
  source   TEXT PRIMARY KEY,
  file_dev INTEGER,
  file_ino INTEGER,
  offset   INTEGER NOT NULL
);
"""


@dataclass(frozen=True, slots=True)
class Cursor:
    file_dev: int
    file_ino: int
    offset: int


class Store:
    """Owns the journal database. Only one process may open it for writing."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        # The tailer thread is the only user after start-up.
        self._db = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=FULL")
        self._migrate()

    def _migrate(self) -> None:
        version = self._db.execute("PRAGMA user_version").fetchone()[0]
        if version == _SCHEMA_VERSION:
            return
        if version != 0:
            raise RuntimeError(f"unsupported journal database version {version}")
        self._db.execute("BEGIN IMMEDIATE")
        try:
            for statement in _SCHEMA.split(";"):
                if statement.strip():
                    self._db.execute(statement)
            self._db.execute(f"PRAGMA user_version={_SCHEMA_VERSION}")
            self._db.execute("COMMIT")
        except BaseException:
            self._db.execute("ROLLBACK")
            raise

    def get_cursor(self, source: str) -> Cursor | None:
        row = self._db.execute(
            "SELECT file_dev, file_ino, offset FROM ingest_cursor WHERE source = ?", (source,)
        ).fetchone()
        return None if row is None else Cursor(row[0], row[1], row[2])

    def last_occurred_at(self, source: str) -> str | None:
        row = self._db.execute(
            "SELECT occurred_at FROM events WHERE source = ? "
            "ORDER BY ingested_at_ms DESC, rowid DESC LIMIT 1",
            (source,),
        ).fetchone()
        return None if row is None else row[0]

    def commit_batch(
        self,
        *,
        source: str,
        rows: Sequence[EventRow],
        cursor: Cursor,
        ingested_at_ms: int,
    ) -> int:
        """Store rows idempotently and move the cursor in one transaction.

        Returns the number of newly stored rows.
        """

        self._db.execute("BEGIN IMMEDIATE")
        try:
            stored = 0
            for row in rows:
                result = self._db.execute(
                    "INSERT OR IGNORE INTO events (source, event_id, event_type, schema_version, "
                    "occurred_at, strategy_instance_id, trade_cycle_id, bar_open_time_ms, body, "
                    "ingested_at_ms) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        source,
                        row.event_id,
                        row.event_type,
                        row.schema_version,
                        row.occurred_at,
                        row.strategy_instance_id,
                        row.trade_cycle_id,
                        row.bar_open_time_ms,
                        row.body,
                        ingested_at_ms,
                    ),
                )
                stored += result.rowcount
            self._db.execute(
                "INSERT INTO ingest_cursor (source, file_dev, file_ino, offset) "
                "VALUES (?, ?, ?, ?) ON CONFLICT(source) DO UPDATE SET "
                "file_dev = excluded.file_dev, file_ino = excluded.file_ino, "
                "offset = excluded.offset",
                (source, cursor.file_dev, cursor.file_ino, cursor.offset),
            )
            self._db.execute("COMMIT")
        except BaseException:
            self._db.execute("ROLLBACK")
            raise
        return stored

    def close(self) -> None:
        self._db.close()
