import math

import numpy as np
import pytest

from tradingbot.broker import PaperBroker
from tradingbot.engine import Engine, RiskSettings
from tradingbot.indicators import bollinger, ema, rsi, sma
from tradingbot.metrics import max_drawdown
from tradingbot.models import Action, Candle
from tradingbot.strategies import Context, Signal, create

# --------------------------------------------------------------- indicators

# Classic StockCharts example. Their sheet rounds intermediate averages and
# shows 70.53 / 66.32 / 66.55; the exact (TA-Lib) values are below.
WILDER = [44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08,
          45.89, 46.03, 45.61, 46.28, 46.28, 46.00, 46.03]


def test_rsi_matches_reference_values():
    values = rsi(WILDER, 14)
    assert all(math.isnan(v) for v in values[:14])
    assert values[14] == pytest.approx(70.464, abs=0.001)
    assert values[15] == pytest.approx(66.250, abs=0.001)
    assert values[16] == pytest.approx(66.481, abs=0.001)


def test_rsi_extremes():
    assert rsi(list(range(1, 30)), 14)[-1] == 100.0
    assert rsi(list(range(30, 1, -1)), 14)[-1] == 0.0
    assert rsi([5.0] * 30, 14)[-1] == 50.0


def test_sma_and_ema():
    assert np.allclose(sma([1, 2, 3, 4, 5], 3)[2:], [2, 3, 4])
    assert math.isnan(sma([1, 2], 3)[-1])
    e = ema([1, 2, 3, 4, 5], 3)
    assert e[2] == pytest.approx(2.0)  # seeded with SMA
    assert e[3] == pytest.approx(3.0)  # 0.5 * 4 + 0.5 * 2
    assert e[4] == pytest.approx(4.0)


def test_bollinger_bands_are_symmetric():
    mid, up, low = bollinger([1, 2, 3, 4, 5, 6], 3, 2)
    assert np.allclose((up - mid)[2:], (mid - low)[2:])
    assert mid[-1] == pytest.approx(5.0)


def test_max_drawdown():
    assert max_drawdown([100, 120, 90, 130, 65]) == pytest.approx(50.0)
    assert max_drawdown([100, 110, 120]) == 0.0

# ------------------------------------------------------------------- broker


def test_paper_broker_round_trip_accounting():
    b = PaperBroker(1000, fee_rate=0.001, slippage=0.0)
    buy = b.buy(100.0, time=1)
    assert buy.quantity == pytest.approx(999 / 100)
    assert b.cash == 0 and b.in_position
    assert b.entry_price == pytest.approx(1000 / buy.quantity)

    sell = b.sell(110.0, time=2)
    assert sell.fee == pytest.approx(9.99 * 110 * 0.001)
    assert b.cash == pytest.approx(9.99 * 110 * 0.999)
    assert not b.in_position
    trade = b.trades[0]
    assert trade.pnl == pytest.approx(b.cash - 1000)
    assert trade.return_pct == pytest.approx((b.cash / 1000 - 1) * 100)


def test_paper_broker_slippage_and_guards():
    b = PaperBroker(1000, fee_rate=0.0, slippage=0.01)
    assert b.sell(100, 1) is None  # nothing to sell
    fill = b.buy(100, 1, fraction=0.5)
    assert fill.price == pytest.approx(101)
    assert b.cash == pytest.approx(500)
    assert b.equity(101) == pytest.approx(1000)
    b.cash = 1
    assert b.buy(100, 2) is None  # below minimum order size

# --------------------------------------------------------------- strategies


def test_strategy_params_validation():
    s = create("rsi", {"period": 7})
    assert s.p == {"period": 7, "oversold": 30.0, "overbought": 70.0}
    with pytest.raises(ValueError, match="desconocidos"):
        create("rsi", {"nope": 1})
    with pytest.raises(ValueError):
        create("rsi", {"oversold": 80, "overbought": 70})
    with pytest.raises(ValueError):
        create("ma_cross", {"fast": 30, "slow": 10})
    with pytest.raises(ValueError, match="desconocida"):
        create("magic")


def candles_from(closes, start=0, step=60_000):
    return [Candle(start + i * step, c, c, c, c, 1.0) for i, c in enumerate(closes)]


def test_rsi_strategy_signals():
    s = create("rsi")
    falling = Context(candles_from(range(100, 70, -1)), in_position=False)
    assert s.decide(falling).action is Action.BUY
    rising = Context(candles_from(range(70, 100)), in_position=True)
    assert s.decide(rising).action is Action.SELL
    assert s.decide(Context(candles_from(range(70, 100)), in_position=False)).action is Action.HOLD


def test_ma_cross_detects_crossover():
    s = create("ma_cross", {"fast": 2, "slow": 4, "use_ema": 0})
    closes = [10, 9, 8, 7, 6, 5, 9]  # sharp rebound: fast crosses above slow on the last bar
    assert s.decide(Context(candles_from(closes), in_position=False)).action is Action.BUY

# ------------------------------------------------------------------- engine


class Scripted:
    """Test strategy that plays back a fixed list of actions."""

    name = "scripted"
    title = ""
    plots = ()
    warmup = 1

    def __init__(self, actions):
        self.actions = list(actions)

    def decide(self, ctx):
        return Signal(self.actions.pop(0) if self.actions else Action.HOLD)

    def indicators(self, ctx):
        return {}

    def describe(self):
        return {"name": self.name, "params": {}}


def make_engine(actions, **risk):
    broker = PaperBroker(1000, fee_rate=0, slippage=0)
    return Engine(Scripted(actions), broker, symbol="X", interval="1m", risk=RiskSettings(**risk))


def test_engine_trades_only_on_closed_candles():
    eng = make_engine([Action.BUY])
    eng.on_candle(Candle(0, 100, 100, 100, 100, 1, closed=False))
    assert not eng.broker.fills
    eng.on_candle(Candle(0, 100, 100, 100, 100, 1, closed=True))
    assert len(eng.broker.fills) == 1
    eng.on_candle(Candle(0, 100, 100, 100, 100, 1, closed=True))  # duplicate close
    assert len(eng.equity_curve) == 1


def test_engine_stop_loss_and_take_profit():
    eng = make_engine([Action.BUY], stop_loss_pct=5)
    eng.on_candle(Candle(0, 100, 100, 100, 100, 1))
    eng.on_candle(Candle(60_000, 99, 99, 90, 92, 1))  # touches the stop at 95
    sell = eng.broker.fills[-1]
    assert sell.side is Action.SELL and sell.price == pytest.approx(95)

    eng = make_engine([Action.BUY], stop_loss_pct=5)
    eng.on_candle(Candle(0, 100, 100, 100, 100, 1))
    eng.on_candle(Candle(60_000, 80, 82, 79, 81, 1))  # gap below the stop fills at the open
    assert eng.broker.fills[-1].price == pytest.approx(80)

    eng = make_engine([Action.BUY], take_profit_pct=10)
    eng.on_candle(Candle(0, 100, 100, 100, 100, 1))
    eng.on_candle(Candle(60_000, 101, 115, 100, 112, 1))
    assert eng.broker.fills[-1].price == pytest.approx(110)
    assert eng.broker.trades[0].return_pct == pytest.approx(10)


def test_engine_emits_events():
    eng = make_engine([Action.BUY])
    events = []
    eng.subscribe(events.append)
    eng.on_candle(Candle(0, 100, 101, 99, 100, 1, closed=False))
    eng.on_candle(Candle(0, 100, 101, 99, 100, 1))
    assert [e["type"] for e in events] == ["candle", "bar"]
    assert events[1]["fills"][0]["side"] == "BUY"
    snap = eng.snapshot()
    assert snap["account"]["quantity"] > 0 and len(snap["fills"]) == 1
