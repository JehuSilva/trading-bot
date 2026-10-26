"""Configuration loaded from a TOML file. See `config.example.toml`."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

from .engine import RiskSettings


@dataclass
class MarketConfig:
    source: str = "binance"  # binance | synthetic | csv
    symbol: str = "ETHUSDT"
    interval: str = "1m"
    rest_url: str = "https://api.binance.com"
    ws_url: str = "wss://stream.binance.com:9443"
    csv_path: str | None = None
    warmup_candles: int = 500


@dataclass
class StrategyConfig:
    name: str = "rsi"
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class PaperConfig:
    initial_cash: float = 1000.0
    fee_rate: float = 0.001
    slippage: float = 0.0005


@dataclass
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8000


@dataclass
class Config:
    market: MarketConfig = field(default_factory=MarketConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    paper: PaperConfig = field(default_factory=PaperConfig)
    risk: RiskSettings = field(default_factory=RiskSettings)
    server: ServerConfig = field(default_factory=ServerConfig)
    journal_dir: str = "runs"


def _build(cls, data: dict, section: str):
    known = {f.name for f in fields(cls)}
    unknown = set(data) - known
    if unknown:
        raise ValueError(f"Claves desconocidas en [{section}]: {', '.join(sorted(unknown))}")
    return cls(**data)


def load_config(path: str | Path | None = None) -> Config:
    if path is None:
        return Config()
    with Path(path).open("rb") as f:
        raw = tomllib.load(f)
    return Config(
        market=_build(MarketConfig, raw.get("market", {}), "market"),
        strategy=_build(StrategyConfig, raw.get("strategy", {}), "strategy"),
        paper=_build(PaperConfig, raw.get("paper", {}), "paper"),
        risk=_build(RiskSettings, raw.get("risk", {}), "risk"),
        server=_build(ServerConfig, raw.get("server", {}), "server"),
        journal_dir=raw.get("journal_dir", "runs"),
    )
