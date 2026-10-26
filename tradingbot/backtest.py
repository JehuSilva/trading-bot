"""Backtests: run a strategy over historical candles."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

from .broker import PaperBroker
from .config import Config
from .engine import Engine, RiskSettings
from .feeds import BinanceFeed, CsvFeed, SyntheticFeed, load_csv, save_csv
from .models import Candle, interval_ms
from .strategies import create

log = logging.getLogger(__name__)

DAY_MS = 86_400_000


@dataclass
class BacktestRequest:
    strategy: str
    params: dict = field(default_factory=dict)
    symbol: str = "ETHUSDT"
    interval: str = "1h"
    days: float = 30
    end_ms: int | None = None
    initial_cash: float = 1000.0
    fee_rate: float = 0.001
    slippage: float = 0.0005
    risk: RiskSettings = field(default_factory=RiskSettings)


def run_backtest(req: BacktestRequest, candles: list[Candle]) -> dict:
    """Run the strategy over `candles`. The first candles are used to warm up indicators."""
    strategy = create(req.strategy, req.params)
    broker = PaperBroker(req.initial_cash, req.fee_rate, req.slippage)
    engine = Engine(
        strategy, broker, symbol=req.symbol, interval=req.interval,
        risk=req.risk, display_limit=len(candles) or 1,
    )
    if len(candles) <= strategy.warmup:
        raise ValueError(
            f"Se necesitan más de {strategy.warmup} velas para esta estrategia; hay {len(candles)}"
        )
    started = time.perf_counter()
    for candle in candles:
        engine.on_candle(candle)
    result = engine.snapshot()
    result["elapsed_s"] = round(time.perf_counter() - started, 3)
    return result


async def load_candles(cfg: Config, req: BacktestRequest, cache_dir: str | Path = "data") -> list[Candle]:
    """Download (or read from cache) the candles a backtest needs."""
    bar = interval_ms(req.interval)
    end = req.end_ms or (int(time.time() * 1000) // bar) * bar
    warmup_bars = create(req.strategy, req.params).warmup
    start = end - int(req.days * DAY_MS) - warmup_bars * bar
    source = cfg.market.source

    if source == "csv":
        if not cfg.market.csv_path:
            raise ValueError("Falta market.csv_path en la configuración")
        return await CsvFeed(cfg.market.csv_path).range(start, end)
    if source == "synthetic":
        return await SyntheticFeed(req.symbol, req.interval, seed=7).range(start, end)
    if source != "binance":
        raise ValueError(f"Fuente de datos desconocida: {source!r}")

    cache = Path(cache_dir) / f"{req.symbol}_{req.interval}_{start}_{end}.csv"
    if cache.exists():
        return load_csv(cache)
    feed = BinanceFeed(req.symbol, req.interval, cfg.market.rest_url, cfg.market.ws_url)
    log.info("Descargando velas de %s %s desde Binance...", req.symbol, req.interval)
    candles = await feed.range(start, end)
    if candles:
        save_csv(cache, candles)
    return candles
