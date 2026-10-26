"""Random-walk market data, for trying the bot without an internet connection.

Prices follow a geometric Brownian motion. Live mode runs faster than
real time: each candle lasts `bar_seconds` of wall-clock time.
"""

from __future__ import annotations

import asyncio
import math
import random
import time
from typing import AsyncIterator

from ..models import Candle, interval_ms


class SyntheticFeed:
    def __init__(
        self,
        symbol: str = "SYNTH",
        interval: str = "1m",
        start_price: float = 2000.0,
        volatility: float = 0.002,  # per-candle standard deviation of returns
        seed: int | None = 42,
        bar_seconds: float = 2.0,
        ticks_per_bar: int = 4,
    ) -> None:
        self.symbol = symbol
        self.interval = interval
        self.bar_ms = interval_ms(interval)
        self.start_price = start_price
        self.volatility = volatility
        self.seed = seed
        self.bar_seconds = bar_seconds
        self.ticks_per_bar = max(1, ticks_per_bar)
        self._rng = random.Random(seed)
        self._price = start_price
        self._next_time: int | None = None

    def _candle(self, t: int) -> Candle:
        rng = self._rng
        open_ = self._price
        # Regime-like drift so trends and ranges both appear.
        drift = 0.0003 * math.sin(t / (self.bar_ms * 180))
        close = open_ * math.exp(rng.gauss(drift, self.volatility))
        wick = abs(rng.gauss(0, self.volatility / 2))
        high = max(open_, close) * (1 + wick)
        low = min(open_, close) * (1 - wick)
        self._price = close
        return Candle(t, open_, high, low, close, rng.uniform(5, 50), True)

    def generate(self, count: int, end_ms: int | None = None) -> list[Candle]:
        end_ms = end_ms or int(time.time() * 1000)
        first = (end_ms // self.bar_ms - count) * self.bar_ms
        candles = [self._candle(first + i * self.bar_ms) for i in range(count)]
        self._next_time = first + count * self.bar_ms
        return candles

    async def history(self, limit: int = 500) -> list[Candle]:
        return self.generate(limit)

    async def range(self, start_ms: int, end_ms: int) -> list[Candle]:
        count = max(0, (end_ms - start_ms) // self.bar_ms)
        return self.generate(count, end_ms=start_ms + count * self.bar_ms)

    async def stream(self) -> AsyncIterator[Candle]:
        if self._next_time is None:
            self._next_time = (int(time.time() * 1000) // self.bar_ms) * self.bar_ms
        tick = self.bar_seconds / self.ticks_per_bar
        while True:
            final = self._candle(self._next_time)
            # Emit a few partial updates before the candle closes, like a real feed.
            for i in range(1, self.ticks_per_bar):
                frac = i / self.ticks_per_bar
                price = final.open + (final.close - final.open) * frac
                yield Candle(
                    final.time, final.open,
                    max(final.open, price), min(final.open, price), price,
                    final.volume * frac, closed=False,
                )
                await asyncio.sleep(tick)
            await asyncio.sleep(tick)
            yield final
            self._next_time += self.bar_ms
