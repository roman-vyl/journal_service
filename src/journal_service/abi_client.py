"""Read one trade cycle from ABI's exchange-journal read API (GET only)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import quote

TIMEOUT_S = 5.0


class AbiReadError(Exception):
    """The cycle could not be read; `code` is stored as the row's `last_error`."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def fetch_cycle(base_url: str, strategy_instance_id: str, trade_cycle_id: str) -> dict[str, Any]:
    url = (
        f"{base_url.rstrip('/')}/v1/strategy-instances/{quote(strategy_instance_id, safe='')}"
        f"/trade-cycles/{quote(trade_cycle_id, safe='')}/exchange-journal"
    )
    request = urllib.request.Request(url, method="GET", headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            raw = response.read()
    except urllib.error.HTTPError as error:
        raise AbiReadError(f"abi_http_{error.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise AbiReadError("abi_unavailable") from None
    try:
        body = json.loads(raw)
    except ValueError:
        raise AbiReadError("abi_bad_response") from None
    if not isinstance(body, dict):
        raise AbiReadError("abi_bad_response")
    return body
