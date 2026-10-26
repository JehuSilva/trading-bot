"""Performance statistics for a run."""

from __future__ import annotations

import math

from .models import Trade

MS_PER_YEAR = 365 * 86_400_000


def max_drawdown(equity: list[float]) -> float:
    """Largest peak-to-trough drop, as a positive percentage."""
    peak = -math.inf
    worst = 0.0
    for value in equity:
        peak = max(peak, value)
        if peak > 0:
            worst = max(worst, (peak - value) / peak)
    return worst * 100


def summarize(
    *,
    initial_cash: float,
    equity_curve: list[tuple[int, float]],
    trades: list[Trade],
    first_price: float | None,
    last_price: float | None,
    bar_ms: int,
) -> dict:
    final = equity_curve[-1][1] if equity_curve else initial_cash
    values = [v for _, v in equity_curve]
    wins = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl <= 0]
    gross_win = sum(t.pnl for t in wins)
    gross_loss = -sum(t.pnl for t in losses)

    # Annualized Sharpe ratio from per-bar returns (risk-free rate = 0).
    sharpe = None
    if len(values) > 2:
        rets = [b / a - 1 for a, b in zip(values, values[1:]) if a > 0]
        if len(rets) > 1:
            mean = sum(rets) / len(rets)
            var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
            if var > 0:
                sharpe = mean / math.sqrt(var) * math.sqrt(MS_PER_YEAR / bar_ms)

    buy_hold = None
    if first_price and last_price:
        buy_hold = (last_price / first_price - 1) * 100

    return {
        "initial_equity": initial_cash,
        "final_equity": final,
        "return_pct": (final / initial_cash - 1) * 100,
        "buy_hold_pct": buy_hold,
        "max_drawdown_pct": max_drawdown(values),
        "trades": len(trades),
        "win_rate_pct": len(wins) / len(trades) * 100 if trades else None,
        "profit_factor": gross_win / gross_loss if gross_loss > 0 else None,
        "avg_trade_pct": sum(t.return_pct for t in trades) / len(trades) if trades else None,
        "best_trade_pct": max((t.return_pct for t in trades), default=None),
        "worst_trade_pct": min((t.return_pct for t in trades), default=None),
        "sharpe": sharpe,
    }
