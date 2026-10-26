"""Binance market data (public, no API key needed).

- REST `/api/v3/klines` for history and backtests.
- Websocket `<symbol>@kline_<interval>` for live candles.

If `api.binance.com` is blocked in your country, set
`rest_url = "https://data-api.binance.vision"` and
`ws_url = "wss://data-stream.binance.vision"` in the config.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import AsyncIterator

import httpx
import websockets

from ..models import Candle, interval_ms

log = logging.getLogger(__name__)

MAX_LIMIT = 1000


def parse_rest_kline(row: list, now_ms: int | None = None) -> Candle:
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    return Candle(
        time=int(row[0]),
        open=float(row[1]),
        high=float(row[2]),
        low=float(row[3]),
        close=float(row[4]),
        volume=float(row[5]),
        closed=int(row[6]) < now_ms,
    )


def parse_ws_kline(message: str | bytes | dict) -> Candle | None:
    data = json.loads(message) if isinstance(message, (str, bytes)) else message
    if "data" in data:  # combined-stream envelope
        data = data["data"]
    k = data.get("k")
    if not k:
        return None
    return Candle(
        time=int(k["t"]),
        open=float(k["o"]),
        high=float(k["h"]),
        low=float(k["l"]),
        close=float(k["c"]),
        volume=float(k["v"]),
        closed=bool(k["x"]),
    )


class BinanceFeed:
    def __init__(
        self,
        symbol: str,
        interval: str,
        rest_url: str = "https://api.binance.com",
        ws_url: str = "wss://stream.binance.com:9443",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.symbol = symbol.upper()
        self.interval = interval
        self.bar_ms = interval_ms(interval)
        self.rest_url = rest_url.rstrip("/")
        self.ws_url = ws_url.rstrip("/")
        self._client = client

    async def _klines(self, **params) -> list[Candle]:
        params = {"symbol": self.symbol, "interval": self.interval, **params}
        client = self._client or httpx.AsyncClient(timeout=20)
        try:
            resp = await client.get(f"{self.rest_url}/api/v3/klines", params=params)
            resp.raise_for_status()
            rows = resp.json()
        finally:
            if self._client is None:
                await client.aclose()
        now = int(time.time() * 1000)
        return [parse_rest_kline(r, now) for r in rows]

    async def history(self, limit: int = 500) -> list[Candle]:
        """The latest `limit` closed candles."""
        candles: list[Candle] = []
        end: int | None = None
        while len(candles) < limit:
            batch_size = min(MAX_LIMIT, limit - len(candles) + 1)
            params = {"limit": batch_size}
            if end is not None:
                params["endTime"] = end
            batch = [c for c in await self._klines(**params) if c.closed]
            if not batch:
                break
            candles = batch + [c for c in candles if c.time > batch[-1].time]
            end = batch[0].time - 1
            if len(batch) < batch_size - 1:
                break
        return candles[-limit:]

    async def range(self, start_ms: int, end_ms: int) -> list[Candle]:
        """All closed candles that open between `start_ms` and `end_ms`."""
        candles: list[Candle] = []
        cursor = start_ms
        while cursor < end_ms:
            batch = await self._klines(startTime=cursor, endTime=end_ms, limit=MAX_LIMIT)
            batch = [c for c in batch if c.closed]
            if not batch:
                break
            candles.extend(batch)
            cursor = batch[-1].time + self.bar_ms
            if len(batch) < MAX_LIMIT:
                break
        return candles

    async def stream(self) -> AsyncIterator[Candle]:
        """Live candle updates. Reconnects forever and back-fills any gap."""
        url = f"{self.ws_url}/ws/{self.symbol.lower()}@kline_{self.interval}"
        last_closed: int | None = None
        delay = 1.0
        while True:
            try:
                async with websockets.connect(url, open_timeout=15) as ws:
                    log.info("Conectado a %s", url)
                    delay = 1.0
                    if last_closed is not None:
                        # Recover candles that closed while we were disconnected.
                        for candle in await self.range(last_closed + self.bar_ms, int(time.time() * 1000)):
                            last_closed = candle.time
                            yield candle
                    async for message in ws:
                        candle = parse_ws_kline(message)
                        if candle is None:
                            continue
                        if candle.closed:
                            last_closed = candle.time
                        yield candle
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # network errors, server restarts, etc.
                log.warning("Conexión perdida (%s). Reintentando en %.0fs", exc, delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)
