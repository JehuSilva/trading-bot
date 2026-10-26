from __future__ import annotations

import math

from ..indicators import rsi
from ..models import Action
from .base import HOLD, Context, Indicator, Param, Signal, Strategy, register


@register
class RsiStrategy(Strategy):
    name = "rsi"
    title = "RSI"
    description = "Compra cuando el RSI cae por debajo de la zona de sobreventa y vende en sobrecompra."
    params = {
        "period": Param(14, "Periodo del RSI", min=2),
        "oversold": Param(30.0, "Compra por debajo de este valor", min=1, max=99),
        "overbought": Param(70.0, "Vende por encima de este valor", min=1, max=99),
    }

    def validate(self) -> None:
        if self.p["oversold"] >= self.p["overbought"]:
            raise ValueError("'oversold' debe ser menor que 'overbought'")

    @property
    def warmup(self) -> int:
        return int(self.p["period"]) + 1

    @property
    def plots(self):
        return (Indicator("rsi", levels=(self.p["oversold"], self.p["overbought"])),)

    def _rsi(self, ctx: Context) -> float:
        return ctx.memo("rsi", lambda: float(rsi(ctx.closes, int(self.p["period"]))[-1]))

    def decide(self, ctx: Context) -> Signal:
        value = self._rsi(ctx)
        if math.isnan(value):
            return HOLD
        if not ctx.in_position and value <= self.p["oversold"]:
            return Signal(Action.BUY, f"RSI {value:.1f} <= {self.p['oversold']:g}")
        if ctx.in_position and value >= self.p["overbought"]:
            return Signal(Action.SELL, f"RSI {value:.1f} >= {self.p['overbought']:g}")
        return HOLD

    def indicators(self, ctx: Context) -> dict[str, float]:
        return {"rsi": self._rsi(ctx)}
