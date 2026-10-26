# Trading Bot

Bot de trading de criptomonedas **en modo pruebas**: usa precios reales de
Binance en tiempo real, pero opera con dinero virtual. Puedes definir
estrategias, probarlas con datos históricos (backtest) y ver cómo funcionarían
en vivo desde un dashboard web.

- **Modo pruebas en vivo**: velas en tiempo real por websocket, órdenes
  simuladas con comisiones y deslizamiento, y un registro de cada orden en
  `runs/<fecha>/fills.csv`.
- **Backtest**: el mismo motor sobre datos históricos de Binance (se guardan
  en `data/` para no descargarlos dos veces).
- **Dashboard web**: gráfica de velas con indicadores y señales, capital,
  posición abierta, métricas, y formularios para cambiar de estrategia o
  lanzar backtests.
- **Estrategias incluidas**: RSI, cruce de medias y bandas de Bollinger, más
  stop loss y take profit opcionales.

No hace falta cuenta ni claves de Binance: los datos de mercado son públicos.
El bot no envía órdenes reales.

## Instalación

Requiere Python 3.11 o superior.

```bash
git clone git@github.com:JehuSilva/trading-bot.git
cd trading-bot
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Uso

### Dashboard + modo pruebas en vivo

```bash
python -m tradingbot serve
```

Abre http://127.0.0.1:8000. El bot carga las últimas velas para preparar los
indicadores y empieza a operar en virtual con la estrategia de la
configuración. Desde el panel **Estrategia** puedes cambiarla; al aplicar, la
cuenta virtual se reinicia.

Para probar sin conexión, usa precios sintéticos (una vela cada 2 segundos):

```bash
python -m tradingbot --source synthetic serve
```

### Backtest

Desde la pestaña **Backtest** del dashboard, o en la terminal:

```bash
python -m tradingbot backtest -s rsi --interval 1h --days 90
python -m tradingbot backtest -s ma_cross -p fast=12 -p slow=26 --interval 4h --days 365 --trades
python -m tradingbot --csv mis_velas.csv backtest -s bollinger --interval 1h --days 30
```

```
python -m tradingbot strategies   # lista las estrategias y sus parámetros
```

### Configuración

```bash
cp config.example.toml config.toml
python -m tradingbot -c config.toml serve
```

En `config.toml` eliges el par (`ETHUSDT`, `BTCUSDT`...), el intervalo, la
estrategia y sus parámetros, el capital virtual, las comisiones y la gestión
de riesgo. Todas las opciones están comentadas en
[`config.example.toml`](config.example.toml).

Si `api.binance.com` está bloqueado en tu país, usa los servidores de solo
datos de Binance:

```toml
[market]
rest_url = "https://data-api.binance.vision"
ws_url = "wss://data-stream.binance.vision"
```

### Docker

```bash
docker build -t tradingbot .
docker run -d --name tradingbot -p 8000:8000 \
  -v $(pwd)/config.toml:/opt/app/config.toml tradingbot
docker logs -f tradingbot
```

## Crear una estrategia

Crea un archivo en `tradingbot/strategies/`, por ejemplo `mi_estrategia.py`:

```python
from ..indicators import rsi, sma
from ..models import Action
from .base import HOLD, Context, Indicator, Param, Signal, Strategy, register


@register
class RsiTendencia(Strategy):
    name = "rsi_tendencia"
    title = "RSI con filtro de tendencia"
    description = "Compra en sobreventa solo si el precio está sobre su media de 200."
    params = {
        "period": Param(14, "Periodo del RSI", min=2),
        "trend": Param(200, "Media de tendencia", min=10),
    }
    plots = (Indicator("trend", overlay=True),)

    @property
    def warmup(self) -> int:
        return int(self.p["trend"])

    def decide(self, ctx: Context) -> Signal:
        value = rsi(ctx.closes, int(self.p["period"]))[-1]
        trend = sma(ctx.closes, int(self.p["trend"]))[-1]
        if not ctx.in_position and value < 30 and ctx.price > trend:
            return Signal(Action.BUY, f"RSI {value:.0f} en tendencia alcista")
        if ctx.in_position and value > 70:
            return Signal(Action.SELL, f"RSI {value:.0f}")
        return HOLD

    def indicators(self, ctx: Context) -> dict[str, float]:
        return {"trend": float(sma(ctx.closes, int(self.p["trend"]))[-1])}
```

Y regístrala en `tradingbot/strategies/__init__.py` añadiéndola al `import`.
Aparecerá en el dashboard con un formulario generado a partir de `params`.

- `decide()` se llama al cierre de cada vela y devuelve `BUY`, `SELL` o `HOLD`.
- `ctx.closes` es un array de numpy con los cierres (el más reciente al final),
  `ctx.candles` las velas completas y `ctx.in_position` si hay posición abierta.
- `indicators()` es opcional: lo que devuelva se dibuja en la gráfica.

## Cómo simula las órdenes

- Las señales se ejecutan al precio de cierre de la vela que las genera.
- Cuenta spot, solo largos: compra con una fracción del efectivo
  (`position_size`) y vende toda la posición.
- Comisión (`fee_rate`, 0,1 % por defecto) y deslizamiento (`slippage`) en
  cada orden.
- El stop loss y el take profit se comprueban con el máximo y el mínimo de
  cada vela; si la vela abre más allá del nivel, se ejecuta al precio de
  apertura. Si ambos se tocan en la misma vela, se asume el stop.
- El backtest y el modo en vivo usan el mismo motor, así que con las mismas
  velas dan los mismos resultados.

Un buen resultado en un backtest no garantiza beneficios en real.

## Estructura

```
tradingbot/
  cli.py            línea de comandos
  config.py         carga de config.toml
  engine.py         motor: velas → estrategia → broker
  broker.py         cuenta virtual (PaperBroker)
  backtest.py       backtests y descarga de históricos
  live.py           sesión en vivo, reconexión y registro de órdenes
  metrics.py        rentabilidad, drawdown, Sharpe...
  indicators.py     SMA, EMA, RSI, Bollinger (numpy, sin TA-Lib)
  feeds/            Binance, datos sintéticos y CSV
  strategies/       estrategias
  web/              dashboard (FastAPI + lightweight-charts)
tests/
```

## Tests

```bash
pip install pytest
python -m pytest
```

## Próximos pasos

- Broker real de Binance: el motor ya opera a través de la interfaz `Broker`,
  así que basta con implementarla con órdenes firmadas.
- Avisos por Telegram.
- Optimizador de parámetros sobre backtests.

Las gráficas usan [TradingView Lightweight Charts](https://github.com/tradingview/lightweight-charts)
(Apache 2.0), incluido en `tradingbot/web/static/vendor/`.
