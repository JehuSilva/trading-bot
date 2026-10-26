"""Live paper trading: real-time candles, virtual money."""

from __future__ import annotations

import asyncio
import csv
import logging
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .broker import PaperBroker
from .config import Config
from .engine import Engine, RiskSettings
from .feeds import BinanceFeed, SyntheticFeed
from .strategies import create

log = logging.getLogger(__name__)

Listener = Callable[[dict], None]


def make_live_feed(cfg: Config):
    m = cfg.market
    if m.source == "binance":
        return BinanceFeed(m.symbol, m.interval, m.rest_url, m.ws_url)
    if m.source == "synthetic":
        return SyntheticFeed(m.symbol, m.interval, seed=None)
    raise ValueError(f"La fuente {m.source!r} no ofrece datos en tiempo real (usa binance o synthetic)")


class Journal:
    """Appends every simulated fill to runs/<start time>/fills.csv."""

    def __init__(self, root: str | Path) -> None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        self.path = Path(root) / stamp / "fills.csv"

    def __call__(self, event: dict) -> None:
        if event.get("type") != "bar" or not event["fills"]:
            return
        new = not self.path.exists()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", newline="") as f:
            writer = csv.writer(f)
            if new:
                writer.writerow(["time_utc", "side", "price", "quantity", "fee", "reason", "equity"])
            equity = event["account"]["equity"]
            for fill in event["fills"]:
                ts = datetime.fromtimestamp(fill["time"] / 1000, timezone.utc).isoformat()
                writer.writerow([ts, fill["side"], fill["price"], fill["quantity"], fill["fee"], fill["reason"], equity])


class LiveSession:
    def __init__(self, cfg: Config, feed_factory=make_live_feed) -> None:
        self.cfg = cfg
        self.feed_factory = feed_factory
        self.engine: Engine | None = None
        self.status = "stopped"
        self.error: str | None = None
        self.started_at: float | None = None
        self._task: asyncio.Task | None = None
        self._listeners: list[Listener] = []

    # Listeners survive strategy changes, so the dashboard stays connected.
    def subscribe(self, listener: Listener) -> Callable[[], None]:
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    def _emit(self, event: dict) -> None:
        for listener in list(self._listeners):
            try:
                listener(event)
            except Exception:
                log.exception("Listener failed")

    async def start(
        self,
        strategy: str | None = None,
        params: dict | None = None,
        risk: RiskSettings | None = None,
    ) -> None:
        """(Re)start paper trading. Restarting resets the virtual account."""
        await self.stop()
        if strategy is not None:
            self.cfg.strategy = replace(self.cfg.strategy, name=strategy, params=params or {})
        if risk is not None:
            self.cfg.risk = risk
        strat = create(self.cfg.strategy.name, self.cfg.strategy.params)  # validates params
        p = self.cfg.paper
        engine = Engine(
            strat,
            PaperBroker(p.initial_cash, p.fee_rate, p.slippage),
            symbol=self.cfg.market.symbol,
            interval=self.cfg.market.interval,
            risk=self.cfg.risk,
        )
        engine.subscribe(self._emit)
        engine.subscribe(self._log_fills)
        engine.subscribe(Journal(self.cfg.journal_dir))
        self.engine = engine
        self.status = "starting"
        self.error = None
        self.started_at = time.time()
        self._task = asyncio.create_task(self._run(engine))
        self._emit({"type": "reset"})

    def _log_fills(self, event: dict) -> None:
        if event.get("type") != "bar":
            return
        for f in event["fills"]:
            log.info(
                "%s %s %.6f @ %.4f (%s) · capital %.2f",
                f["side"], self.cfg.market.symbol, f["quantity"], f["price"], f["reason"],
                event["account"]["equity"],
            )

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None
        if self.status != "error":
            self.status = "stopped"

    async def _run(self, engine: Engine) -> None:
        try:
            feed = self.feed_factory(self.cfg)
            warm = max(self.cfg.market.warmup_candles, engine.strategy.warmup + 1)
            delay = 2.0
            while True:  # keep retrying until the market data is reachable
                try:
                    history = await feed.history(warm)
                    break
                except Exception as exc:
                    self.error = str(exc) or exc.__class__.__name__
                    log.warning("No se pudo cargar el histórico (%s). Reintentando en %.0fs", self.error, delay)
                    self._emit({"type": "status", "status": self.status, "error": self.error})
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, 60)
            self.error = None
            engine.warmup(history)
            log.info(
                "Modo pruebas iniciado: %s %s, estrategia %s %s",
                engine.symbol, engine.interval, engine.strategy.name, engine.strategy.p,
            )
            self.status = "running"
            self._emit({"type": "reset"})
            async for candle in feed.stream():
                engine.on_candle(candle)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.exception("La sesión en vivo se detuvo")
            self.status = "error"
            self.error = str(exc) or exc.__class__.__name__
            self._emit({"type": "status", "status": self.status, "error": self.error})

    def info(self) -> dict:
        return {
            "status": self.status,
            "error": self.error,
            "source": self.cfg.market.source,
            "started_at": self.started_at,
            "paper": vars(self.cfg.paper),
        }
