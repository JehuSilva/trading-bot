"""Command line entry point.

    python -m tradingbot serve       # dashboard + live paper trading
    python -m tradingbot backtest    # backtest in the terminal
    python -m tradingbot strategies  # list strategies and their parameters
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timezone

import httpx

from .backtest import BacktestRequest, load_candles, run_backtest
from .config import load_config
from .strategies import available


def _parse_params(items: list[str]) -> dict[str, float]:
    params = {}
    for item in items:
        key, sep, value = item.partition("=")
        if not sep:
            raise SystemExit(f"Parámetro inválido {item!r}; usa nombre=valor")
        params[key.strip()] = float(value)
    return params


def _fmt(value, suffix: str = "", digits: int = 2) -> str:
    return "—" if value is None else f"{value:,.{digits}f}{suffix}"


def cmd_strategies(_args) -> None:
    for cls in available().values():
        s = cls.schema()
        print(f"\n{s['name']}  ({s['title']})\n  {s['description']}")
        for key, p in s["params"].items():
            print(f"    {key:<15} default={p['default']:<8} {p['description']}")


def cmd_backtest(args, cfg) -> None:
    strategy = args.strategy or cfg.strategy.name
    params = cfg.strategy.params if not args.strategy else {}
    params = {**params, **_parse_params(args.param)}
    req = BacktestRequest(
        strategy=strategy,
        params=params,
        symbol=(args.symbol or cfg.market.symbol).upper(),
        interval=args.interval or cfg.market.interval,
        days=args.days,
        initial_cash=cfg.paper.initial_cash,
        fee_rate=cfg.paper.fee_rate,
        slippage=cfg.paper.slippage,
        risk=cfg.risk,
    )
    candles = asyncio.run(load_candles(cfg, req))
    result = run_backtest(req, candles)
    m = result["metrics"]

    def ts(ms):
        return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M")

    print(f"\nBacktest {req.symbol} {req.interval} · {strategy} {result['strategy']['params']}")
    print(f"Datos: {len(candles)} velas, {ts(candles[0].time)} → {ts(candles[-1].time)} UTC\n")
    rows = [
        ("Capital inicial", _fmt(m["initial_equity"])),
        ("Capital final", _fmt(m["final_equity"])),
        ("Rentabilidad", _fmt(m["return_pct"], "%")),
        ("Comprar y mantener", _fmt(m["buy_hold_pct"], "%")),
        ("Máx. drawdown", _fmt(m["max_drawdown_pct"], "%")),
        ("Operaciones", str(m["trades"])),
        ("Aciertos", _fmt(m["win_rate_pct"], "%", 1)),
        ("Profit factor", _fmt(m["profit_factor"])),
        ("Media por operación", _fmt(m["avg_trade_pct"], "%")),
        ("Sharpe (anual.)", _fmt(m["sharpe"])),
    ]
    for label, value in rows:
        print(f"  {label:<22}{value:>14}")
    if args.trades and result["trades"]:
        print("\n  Entrada            Salida              Precio ent.  Precio sal.   Resultado")
        for t in result["trades"]:
            print(
                f"  {ts(t['entry_time'])}  {ts(t['exit_time'])}  {t['entry_price']:>11.4f}"
                f"  {t['exit_price']:>11.4f}  {t['return_pct']:>9.2f}%"
            )
    print()


def cmd_serve(args, cfg) -> None:
    import uvicorn

    from .web import create_app

    host = args.host or cfg.server.host
    port = args.port or cfg.server.port
    print(f"Dashboard en http://{host}:{port}  (Ctrl+C para salir)")
    uvicorn.run(create_app(cfg), host=host, port=port, log_level="warning")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="tradingbot", description="Bot de trading en modo pruebas")
    parser.add_argument("-c", "--config", help="Archivo TOML de configuración")
    parser.add_argument("--source", choices=["binance", "synthetic", "csv"], help="Fuente de datos")
    parser.add_argument("--csv", help="Archivo CSV con velas (implica --source csv)")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    p_serve = sub.add_parser("serve", help="Dashboard web + modo pruebas en vivo")
    p_serve.add_argument("--host")
    p_serve.add_argument("--port", type=int)

    p_bt = sub.add_parser("backtest", help="Probar una estrategia con datos históricos")
    p_bt.add_argument("-s", "--strategy", help="Nombre de la estrategia (ver 'strategies')")
    p_bt.add_argument("-p", "--param", action="append", default=[], help="nombre=valor (repetible)")
    p_bt.add_argument("--symbol")
    p_bt.add_argument("--interval", help="1m, 5m, 15m, 1h, 4h, 1d...")
    p_bt.add_argument("--days", type=float, default=30)
    p_bt.add_argument("--trades", action="store_true", help="Listar cada operación")

    sub.add_parser("strategies", help="Listar estrategias disponibles")

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    if args.command == "strategies":
        return cmd_strategies(args)

    try:
        cfg = load_config(args.config)
        if args.csv:
            cfg.market.source, cfg.market.csv_path = "csv", args.csv
        elif args.source:
            cfg.market.source = args.source
        if args.command == "backtest":
            cmd_backtest(args, cfg)
        else:
            cmd_serve(args, cfg)
    except (ValueError, FileNotFoundError) as exc:
        sys.exit(f"Error: {exc}")
    except httpx.HTTPError as exc:
        sys.exit(
            f"No se pudo conectar con Binance ({exc}).\n"
            "Revisa tu conexión, prueba rest_url = \"https://data-api.binance.vision\" "
            "en config.toml, o usa --source synthetic para probar sin conexión."
        )


if __name__ == "__main__":
    main()
