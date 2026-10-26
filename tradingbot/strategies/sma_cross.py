from __future__ import annotations

import math

from ..indicators import ema, sma
from ..models import Action
from .base import HOLD, Context, Indicator, Param, Signal, Strategy, register


@register
class MaCrossStrategy(Strategy):
    name = "ma_cross"
    title = "Cruce de medias"
    description = "Compra cuando la media rápida cruza por encima de la lenta y vende en el cruce contrario."
    params = {
        "fast": Param(9, "Periodo de la media rápida", min=1),
        "slow": Param(21, "Periodo de la media lenta", min=2),
        "use_ema": Param(1, "1 = media exponencial, 0 = media simple", min=0, max=1),
    }
    plots = (Indicator("fast", overlay=True), Indicator("slow", overlay=True))

    def validate(self) -> None:
        if self.p["fast"] >= self.p["slow"]:
            raise ValueError("'fast' debe ser menor que 'slow'")

    @property
    def warmup(self) -> int:
        return int(self.p["slow"]) + 1

    def _averages(self, ctx: Context):
        fn = ema if self.p["use_ema"] else sma
        return ctx.memo(
            "ma", lambda: (fn(ctx.closes, int(self.p["fast"])), fn(ctx.closes, int(self.p["slow"])))
        )

    def decide(self, ctx: Context) -> Signal:
        fast, slow = self._averages(ctx)
        if len(fast) < 2 or any(math.isnan(v) for v in (fast[-2], slow[-2], fast[-1], slow[-1])):
            return HOLD
        crossed_up = fast[-2] <= slow[-2] and fast[-1] > slow[-1]
        crossed_down = fast[-2] >= slow[-2] and fast[-1] < slow[-1]
        if not ctx.in_position and crossed_up:
            return Signal(Action.BUY, "Cruce alcista")
        if ctx.in_position and crossed_down:
            return Signal(Action.SELL, "Cruce bajista")
        return HOLD

    def indicators(self, ctx: Context) -> dict[str, float]:
        fast, slow = self._averages(ctx)
        return {"fast": float(fast[-1]), "slow": float(slow[-1])}
