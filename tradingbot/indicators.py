"""Technical indicators in plain numpy (no TA-Lib needed).

Every function returns an array the same length as the input, with NaN
where there is not enough data yet.
"""

from __future__ import annotations

import numpy as np


def _as_array(values) -> np.ndarray:
    return np.asarray(values, dtype=float)


def sma(values, period: int) -> np.ndarray:
    x = _as_array(values)
    out = np.full(x.shape, np.nan)
    if period <= 0 or len(x) < period:
        return out
    csum = np.cumsum(np.insert(x, 0, 0.0))
    out[period - 1 :] = (csum[period:] - csum[:-period]) / period
    return out


def ema(values, period: int) -> np.ndarray:
    """Exponential moving average, seeded with the SMA of the first `period` values."""
    x = _as_array(values)
    out = np.full(x.shape, np.nan)
    if period <= 0 or len(x) < period:
        return out
    alpha = 2.0 / (period + 1)
    prev = float(x[:period].mean())
    values = [prev]
    # Plain Python floats are much faster than indexing numpy arrays in a loop.
    for v in x[period:].tolist():
        prev = alpha * v + (1 - alpha) * prev
        values.append(prev)
    out[period - 1 :] = values
    return out


def rsi(values, period: int = 14) -> np.ndarray:
    """Relative Strength Index with Wilder smoothing (same method as TA-Lib)."""
    x = _as_array(values)
    out = np.full(x.shape, np.nan)
    if period <= 0 or len(x) <= period:
        return out
    delta = np.diff(x)
    gains = np.where(delta > 0, delta, 0.0)
    losses = np.where(delta < 0, -delta, 0.0)

    avg_gain = float(gains[:period].mean())
    avg_loss = float(losses[:period].mean())
    values = [_rsi_value(avg_gain, avg_loss)]
    for gain, loss in zip(gains[period:].tolist(), losses[period:].tolist()):
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        values.append(_rsi_value(avg_gain, avg_loss))
    out[period:] = values
    return out


def _rsi_value(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def bollinger(values, period: int = 20, num_std: float = 2.0):
    """Returns (middle, upper, lower) bands."""
    x = _as_array(values)
    mid = sma(x, period)
    std = np.full(x.shape, np.nan)
    if period > 0 and len(x) >= period:
        windows = np.lib.stride_tricks.sliding_window_view(x, period)
        std[period - 1 :] = windows.std(axis=1)
    return mid, mid + num_std * std, mid - num_std * std
