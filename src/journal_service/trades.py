"""Closed-trades builder: detects stored closures and assembles their rows.

It reads only this service's database and one ABI read route per cycle. Formulas are
those of OpenSpec `journal-closed-trades-table-v1`; decimal arithmetic, stored as text.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from collections.abc import Callable, Sequence
from contextlib import closing
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from threading import Lock
from typing import Any

from journal_service.abi_client import AbiReadError

_LOGGER = logging.getLogger("journal_service.trades")

INCOMPLETE = "incomplete"
COMPLETE = "complete"
ENTRY_ROLES = frozenset({"entry"})
EXIT_ROLES = frozenset({"close", "stop_loss", "take_profit"})

FetchCycle = Callable[[str, str, str], dict[str, Any]]


class TradeIncomplete(Exception):
    """The row cannot be completed yet; `code` is stored as `last_error`."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class Plan:
    entry_price: Decimal | None = None
    initial_stop: Decimal | None = None
    initial_take: Decimal | None = None
    last_stop: Decimal | None = None
    last_take: Decimal | None = None


@dataclass(frozen=True, slots=True)
class Fill:
    price: Decimal
    qty: Decimal
    fee: Decimal
    time_ms: int


class TradesStats:
    """Builder state shown by /health."""

    def __init__(self, *, abi_configured: bool) -> None:
        self._lock = Lock()
        self.abi_configured = abi_configured
        self._last_pass_at_ms: int | None = None
        self._last_error: str | None = None

    def record_pass(self, at_ms: int, errors: Sequence[str]) -> None:
        with self._lock:
            self._last_pass_at_ms = at_ms
            if errors:
                self._last_error = errors[-1]

    def snapshot(self) -> tuple[int | None, str | None]:
        with self._lock:
            return self._last_pass_at_ms, self._last_error


def _decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _text(value: Decimal | None) -> str | None:
    return None if value is None else format(value.normalize(), "f")


def _plan(bodies: Sequence[dict[str, Any]]) -> Plan:
    applied = [b["payload"] for b in bodies if b.get("event_type") == "entry_package_applied"]
    protections = [b["payload"] for b in bodies if b.get("event_type") == "protection_applied"]
    if not applied:
        return Plan()
    last = applied[-1]
    initial_stop = _decimal(last.get("stop_loss"))
    initial_take = _decimal(last.get("take_profit"))
    last_stop, last_take = initial_stop, initial_take
    if protections:
        confirmed = protections[-1].get("confirmed_protection") or {}
        last_stop = _decimal(confirmed.get("stop_price"))
        last_take = _decimal(confirmed.get("take_price"))
    return Plan(
        _decimal(last.get("trigger_price")), initial_stop, initial_take, last_stop, last_take
    )


def _fill(raw: dict[str, Any]) -> Fill:
    price, qty, fee = (_decimal(raw.get(k)) for k in ("execPrice", "execQty", "execFee"))
    if price is None or qty is None or fee is None:
        raise TradeIncomplete("abi_bad_response")
    return Fill(price, qty, fee, int(raw["execTime"]))


def assemble(
    cycle: dict[str, Any], closing_order_id: str, close_reason: str, plan: Plan
) -> dict[str, Any]:
    """Return every column of a complete row, or raise TradeIncomplete."""

    try:
        return _assemble(cycle, closing_order_id, close_reason, plan)
    except (KeyError, TypeError, ValueError, AttributeError, InvalidOperation):
        raise TradeIncomplete("abi_bad_response") from None


def _assemble(
    cycle: dict[str, Any], closing_order_id: str, close_reason: str, plan: Plan
) -> dict[str, Any]:
    orders = cycle["orders"]
    if cycle.get("truncated") or any(o.get("truncated") for o in orders):
        raise TradeIncomplete("abi_truncated")
    entry: list[Fill] = []
    exits: list[Fill] = []
    symbol: str | None = None
    entry_side: str | None = None
    closing_filled = closing_executed = False
    for order in orders:
        role = order["link"]["role"]
        order_id = order["link"]["order_id"]
        for event in order["events"]:
            if order_id == closing_order_id and event["fact_kind"] == "order_state":
                closing_filled = closing_filled or event["order_status"] == "Filled"
            if event["fact_kind"] != "execution" or event["exec_type"] != "Trade":
                continue
            fill = _fill(event["raw"])
            if role in ENTRY_ROLES:
                entry.append(fill)
                symbol = symbol or event["symbol"]
                entry_side = entry_side or event["raw"]["side"]
            elif role in EXIT_ROLES:
                exits.append(fill)
                closing_executed = closing_executed or order_id == closing_order_id
    if not entry:
        raise TradeIncomplete("no_entry_execution")
    if not (closing_filled and closing_executed):
        raise TradeIncomplete("closing_order_not_filled")
    if entry_side not in ("Buy", "Sell"):
        raise TradeIncomplete("abi_bad_response")
    s = Decimal(1) if entry_side == "Buy" else Decimal(-1)

    entry_qty = sum((f.qty for f in entry), Decimal(0))
    exit_qty = sum((f.qty for f in exits), Decimal(0))
    entry_avg = sum((f.price * f.qty for f in entry), Decimal(0)) / entry_qty
    exit_avg = sum((f.price * f.qty for f in exits), Decimal(0)) / exit_qty
    entry_fee = sum((f.fee for f in entry), Decimal(0))
    exit_fee = sum((f.fee for f in exits), Decimal(0))
    opened_at = min(f.time_ms for f in entry)
    closed_at = max(f.time_ms for f in exits)
    notional = entry_avg * entry_qty
    gross = s * (exit_avg - entry_avg) * exit_qty
    fees = entry_fee + exit_fee
    net = gross - fees

    risk = r_multiple = entry_slip = exit_slip = None
    if plan.initial_stop is not None:
        risk = abs(entry_avg - plan.initial_stop) * exit_qty
        r_multiple = net / risk if risk != 0 else None
    if plan.entry_price:
        entry_slip = s * (entry_avg - plan.entry_price) / plan.entry_price * 100
    planned_exit = {"stop_loss": plan.last_stop, "take_profit": plan.last_take}.get(close_reason)
    if planned_exit:
        exit_slip = s * (planned_exit - exit_avg) / planned_exit * 100

    return {
        "symbol": symbol,
        "side": "long" if entry_side == "Buy" else "short",
        "opened_at_ms": opened_at,
        "entry_avg_price": _text(entry_avg),
        "entry_qty": _text(entry_qty),
        "entry_notional_usdt": _text(notional),
        "entry_fill_count": len(entry),
        "entry_fee_usdt": _text(entry_fee),
        "closed_at_ms": closed_at,
        "exit_avg_price": _text(exit_avg),
        "exit_qty": _text(exit_qty),
        "exit_fill_count": len(exits),
        "exit_fee_usdt": _text(exit_fee),
        "duration_ms": closed_at - opened_at,
        "planned_entry_price": _text(plan.entry_price),
        "planned_initial_stop": _text(plan.initial_stop),
        "planned_initial_take": _text(plan.initial_take),
        "last_stop": _text(plan.last_stop),
        "last_take": _text(plan.last_take),
        "gross_pnl_usdt": _text(gross),
        "fees_usdt": _text(fees),
        "net_pnl_usdt": _text(net),
        "price_return_pct": _text(s * (exit_avg / entry_avg - 1) * 100),
        "net_return_pct": _text(net / notional * 100),
        "risk_usdt": _text(risk),
        "r_multiple": _text(r_multiple),
        "entry_slippage_pct": _text(entry_slip),
        "exit_slippage_pct": _text(exit_slip),
    }


class TradeBuilder:
    """One pass: create rows for new closures, then try to complete every incomplete row."""

    def __init__(
        self,
        db_path: Path,
        abi_base_url: str,
        stats: TradesStats,
        fetch: FetchCycle,
        clock_ms: Callable[[], int] = lambda: int(time.time() * 1000),
    ) -> None:
        self._db_path = db_path
        self._abi_base_url = abi_base_url
        self._stats = stats
        self._fetch = fetch
        self._clock_ms = clock_ms

    def run_pass(self) -> None:
        now = self._clock_ms()
        errors: list[str] = []
        with closing(sqlite3.connect(self._db_path, isolation_level=None, timeout=5)) as db:
            self._detect(db, now)
            pending = db.execute(
                "SELECT strategy_instance_id, trade_cycle_id, closing_order_id, close_reason "
                "FROM closed_trades WHERE status = ? ORDER BY created_at_ms, rowid",
                (INCOMPLETE,),
            ).fetchall()
            for sid, cid, closing_order_id, reason in pending:
                error = self._build(db, sid, cid, closing_order_id, reason)
                if error is not None:
                    errors.append(error)
        self._stats.record_pass(now, errors)

    def _detect(self, db: sqlite3.Connection, now: int) -> None:
        rows = db.execute(
            "SELECT e.event_id, e.strategy_instance_id, e.trade_cycle_id, e.body FROM events e "
            "WHERE e.event_type = 'trade_cycle_closed' AND NOT EXISTS (SELECT 1 FROM "
            "closed_trades t WHERE t.strategy_instance_id = e.strategy_instance_id "
            "AND t.trade_cycle_id = e.trade_cycle_id) ORDER BY e.rowid"
        ).fetchall()
        for event_id, sid, cid, body in rows:
            payload = json.loads(body).get("payload", {})
            reason, order_id = payload.get("reason"), payload.get("order_id")
            if not isinstance(reason, str) or not isinstance(order_id, str) or not order_id:
                _LOGGER.warning("trade_cycle_closed %s has no reason or order_id", event_id)
                continue
            # The first closure of a pair wins: later ones hit the primary key and are ignored.
            db.execute(
                "INSERT OR IGNORE INTO closed_trades (strategy_instance_id, trade_cycle_id, "
                "close_reason, close_event_id, closing_order_id, status, attempts, "
                "created_at_ms) VALUES (?, ?, ?, ?, ?, ?, 0, ?)",
                (sid, cid, reason, event_id, order_id, INCOMPLETE, now),
            )

    def _build(
        self, db: sqlite3.Connection, sid: str, cid: str, closing_order_id: str, reason: str
    ) -> str | None:
        now = self._clock_ms()
        try:
            if not self._abi_base_url:
                raise TradeIncomplete("abi_not_configured")
            bodies = [
                json.loads(r[0])
                for r in db.execute(
                    "SELECT body FROM events WHERE strategy_instance_id = ? AND trade_cycle_id = ? "
                    "AND event_type IN ('entry_package_applied', 'protection_applied') "
                    "ORDER BY rowid",
                    (sid, cid),
                )
            ]
            try:
                cycle = self._fetch(self._abi_base_url, sid, cid)
            except AbiReadError as error:
                raise TradeIncomplete(error.code) from None
            columns = assemble(cycle, closing_order_id, reason, _plan(bodies))
        except TradeIncomplete as incomplete:
            db.execute(
                "UPDATE closed_trades SET attempts = attempts + 1, last_attempt_at_ms = ?, "
                "last_error = ? WHERE strategy_instance_id = ? AND trade_cycle_id = ? "
                "AND status = ?",
                (now, incomplete.code, sid, cid, INCOMPLETE),
            )
            return incomplete.code
        names = list(columns)
        db.execute(
            "UPDATE closed_trades SET "
            + ", ".join(f"{name} = ?" for name in names)
            + ", status = ?, completed_at_ms = ?, attempts = attempts + 1, "
            "last_attempt_at_ms = ?, last_error = NULL "
            "WHERE strategy_instance_id = ? AND trade_cycle_id = ? AND status = ?",
            [columns[n] for n in names] + [COMPLETE, now, now, sid, cid, INCOMPLETE],
        )
        return None


def closed_trade_counts(db_path: Path) -> dict[str, int]:
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)
    try:
        rows = db.execute("SELECT status, COUNT(*) FROM closed_trades GROUP BY status").fetchall()
    finally:
        db.close()
    counts = {COMPLETE: 0, INCOMPLETE: 0}
    counts.update({status: count for status, count in rows})
    return counts
