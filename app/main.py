'''
Trading bot
-------------------------------------------------------------------------
This application uses the Binance API to retrieve the latest price of a
specified symbol and then uses the TALIB library to calculate the RSI
value. If the RSI value is overbought, the application will buy the
specified symbol. If the RSI value is oversold, the application will sell
the specified symbol.
'''

# Basic packages
import os
import json
import talib
import websocket
import numpy as np

# Custom packages
from common.utils import logger
from binance.api import BinanceAPI
from common.telegram import TelegramBot

environment = os.getenv('ENVIRONMENT')
binance_key = os.getenv('BINANCE_KEY')
binance_secret = os.getenv('BINANCE_SECRET')
telegram_channel = os.getenv('TELEGRAM_CHANNEL')
telegram_bot = os.getenv('TELEGRAM_BOT')


RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
TRADE_SYMBOL = 'ETHUSDT'
TRADE_QUANTITY = 0.03
SOCKET = 'wss://stream.binance.com:9443/ws/ethusdt@kline_1m'

closes = []
in_position = True

client = BinanceAPI(binance_key, binance_secret)
telegram = TelegramBot(telegram_bot, telegram_channel)


def on_open(ws):
    logger('Opened connection')


def on_close(ws):
    logger('Closed connection')


def on_message(ws, message):
    global closes
    global in_position

    message = json.loads(message)
    candle = message['k']
    is_candle_close = candle['x']
    close = candle['c']

    if is_candle_close:
        closes.append(float(close))
        if len(closes) > RSI_PERIOD:

            np_closes = np.array(closes)
            rsi = talib.RSI(np_closes, RSI_PERIOD)
            last_rsi = rsi[-1]
            message = 'Sym: %s  Close: %0.6s  RSI: %0.6s' % (
                TRADE_SYMBOL,
                close,
                last_rsi
            )
            logger(message)
            telegram.send_message(message)

            if last_rsi > RSI_OVERBOUGHT:
                if in_position:
                    try:
                        logger('Overbought! Sell! Sell!', 'green')
                        logger('Sending order', 'green')
                        telegram.send_message('Selling...')
                        order = client.sell_market(
                            TRADE_SYMBOL, TRADE_QUANTITY)
                        message = 'SELL %s  Price: %.7s  QTY: %.5s  '\
                            'Commission: %.4s  OrderID: %s ' % (
                                order['symbol'],
                                order['fills'][0]['price'],
                                order['executedQty'],
                                order['fills'][0]['commission'],
                                order['orderId']
                            )
                        logger(message, 'green', True)
                        telegram.send_message(message)
                        in_position = False
                    except Exception as e:
                        message = f'Transaction could not be completed, Error: {e}'
                        logger(message, 'cyan', True)
                        telegram.send_message(message)

                else:
                    message = 'It is overbought, but you already own it. Nothing to do'
                    logger(message)
                    telegram.send_message(message)

            if last_rsi < RSI_OVERSOLD:
                if in_position:
                    message = 'It is oversold, but you already own it. Nothing to do.'
                    logger(message)
                    telegram.send_message(message)
                else:
                    try:
                        logger('Overbought! Buy!', 'red')
                        logger('Sending order', 'red')
                        telegram.send_message('Buying...')
                        order = client.buy_market(TRADE_SYMBOL, TRADE_QUANTITY)
                        message = 'BUY %s  Price: %.7s  QTY: %.5s  '\
                            'Commission: %.4s  OrderID: %s ' % (
                                order['symbol'],
                                order['fills'][0]['price'],
                                order['executedQty'],
                                order['fills'][0]['commission'],
                                order['orderId']
                            )
                        logger(message, 'red', True)
                        telegram.send_message(message)
                        in_position = True
                    except Exception as e:
                        message = f'Transaction could not be completed, Error: {e}'
                        logger(message, 'cyan', True)

        else:
            logger(f'Closes size: {len(closes)}, Retrivering data...')


if __name__ == '__main__':
    try:
        logger('Starting trading ', 'cyan', True)
        telegram.send_message('Everything set. Let\'s trade!')
        ws = websocket.WebSocketApp(
            SOCKET,
            on_open=on_open,
            on_close=on_close,
            on_message=on_message
        )
        ws.run_forever()
    except KeyboardInterrupt:
        logger('Bot finished by user', 'cyan', True)
    except Exception as err:
        logger(f'Bot finished with error: {err}', 'cyan', True)
        telegram.send_message(f'Bot finished with error: {err}')
    finally:
        logger('Bot finished', 'cyan', True)
