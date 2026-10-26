"""Core data types shared across the bot."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum


class Action(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass(frozen=True)
class Candle:
    """One OHLCV bar. `time` is the open time in milliseconds (UTC)."""

    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    closed: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Fill:
    """A simulated order execution."""

    time: int
    side: Action
    price: float
    quantity: float
    fee: float
    reason: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["side"] = self.side.value
        return d


@dataclass(frozen=True)
class Trade:
    """A closed round trip: one buy followed by one sell."""

    entry_time: int
    exit_time: int
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    return_pct: float

    def to_dict(self) -> dict:
        return asdict(self)


INTERVAL_MS = {
    "1m": 60_000,
    "3m": 3 * 60_000,
    "5m": 5 * 60_000,
    "15m": 15 * 60_000,
    "30m": 30 * 60_000,
    "1h": 3_600_000,
    "2h": 2 * 3_600_000,
    "4h": 4 * 3_600_000,
    "6h": 6 * 3_600_000,
    "12h": 12 * 3_600_000,
    "1d": 86_400_000,
}


def interval_ms(interval: str) -> int:
    try:
        return INTERVAL_MS[interval]
    except KeyError:
        raise ValueError(
            f"Intervalo no soportado: {interval!r}. Usa uno de: {', '.join(INTERVAL_MS)}"
        ) from None
