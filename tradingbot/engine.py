"""The engine: feeds candles to a strategy and executes its signals on a broker.

The same engine runs backtests and live paper trading, so both behave
identically for the same candles.
"""

from __future__ import annotations

import logging
import math
from collections import deque
from dataclasses import dataclass
from typing import Callable

import numpy as np

from . import metrics
from .broker import PaperBroker
from .models import Action, Candle, Fill, interval_ms
from .strategies import Context, Strategy

log = logging.getLogger(__name__)

Listener = Callable[[dict], None]


@dataclass
class RiskSettings:
    position_size: float = 1.0  # fraction of cash used per buy
    stop_loss_pct: float = 0.0  # 0 = disabled
    take_profit_pct: float = 0.0  # 0 = disabled


class Engine:
    def __init__(
        self,
        strategy: Strategy,
        broker: PaperBroker,
        *,
        symbol: str,
        interval: str,
        risk: RiskSettings | None = None,
        display_limit: int = 1500,
    ) -> None:
        self.strategy = strategy
        self.broker = broker
        self.symbol = symbol
        self.interval = interval
        self.bar_ms = interval_ms(interval)
        self.risk = risk or RiskSettings()
        # Strategies only see the latest `lookback` candles. This keeps each
        # step fast and makes backtests and live runs match.
        self.lookback = max(strategy.warmup * 10, 300)
        self.history: deque[Candle] = deque(maxlen=self.lookback)
        self._closes: deque[float] = deque(maxlen=self.lookback)
        self.current: Candle | None = None  # candle still forming (live only)

        self.candles: deque[Candle] = deque(maxlen=display_limit)
        self.indicator_series: dict[str, deque] = {}
        self.equity_curve: deque[tuple[int, float]] = deque(maxlen=20_000)
        self._display_limit = display_limit
        self.start_price: float | None = None
        self.listeners: list[Listener] = []

    # ------------------------------------------------------------------ input

    def warmup(self, candles: list[Candle]) -> None:
        """Load past candles so indicators are ready. No trades are made."""
        for candle in candles:
            if candle.closed:
                self._append(candle)
                self._record_indicators(candle)

    def on_candle(self, candle: Candle) -> list[Fill]:
        """Process a candle update. Trading only happens when a candle closes."""
        if self.history and candle.time < self.history[-1].time:
            return []  # stale update
        if not candle.closed:
            self.current = candle
            self._emit({"type": "candle", "candle": candle.to_dict()})
            return []
        if self.history and candle.time == self.history[-1].time:
            return []  # duplicate close
        self.current = None
        self._append(candle)
        fills = self._step(candle)
        return fills

    # ------------------------------------------------------------------ logic

    def _append(self, candle: Candle) -> None:
        self.history.append(candle)
        self._closes.append(candle.close)
        self.candles.append(candle)

    def _step(self, candle: Candle) -> list[Fill]:
        fills: list[Fill] = []
        exit_fill = self._check_risk_exits(candle)
        if exit_fill:
            fills.append(exit_fill)

        indicators: dict[str, float] = {}
        if len(self.history) >= self.strategy.warmup:
            if self.start_price is None:
                self.start_price = candle.close
            ctx = self._context()
            indicators = self._record_indicators(candle, ctx)
            if not exit_fill:  # don't re-enter on the same bar a stop fired
                signal = self.strategy.decide(ctx)
                fill = self._execute(signal.action, candle, signal.reason)
                if fill:
                    fills.append(fill)
            self.equity_curve.append((candle.time, self.broker.equity(candle.close)))

        for fill in fills:
            log.debug(
                "%s %s %.6f @ %.4f (%s)",
                fill.side.value, self.symbol, fill.quantity, fill.price, fill.reason,
            )
        if not self.listeners:  # backtests: skip building events nobody reads
            return fills
        self._emit(
            {
                "type": "bar",
                "candle": candle.to_dict(),
                "indicators": indicators,
                "fills": [f.to_dict() for f in fills],
                "equity": self.equity_curve[-1] if self.equity_curve else None,
                "account": self.broker.snapshot(candle.close),
                "metrics": self.summary(),
            }
        )
        return fills

    def _execute(self, action: Action, candle: Candle, reason: str) -> Fill | None:
        # Signals are acted on at the close of the candle that produced them.
        if action is Action.BUY and not self.broker.in_position:
            return self.broker.buy(candle.close, candle.time, self.risk.position_size, reason)
        if action is Action.SELL and self.broker.in_position:
            return self.broker.sell(candle.close, candle.time, reason)
        return None

    def _check_risk_exits(self, candle: Candle) -> Fill | None:
        entry = self.broker.entry_price
        if entry is None:
            return None
        sl, tp = self.risk.stop_loss_pct, self.risk.take_profit_pct
        # Stop loss is checked first: if both levels were touched in the same
        # candle we can't know the order, so assume the worse outcome.
        if sl > 0:
            stop = entry * (1 - sl / 100)
            if candle.low <= stop:
                price = min(stop, candle.open)  # a gap down fills at the open
                return self.broker.sell(price, candle.time, f"Stop loss {sl:g}%")
        if tp > 0:
            target = entry * (1 + tp / 100)
            if candle.high >= target:
                price = max(target, candle.open)
                return self.broker.sell(price, candle.time, f"Take profit {tp:g}%")
        return None

    def _context(self) -> Context:
        ctx = Context(
            candles=list(self.history),
            in_position=self.broker.in_position,
            entry_price=self.broker.entry_price,
        )
        ctx.memo("closes", lambda: np.array(self._closes))
        return ctx

    def _record_indicators(self, candle: Candle, ctx: Context | None = None) -> dict[str, float]:
        if len(self.history) < self.strategy.warmup:
            return {}
        ctx = ctx or self._context()
        values = {
            k: v for k, v in self.strategy.indicators(ctx).items()
            if v is not None and not math.isnan(v)
        }
        for name, value in values.items():
            series = self.indicator_series.setdefault(name, deque(maxlen=self._display_limit))
            series.append((candle.time, value))
        return values

    # ----------------------------------------------------------------- output

    def subscribe(self, listener: Listener) -> Callable[[], None]:
        self.listeners.append(listener)
        return lambda: self.listeners.remove(listener)

    def _emit(self, event: dict) -> None:
        for listener in list(self.listeners):
            try:
                listener(event)
            except Exception:  # a broken listener must never stop trading
                log.exception("Listener failed")

    @property
    def last_price(self) -> float | None:
        if self.current:
            return self.current.close
        return self.history[-1].close if self.history else None

    def summary(self) -> dict:
        return metrics.summarize(
            initial_cash=self.broker.initial_cash,
            equity_curve=list(self.equity_curve),
            trades=self.broker.trades,
            first_price=self.start_price,
            last_price=self.last_price,
            bar_ms=self.bar_ms,
        )

    def snapshot(self) -> dict:
        """Full state, used to draw the dashboard."""
        price = self.last_price or 0.0
        candles = [c.to_dict() for c in self.candles]
        if self.current:
            candles.append(self.current.to_dict())
        return {
            "symbol": self.symbol,
            "interval": self.interval,
            "strategy": {
                **self.strategy.describe(),
                "title": self.strategy.title or self.strategy.name,
                "plots": [
                    {"name": p.name, "overlay": p.overlay, "levels": list(p.levels)}
                    for p in self.strategy.plots
                ],
            },
            "risk": vars(self.risk),
            "candles": candles,
            "indicators": {k: list(v) for k, v in self.indicator_series.items()},
            "equity": list(self.equity_curve),
            "fills": [f.to_dict() for f in self.broker.fills],
            "trades": [t.to_dict() for t in self.broker.trades],
            "account": self.broker.snapshot(price),
            "metrics": self.summary(),
        }
