"""Read and write candles as CSV (columns: time,open,high,low,close,volume).

`time` is the candle open time in milliseconds since epoch (UTC).
"""

from __future__ import annotations

import csv
from pathlib import Path

from ..models import Candle

FIELDS = ["time", "open", "high", "low", "close", "volume"]


def save_csv(path: str | Path, candles: list[Candle]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(FIELDS)
        for c in candles:
            writer.writerow([c.time, c.open, c.high, c.low, c.close, c.volume])


def load_csv(path: str | Path) -> list[Candle]:
    with Path(path).open(newline="") as f:
        return [
            Candle(
                time=int(float(row["time"])),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row.get("volume") or 0),
            )
            for row in csv.DictReader(f)
        ]


class CsvFeed:
    """Historical candles from a CSV file (backtests only)."""

    def __init__(self, path: str | Path) -> None:
        self.candles = sorted(load_csv(path), key=lambda c: c.time)

    async def history(self, limit: int = 500) -> list[Candle]:
        return self.candles[-limit:]

    async def range(self, start_ms: int, end_ms: int) -> list[Candle]:
        return [c for c in self.candles if start_ms <= c.time < end_ms]

    async def stream(self):
        raise NotImplementedError("Un archivo CSV no tiene datos en tiempo real")
        yield  # pragma: no cover
