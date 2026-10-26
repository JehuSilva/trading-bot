import asyncio
import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from tradingbot.backtest import BacktestRequest, load_candles, run_backtest
from tradingbot.config import Config, load_config
from tradingbot.feeds import BinanceFeed, CsvFeed, SyntheticFeed, save_csv
from tradingbot.feeds.binance import parse_ws_kline
from tradingbot.live import LiveSession
from tradingbot.web import create_app

ROOT = Path(__file__).resolve().parent.parent

# ------------------------------------------------------------------ binance


def test_parse_ws_kline():
    msg = json.dumps({
        "e": "kline", "s": "ETHUSDT",
        "k": {"t": 1000, "o": "1.5", "h": "2", "l": "1", "c": "1.8", "v": "10", "x": True},
    })
    c = parse_ws_kline(msg)
    assert (c.time, c.open, c.high, c.low, c.close, c.volume, c.closed) == (1000, 1.5, 2, 1, 1.8, 10, True)
    assert parse_ws_kline('{"result": null, "id": 1}') is None


def fake_binance(total: int, bar: int = 60_000):
    """Mock /api/v3/klines serving `total` closed candles starting at 0."""
    rows = [[i * bar, "1", "2", "0.5", str(1 + i), "3", i * bar + bar - 1] for i in range(total)]

    def handler(request: httpx.Request) -> httpx.Response:
        q = request.url.params
        limit = int(q.get("limit", 500))
        start, end = int(q.get("startTime", 0)), int(q.get("endTime", 10**15))
        sel = [r for r in rows if start <= r[0] <= end]
        sel = sel[:limit] if "startTime" in q else sel[-limit:]
        return httpx.Response(200, json=sel)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_binance_range_paginates():
    async def go():
        feed = BinanceFeed("ETHUSDT", "1m", client=fake_binance(2500))
        return await feed.range(0, 2500 * 60_000)

    candles = asyncio.run(go())
    assert len(candles) == 2500
    assert [c.time for c in candles] == [i * 60_000 for i in range(2500)]


def test_binance_history_returns_latest_closed():
    async def go():
        feed = BinanceFeed("ETHUSDT", "1m", client=fake_binance(1800))
        return await feed.history(1200)

    candles = asyncio.run(go())
    assert len(candles) == 1200
    assert candles[-1].time == 1799 * 60_000
    times = [c.time for c in candles]
    assert times == sorted(set(times))

# ---------------------------------------------------------------- backtests


def test_backtest_on_synthetic_data_is_consistent():
    candles = asyncio.run(SyntheticFeed(interval="1h", seed=1).range(0, 2000 * 3_600_000))
    req = BacktestRequest(strategy="ma_cross", interval="1h")
    result = run_backtest(req, candles)
    m = result["metrics"]
    assert m["trades"] == len(result["trades"]) > 0
    final_cash = 1000 + sum(t["pnl"] for t in result["trades"])
    if result["account"]["quantity"] == 0:
        assert m["final_equity"] == pytest.approx(final_cash)
    # Running it twice gives identical results.
    assert run_backtest(req, candles)["metrics"] == m


def test_backtest_from_csv(tmp_path):
    candles = asyncio.run(SyntheticFeed(interval="1h", seed=3).range(0, 500 * 3_600_000))
    path = tmp_path / "candles.csv"
    save_csv(path, candles)
    assert asyncio.run(CsvFeed(path).range(0, 10**15)) == candles

    cfg = Config()
    cfg.market.source, cfg.market.csv_path = "csv", str(path)
    req = BacktestRequest(strategy="rsi", interval="1h", days=10, end_ms=500 * 3_600_000)
    loaded = asyncio.run(load_candles(cfg, req))
    assert 240 < len(loaded) < 260
    run_backtest(req, loaded)


def test_example_config_loads():
    cfg = load_config(ROOT / "config.example.toml")
    assert cfg.market.symbol == "ETHUSDT"
    assert cfg.strategy.params["oversold"] == 30

# ---------------------------------------------------------------- dashboard


def synthetic_config() -> Config:
    cfg = Config()
    cfg.market.source = "synthetic"
    cfg.market.warmup_candles = 100
    return cfg


def test_web_api(tmp_path):
    cfg = synthetic_config()
    cfg.journal_dir = str(tmp_path)

    def fast_feed(c):
        return SyntheticFeed(c.market.symbol, c.market.interval, bar_seconds=0.01, ticks_per_bar=1)

    session = LiveSession(cfg, feed_factory=fast_feed)
    with TestClient(create_app(cfg, session)) as client:
        names = {s["name"] for s in client.get("/api/strategies").json()}
        assert {"rsi", "ma_cross", "bollinger"} <= names

        r = client.post("/api/backtest", json={"strategy": "bollinger", "interval": "1h", "days": 20})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["metrics"]["initial_equity"] == 1000
        assert body["strategy"]["name"] == "bollinger"

        r = client.post("/api/backtest", json={"strategy": "rsi", "params": {"oversold": 90}})
        assert r.status_code == 400

        r = client.post("/api/live/start", json={"strategy": "rsi", "params": {"period": 3, "oversold": 49, "overbought": 51}})
        assert r.status_code == 200
        for _ in range(100):
            state = client.get("/api/live").json()
            if state["state"] and state["state"]["fills"]:
                break
            asyncio.run(asyncio.sleep(0.05))
        assert state["session"]["status"] == "running"
        assert state["state"]["strategy"]["params"]["period"] == 3
        assert state["state"]["fills"], "expected simulated trades"
        assert list(tmp_path.glob("*/fills.csv")), "fills should be journaled"

        with client.websocket_connect("/ws/live") as ws:
            assert ws.receive_json()["type"] in {"candle", "bar"}

        assert client.post("/api/live/stop").json()["status"] == "stopped"
