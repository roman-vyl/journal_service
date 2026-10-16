"""Environment configuration of the Central Journal."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

RUNTIME_SOURCE_NAME = "runtime"


@dataclass(frozen=True, slots=True)
class Config:
    runtime_source_path: Path
    db_path: Path
    poll_interval_s: float = 1.0
    batch_size: int = 1000
    host: str = "0.0.0.0"
    port: int = 8097

    def __post_init__(self) -> None:
        if self.poll_interval_s <= 0:
            raise ValueError("poll_interval_s must be positive")
        if self.batch_size < 1:
            raise ValueError("batch_size must be at least 1")
        if not 0 <= self.port <= 65535:
            raise ValueError("port must be in 0..65535")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Config:
        values = os.environ if env is None else env
        try:
            source = values["JOURNAL_RUNTIME_SOURCE_PATH"]
            db = values["JOURNAL_DB_PATH"]
        except KeyError as exc:
            raise ValueError(f"{exc.args[0]} is required") from exc
        return cls(
            runtime_source_path=Path(source),
            db_path=Path(db),
            poll_interval_s=float(values.get("JOURNAL_POLL_INTERVAL_S", "1.0")),
            batch_size=int(values.get("JOURNAL_BATCH_SIZE", "1000")),
            host=values.get("JOURNAL_HOST", "0.0.0.0"),
            port=int(values.get("JOURNAL_PORT", "8097")),
        )
