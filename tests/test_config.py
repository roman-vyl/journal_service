from pathlib import Path

import pytest

from journal_service.config import Config


def test_defaults_and_required_paths() -> None:
    config = Config.from_env(
        {"JOURNAL_RUNTIME_SOURCE_PATH": "/in/runtime.jsonl", "JOURNAL_DB_PATH": "/db/j.sqlite3"}
    )
    assert config.runtime_source_path == Path("/in/runtime.jsonl")
    assert config.db_path == Path("/db/j.sqlite3")
    assert (config.poll_interval_s, config.batch_size, config.port) == (1.0, 1000, 8097)


def test_overrides() -> None:
    config = Config.from_env(
        {
            "JOURNAL_RUNTIME_SOURCE_PATH": "a",
            "JOURNAL_DB_PATH": "b",
            "JOURNAL_POLL_INTERVAL_S": "0.25",
            "JOURNAL_BATCH_SIZE": "50",
            "JOURNAL_PORT": "9000",
            "JOURNAL_HOST": "127.0.0.1",
        }
    )
    assert (config.poll_interval_s, config.batch_size, config.port, config.host) == (
        0.25,
        50,
        9000,
        "127.0.0.1",
    )


@pytest.mark.parametrize("missing", ["JOURNAL_RUNTIME_SOURCE_PATH", "JOURNAL_DB_PATH"])
def test_missing_required_variable_is_rejected(missing: str) -> None:
    env = {"JOURNAL_RUNTIME_SOURCE_PATH": "a", "JOURNAL_DB_PATH": "b"}
    del env[missing]
    with pytest.raises(ValueError, match=missing):
        Config.from_env(env)


def test_invalid_values_are_rejected() -> None:
    base = {"JOURNAL_RUNTIME_SOURCE_PATH": "a", "JOURNAL_DB_PATH": "b"}
    with pytest.raises(ValueError):
        Config.from_env({**base, "JOURNAL_POLL_INTERVAL_S": "0"})
    with pytest.raises(ValueError):
        Config.from_env({**base, "JOURNAL_BATCH_SIZE": "0"})


def test_closed_trades_settings() -> None:
    base = {"JOURNAL_RUNTIME_SOURCE_PATH": "a", "JOURNAL_DB_PATH": "b"}
    default = Config.from_env(base)
    assert (default.abi_base_url, default.trades_interval_s) == ("", 60.0)
    config = Config.from_env(
        {**base, "JOURNAL_ABI_BASE_URL": " http://abi:8787 ", "JOURNAL_TRADES_INTERVAL_S": "5"}
    )
    assert (config.abi_base_url, config.trades_interval_s) == ("http://abi:8787", 5.0)
    with pytest.raises(ValueError):
        Config.from_env({**base, "JOURNAL_TRADES_INTERVAL_S": "0"})
