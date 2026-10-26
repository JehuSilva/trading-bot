from __future__ import annotations

from typing import AsyncIterator, Protocol

from ..models import Candle
from .binance import BinanceFeed
from .csvfile import CsvFeed, load_csv, save_csv
from .synthetic import SyntheticFeed


class Feed(Protocol):
    async def history(self, limit: int = 500) -> list[Candle]: ...

    async def range(self, start_ms: int, end_ms: int) -> list[Candle]: ...

    def stream(self) -> AsyncIterator[Candle]: ...


__all__ = ["BinanceFeed", "CsvFeed", "Feed", "SyntheticFeed", "load_csv", "save_csv"]
