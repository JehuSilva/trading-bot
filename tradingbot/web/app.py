"""Web dashboard: live paper trading view, strategy controls and backtests."""

from __future__ import annotations

import asyncio
import logging
import math
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ..backtest import BacktestRequest, load_candles, run_backtest
from ..config import Config
from ..engine import RiskSettings
from ..live import LiveSession
from ..strategies import available

log = logging.getLogger(__name__)
STATIC = Path(__file__).parent / "static"


def clean(obj: Any) -> Any:
    """Make data JSON-safe: NaN/inf become null."""
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean(v) for v in obj]
    return obj


def json_response(data: Any) -> JSONResponse:
    return JSONResponse(clean(jsonable_encoder(data)))


class RiskIn(BaseModel):
    position_size: float = Field(1.0, gt=0, le=1)
    stop_loss_pct: float = Field(0.0, ge=0, lt=100)
    take_profit_pct: float = Field(0.0, ge=0)

    def to_settings(self) -> RiskSettings:
        return RiskSettings(**self.model_dump())


class StartIn(BaseModel):
    strategy: str
    params: dict[str, float] = {}
    risk: RiskIn = RiskIn()


class BacktestIn(BaseModel):
    strategy: str
    params: dict[str, float] = {}
    symbol: str | None = None
    interval: str = "1h"
    days: float = Field(30, gt=0, le=1000)
    initial_cash: float | None = Field(None, gt=0)
    fee_rate: float | None = Field(None, ge=0, lt=0.1)
    slippage: float | None = Field(None, ge=0, lt=0.1)
    risk: RiskIn = RiskIn()


def create_app(cfg: Config, session: LiveSession | None = None, autostart: bool = True) -> FastAPI:
    session = session or LiveSession(cfg)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if autostart:
            await session.start()
        yield
        await session.stop()

    app = FastAPI(title="Trading Bot", lifespan=lifespan)
    app.state.session = session
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/")
    async def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/api/strategies")
    async def strategies():
        return json_response([cls.schema() for cls in available().values()])

    @app.get("/api/config")
    async def config():
        return json_response(
            {
                "market": vars(cfg.market),
                "paper": vars(cfg.paper),
                "risk": vars(cfg.risk),
                "strategy": vars(cfg.strategy),
            }
        )

    @app.get("/api/live")
    async def live_state():
        data = {"session": session.info(), "state": session.engine.snapshot() if session.engine else None}
        return json_response(data)

    @app.post("/api/live/start")
    async def live_start(body: StartIn):
        try:
            await session.start(body.strategy, body.params, body.risk.to_settings())
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return json_response(session.info())

    @app.post("/api/live/stop")
    async def live_stop():
        await session.stop()
        return json_response(session.info())

    @app.post("/api/backtest")
    async def backtest(body: BacktestIn):
        req = BacktestRequest(
            strategy=body.strategy,
            params=body.params,
            symbol=(body.symbol or cfg.market.symbol).upper(),
            interval=body.interval,
            days=body.days,
            initial_cash=body.initial_cash or cfg.paper.initial_cash,
            fee_rate=cfg.paper.fee_rate if body.fee_rate is None else body.fee_rate,
            slippage=cfg.paper.slippage if body.slippage is None else body.slippage,
            risk=body.risk.to_settings(),
        )
        try:
            candles = await load_candles(cfg, req)
            result = await asyncio.to_thread(run_backtest, req, candles)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except Exception as exc:
            log.exception("Backtest failed")
            raise HTTPException(502, f"No se pudieron obtener los datos: {exc}") from exc
        return json_response(result)

    @app.websocket("/ws/live")
    async def live_ws(ws: WebSocket):
        await ws.accept()
        queue: asyncio.Queue = asyncio.Queue(maxsize=500)

        def push(event: dict) -> None:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # The browser is too slow; tell it to reload the full state.
                while not queue.empty():
                    queue.get_nowait()
                queue.put_nowait({"type": "reset"})

        unsubscribe = session.subscribe(push)
        try:
            while True:
                event = await queue.get()
                await ws.send_json(clean(event))
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            unsubscribe()

    return app
