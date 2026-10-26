"""Built-in strategies. Importing this package registers all of them."""

from . import bollinger, rsi, sma_cross  # noqa: F401  (registers the strategies)
from .base import HOLD, Context, Indicator, Param, Signal, Strategy, available, create, register

__all__ = [
    "HOLD",
    "Context",
    "Indicator",
    "Param",
    "Signal",
    "Strategy",
    "available",
    "create",
    "register",
]
