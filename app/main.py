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

strategy = Strategy(config=config)
binance = BinanceAPI(config=config)
telegram = TelegramBot(config=config)


def on_open(ws):
    logger('Opened connection')


def on_close(ws):
    logger('Closed connection')


def on_message(ws, message):
    global closes

    message = json.loads(message)
    candle = message['k']
    is_candle_close = candle['x']
    close = candle['c']

    if is_candle_close:
        closes.append(float(close))
        if len(closes) > config.RSI_PERIOD:
            last_rsi, action = strategy.get_trade_recommendation(closes)
            close_message = 'Symbol: %s  Close: %0.6s  RSI: %0.6s' % (
                config.TRADE_SYMBOL, close, last_rsi
            )
            logger(close_message)
            if action in ['SELL', 'BUY']:
                logger(f'{action} {config.TRADE_SYMBOL}')

                try:
                    if action == 'SELL':
                        order = binance.sell(
                            symbol=config.TRADE_SYMBOL,
                            quantity=config.TRADE_QUANTITY
                        )
                        strategy.change_position(position=False)
                    elif action == 'BUY':
                        order = binance.buy(
                            symbol=config.TRADE_SYMBOL,
                            quantity=config.TRADE_QUANTITY
                        )
                        strategy.change_position(position=True)
                    order_message = (
                        '%s %s \n'
                        'Price: %.6s \n'
                        'Qty: %.6s \n'
                        'Commission: %.6s \n'
                        'Order ID: %s' % (
                            action,
                            order['symbol'],
                            order['fills'][0]['price'],
                            order['executedQty'],
                            order['fills'][0]['commission'],
                            order['orderId']
                        )
                    )
                    logger(order_message, color='green')
                    telegram.send_message(message=order_message)
                except Exception as e:
                    logger(
                        text='Couldn\'t place order: %s' % e, color='red'
                    )

            # else:
            #     logger(f'{action} {config.TRADE_SYMBOL}')

        else:
            logger('Not enough data, Waiting...')


if __name__ == '__main__':
    try:
        assets = [
            '%s: %.7s' % (a['asset'], a['free'])
            for a in binance.get_account()['balances']
        ]
        message = 'Everything set. Let\'s trade!\nCurrent balances:\n' + \
            '\n'.join(assets)
        logger(message, color='cyan')
        telegram.send_message(message=message)
        strategy.set_quantities(assets)

        ws = websocket.WebSocketApp(
            config.SOCKET,
            on_open=on_open,
            on_close=on_close,
            on_message=on_message
        )
        ws.run_forever()
    except KeyboardInterrupt:
        logger('Bot finished by user', 'cyan')
        telegram.send_message(f'Bot finished by the user')
    except Exception as err:
        logger(f'Bot finished with error: {err}', 'cyan')
        telegram.send_message(f'Bot finished with error: {err}')
    finally:
        logger('Bot stopped', 'cyan')
        telegram.send_message('Bot stopped!')
