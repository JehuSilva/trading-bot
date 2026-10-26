from __future__ import annotations

import math

from ..indicators import bollinger
from ..models import Action
from .base import HOLD, Context, Indicator, Param, Signal, Strategy, register


@register
class BollingerStrategy(Strategy):
    name = "bollinger"
    title = "Bandas de Bollinger"
    description = "Compra al cerrar bajo la banda inferior y vende al volver a la media o tocar la banda superior."
    params = {
        "period": Param(20, "Periodo de la media", min=2),
        "num_std": Param(2.0, "Ancho de las bandas en desviaciones típicas", min=0.1),
        "exit_at_middle": Param(1, "1 = vende en la media, 0 = vende en la banda superior", min=0, max=1),
    }
    plots = (
        Indicator("upper", overlay=True),
        Indicator("middle", overlay=True),
        Indicator("lower", overlay=True),
    )

    @property
    def warmup(self) -> int:
        return int(self.p["period"])

    def _bands(self, ctx: Context):
        def compute():
            mid, up, low = bollinger(ctx.closes, int(self.p["period"]), float(self.p["num_std"]))
            return float(mid[-1]), float(up[-1]), float(low[-1])

        return ctx.memo("bands", compute)

    def decide(self, ctx: Context) -> Signal:
        mid, up, low = self._bands(ctx)
        if math.isnan(mid):
            return HOLD
        price = ctx.price
        if not ctx.in_position and price < low:
            return Signal(Action.BUY, "Cierre bajo la banda inferior")
        if ctx.in_position:
            target = mid if self.p["exit_at_middle"] else up
            if price >= target:
                return Signal(Action.SELL, "Precio alcanzó el objetivo")
        return HOLD

    def indicators(self, ctx: Context) -> dict[str, float]:
        mid, up, low = self._bands(ctx)
        return {"upper": up, "middle": mid, "lower": low}
