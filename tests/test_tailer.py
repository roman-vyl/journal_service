import os
import sqlite3
from pathlib import Path

import pytest

from journal_service.parser import EventRow
from journal_service.stats import IngestStats
from journal_service.storage import Cursor, Store
from journal_service.tailer import Tailer
from tests.support import ENTRY, append, dump, live_entry

SOURCE = "runtime"


class Rig:
    def __init__(self, tmp_path: Path, batch_size: int = 1000) -> None:
        self.journal = tmp_path / "strategy-runtime" / "journal" / "runtime.jsonl"
        self.journal.parent.mkdir(parents=True)
        self.db_path = tmp_path / "journal" / "journal.sqlite3"
        self.batch_size = batch_size
        self.open()

    def open(self) -> None:
        self.store = Store(self.db_path)
        self.stats = IngestStats()
        self.tailer = Tailer(
            store=self.store,
            source=SOURCE,
            path=self.journal,
            stats=self.stats,
            batch_size=self.batch_size,
            clock=lambda: 1_700_000_000.0,
        )

    def restart(self) -> None:
        self.store.close()
        self.open()

    def rows(self) -> list[sqlite3.Row]:
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        try:
            return db.execute("SELECT * FROM events ORDER BY rowid").fetchall()
        finally:
            db.close()


@pytest.fixture
def rig(tmp_path: Path) -> Rig:
    return Rig(tmp_path)


def test_null_and_non_null_events_become_rows(rig: Rig) -> None:
    with_entry = live_entry("e1", 1000, desired_entry=ENTRY)
    without_entry = live_entry("e2", 1300)
    append(rig.journal, with_entry, without_entry)

    assert rig.tailer.poll_once() == 2

    first, second = rig.rows()
    assert (first["source"], first["event_id"]) == (SOURCE, "e1")
    assert first["event_type"] == "live_entry_evaluated"
    assert first["schema_version"] == 2
    assert first["strategy_instance_id"] == "ema_pullback:abc"
    assert first["trade_cycle_id"] is None
    assert first["bar_open_time_ms"] == 1000
    assert first["occurred_at"] == with_entry["occurred_at"]
    assert first["body"] == dump(with_entry)
    assert first["ingested_at_ms"] == 1_700_000_000_000
    assert second["body"] == dump(without_entry)
    assert '"desired_entry":null' in second["body"]


def test_envelope_source_never_reaches_the_source_column(rig: Rig) -> None:
    append(rig.journal, live_entry("e1"))
    rig.tailer.poll_once()
    (row,) = rig.rows()
    assert row["source"] == SOURCE
    assert "strategy_runtime.committed_bar_orchestrator" in row["body"]


def test_structurally_invalid_events_are_skipped_and_counted(rig: Rig) -> None:
    broken = live_entry("e3")
    del broken["strategy_instance_id"]
    wrong_bar = live_entry("e4")
    wrong_bar["payload"]["bar_open_time_ms"] = "1000"
    empty_payload = live_entry("e5", payload={})
    append(rig.journal, live_entry("e1"), "not json at all", broken, wrong_bar, empty_payload)
    append(rig.journal, live_entry("e2", 1300))

    assert rig.tailer.poll_once() == 2

    assert [row["event_id"] for row in rig.rows()] == ["e1", "e2"]
    snapshot = rig.stats.snapshot()
    assert snapshot.malformed_count == 4
    assert snapshot.stored_count == 2


def test_meaningless_desired_entry_is_stored_unchanged(rig: Rig) -> None:
    record = live_entry("e1", desired_entry={"unexpected": ["shape", 1]})
    append(rig.journal, record)
    rig.tailer.poll_once()
    (row,) = rig.rows()
    assert row["body"] == dump(record)


def test_unrelated_and_old_events_are_skipped_and_the_cursor_advances(rig: Rig) -> None:
    started = {
        "schema_version": 1,
        "event_id": "x1",
        "event_type": "committed_bar_orchestration_started",
        "occurred_at": "2026-10-16T12:00:00Z",
        "payload": {},
    }
    append(rig.journal, started, live_entry("old", schema_version=1), started)

    assert rig.tailer.poll_once() == 0

    assert rig.rows() == []
    assert rig.stats.snapshot().skipped_count == 3
    cursor = rig.store.get_cursor(SOURCE)
    assert cursor is not None
    assert cursor.offset == rig.journal.stat().st_size
    assert rig.tailer.poll_once() == 0
    assert rig.stats.snapshot().skipped_count == 3


def test_partial_last_line_waits_until_complete(rig: Rig) -> None:
    complete = dump(live_entry("e1"))
    second = dump(live_entry("e2", 1300))
    append(rig.journal, complete)
    with rig.journal.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(second[:30])

    assert rig.tailer.poll_once() == 1
    cursor = rig.store.get_cursor(SOURCE)
    assert cursor is not None
    assert cursor.offset == len(complete) + 1
    assert rig.tailer.poll_once() == 0

    with rig.journal.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(second[30:] + "\n")

    assert rig.tailer.poll_once() == 1
    assert [row["event_id"] for row in rig.rows()] == ["e1", "e2"]


def test_restart_resumes_from_the_cursor_without_gaps_or_duplicates(rig: Rig) -> None:
    append(rig.journal, live_entry("e1", 1000), live_entry("e2", 1300))
    assert rig.tailer.poll_once() == 2

    rig.restart()
    assert rig.tailer.poll_once() == 0
    append(rig.journal, live_entry("e3", 1600))
    rig.restart()
    assert rig.tailer.poll_once() == 1

    assert [row["event_id"] for row in rig.rows()] == ["e1", "e2", "e3"]
    assert rig.stats.snapshot().stored_count == 1


def test_duplicate_event_id_is_stored_once(rig: Rig) -> None:
    record = live_entry("e1")
    append(rig.journal, record, record)

    assert rig.tailer.poll_once() == 1
    assert len(rig.rows()) == 1


def test_same_bar_twice_with_different_event_ids_gives_two_rows(rig: Rig) -> None:
    append(rig.journal, live_entry("e1", 1000), live_entry("e2", 1000))
    assert rig.tailer.poll_once() == 2
    assert [row["bar_open_time_ms"] for row in rig.rows()] == [1000, 1000]


def test_replaced_file_is_re_read_from_zero_without_duplicates(rig: Rig) -> None:
    append(rig.journal, live_entry("e1", 1000), live_entry("e2", 1300))
    rig.tailer.poll_once()
    old_inode = rig.journal.stat().st_ino

    replacement = rig.journal.with_name("runtime.jsonl.new")
    append(replacement, live_entry("e2", 1300), live_entry("e3", 1600))
    os.replace(replacement, rig.journal)
    assert rig.journal.stat().st_ino != old_inode

    assert rig.tailer.poll_once() == 1
    assert [row["event_id"] for row in rig.rows()] == ["e1", "e2", "e3"]


def test_truncated_file_is_re_read_from_zero_without_duplicates(rig: Rig) -> None:
    append(rig.journal, live_entry("e1", 1000), live_entry("e2", 1300))
    rig.tailer.poll_once()

    rig.journal.write_text(dump(live_entry("e3", 1600)) + "\n", encoding="utf-8")

    assert rig.tailer.poll_once() == 1
    assert [row["event_id"] for row in rig.rows()] == ["e1", "e2", "e3"]


def test_missing_source_file_is_not_an_error(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    assert rig.tailer.poll_once() == 0
    append(rig.journal, live_entry("e1"))
    assert rig.tailer.poll_once() == 1


def test_large_file_is_ingested_in_batches_with_the_cursor_following(tmp_path: Path) -> None:
    rig = Rig(tmp_path, batch_size=7)
    append(rig.journal, *(live_entry(f"e{i}", i) for i in range(50)))
    append(rig.journal, *({"event_type": "other", "schema_version": 1} for _ in range(20)))

    assert rig.tailer.poll_once() == 50

    assert len(rig.rows()) == 50
    snapshot = rig.stats.snapshot()
    assert snapshot.skipped_count == 20
    assert snapshot.cursor_offset == rig.journal.stat().st_size
    assert snapshot.last_occurred_at == live_entry("e49", 49)["occurred_at"]


def test_a_very_long_line_is_read_whole(rig: Rig) -> None:
    record = live_entry("e1", desired_entry={"blob": "x" * 2_000_000})
    append(rig.journal, record)
    assert rig.tailer.poll_once() == 1
    (row,) = rig.rows()
    assert len(row["body"]) == len(dump(record))


def test_failed_transaction_leaves_neither_rows_nor_cursor(rig: Rig) -> None:
    good = EventRow("e1", "live_entry_evaluated", 2, "t", "inst", None, 1, "{}")
    broken_cursor = Cursor(1, 2, None)  # type: ignore[arg-type]

    with pytest.raises(sqlite3.IntegrityError):
        rig.store.commit_batch(source=SOURCE, rows=[good], cursor=broken_cursor, ingested_at_ms=1)

    assert rig.rows() == []
    assert rig.store.get_cursor(SOURCE) is None


def test_cursor_is_stored_per_source_with_file_identity(rig: Rig) -> None:
    append(rig.journal, live_entry("e1"))
    rig.tailer.poll_once()
    info = rig.journal.stat()
    assert rig.store.get_cursor(SOURCE) == Cursor(info.st_dev, info.st_ino, info.st_size)
    assert rig.store.get_cursor("abi") is None


def test_database_runs_in_wal_mode_with_the_expected_indexes(rig: Rig) -> None:
    db = sqlite3.connect(rig.db_path)
    try:
        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        names = {row[1] for row in db.execute("PRAGMA index_list(events)")}
    finally:
        db.close()
    assert {
        "events_instance_time",
        "events_instance_bar",
        "events_instance_cycle",
        "events_type_time",
    } <= names


def test_stats_resume_values_come_from_the_database(rig: Rig) -> None:
    append(rig.journal, live_entry("e1", 1000), live_entry("e2", 1300))
    rig.tailer.poll_once()
    assert rig.store.last_occurred_at(SOURCE) == live_entry("e2", 1300)["occurred_at"]
