"""Strategy interface.

To create a strategy, subclass `Strategy`, declare its parameters in
`params`, implement `decide()` and register it with `@register`.
See `rsi.py` for a short example.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar

import numpy as np

from ..models import Action, Candle


@dataclass(frozen=True)
class Param:
    """A tunable strategy parameter, shown as a field in the dashboard."""

    default: float | int
    description: str = ""
    min: float | None = None
    max: float | None = None

    @property
    def kind(self) -> str:
        return "int" if isinstance(self.default, int) else "float"

    def to_dict(self) -> dict:
        return {
            "default": self.default,
            "description": self.description,
            "min": self.min,
            "max": self.max,
            "type": self.kind,
        }


@dataclass(frozen=True)
class Indicator:
    """How to draw an indicator: on the price chart (overlay) or in its own pane."""

    name: str
    overlay: bool = False
    levels: tuple[float, ...] = ()


@dataclass
class Context:
    """What a strategy sees each time a candle closes."""

    candles: list[Candle]
    in_position: bool
    entry_price: float | None = None
    _cache: dict = field(default_factory=dict, repr=False)

    def memo(self, key: str, compute):
        """Compute a value once per candle (shared by `decide` and `indicators`)."""
        if key not in self._cache:
            self._cache[key] = compute()
        return self._cache[key]

    @property
    def closes(self) -> np.ndarray:
        return self.memo(
            "closes", lambda: np.fromiter((c.close for c in self.candles), float, len(self.candles))
        )

    @property
    def price(self) -> float:
        return self.candles[-1].close


@dataclass(frozen=True)
class Signal:
    action: Action
    reason: str = ""


HOLD = Signal(Action.HOLD)


class Strategy(ABC):
    name: ClassVar[str]
    title: ClassVar[str] = ""
    description: ClassVar[str] = ""
    params: ClassVar[dict[str, Param]] = {}
    plots: ClassVar[tuple[Indicator, ...]] = ()

    def __init__(self, **overrides: Any) -> None:
        unknown = set(overrides) - set(self.params)
        if unknown:
            raise ValueError(
                f"Parámetros desconocidos para '{self.name}': {', '.join(sorted(unknown))}"
            )
        self.p: dict[str, float | int] = {}
        for key, spec in self.params.items():
            value = overrides.get(key, spec.default)
            value = int(value) if spec.kind == "int" else float(value)
            if spec.min is not None and value < spec.min:
                raise ValueError(f"'{key}' debe ser >= {spec.min}")
            if spec.max is not None and value > spec.max:
                raise ValueError(f"'{key}' debe ser <= {spec.max}")
            self.p[key] = value
        self.validate()

    def validate(self) -> None:
        """Override to check relations between parameters."""

    @property
    @abstractmethod
    def warmup(self) -> int:
        """Number of closed candles needed before `decide` is called."""

    @abstractmethod
    def decide(self, ctx: Context) -> Signal:
        """Return BUY, SELL or HOLD for the candle that just closed."""

    def indicators(self, ctx: Context) -> dict[str, float]:
        """Latest indicator values, for the dashboard. Keys match `plots`."""
        return {}

    def describe(self) -> dict:
        return {"name": self.name, "params": dict(self.p)}

    @classmethod
    def schema(cls) -> dict:
        return {
            "name": cls.name,
            "title": cls.title or cls.name,
            "description": cls.description,
            "params": {k: v.to_dict() for k, v in cls.params.items()},
        }


_REGISTRY: dict[str, type[Strategy]] = {}


def register(cls: type[Strategy]) -> type[Strategy]:
    _REGISTRY[cls.name] = cls
    return cls


def available() -> dict[str, type[Strategy]]:
    return dict(_REGISTRY)


def create(name: str, params: dict | None = None) -> Strategy:
    try:
        cls = _REGISTRY[name]
    except KeyError:
        raise ValueError(
            f"Estrategia desconocida: {name!r}. Disponibles: {', '.join(sorted(_REGISTRY))}"
        ) from None
    return cls(**(params or {}))
