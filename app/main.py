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
from config import config
from common.utils import logger
from binance.api import BinanceAPI
from common.telegram import TelegramBot
from common.strategy import Strategy


closes = []
in_position = True

strategy = Strategy(config=config)
binance = BinanceAPI(config=config)
telegram = TelegramBot(config=config)


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
        if len(closes) > config.RSI_PERIOD:
            last_rsi, action = strategy.get_trade_recommendation(closes)
            message = 'Symbol: %s  Close: %0.6s  RSI: %0.6s' % (
                config.TRADE_SYMBOL, close, last_rsi
            )
            logger(message)
            if action in ['SELL', 'BUY']:
                logger(f'{action} {config.TRADE_SYMBOL}')

                try:
                    if action == 'SELL':
                        order = binance.sell(
                            symbol=config.TRADE_SYMBOL,
                            quantity=config.TRADE_QUANTITY
                        )
                    elif action == 'BUY':
                        order = binance.buy(
                            symbol=config.TRADE_SYMBOL,
                            quantity=config.TRADE_QUANTITY
                        )
                    logger(
                        '%s %s \n'
                        'Price: %.7s \n'
                        'QTY: %.5s \n'
                        'Commission: %.4s \n'
                        'OrderID: %s' % (
                            action,
                            order['symbol'],
                            order['fills'][0]['price'],
                            order['executedQty'],
                            order['fills'][0]['commission'],
                            order['orderId']
                        )
                    )
                    telegram.send_message()
                except Exception as e:
                    logger(
                        text='Couldn\'t place order: %s' % e, color='red'
                    )

            else:
                logger(f'{action} {config.RADE_SYMBOL}')

        else:
            logger('Not enough data, Waiting...')


if __name__ == '__main__':
    try:
        logger('Starting trading ', 'cyan')
        telegram.send_message('Everything set. Let\'s trade!')
        ws = websocket.WebSocketApp(
            config.SOCKET,
            on_open=on_open,
            on_close=on_close,
            on_message=on_message
        )
        ws.run_forever()
    except KeyboardInterrupt:
        logger('Bot finished by user', 'cyan')
    except Exception as err:
        logger(f'Bot finished with error: {err}', 'cyan')
        telegram.send_message(f'Bot finished with error: {err}')
    finally:
        logger('Bot stopped', 'cyan')
        telegram.send_message('Bot stopped!')
