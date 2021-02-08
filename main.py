#!/usr/bin/env python3
from app.BinanceAPI import BinanceAPI
from app.utils import logger
from config import BINANCE
import numpy as np
import websocket
import talib
import json

RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
TRADE_SYMBOL = 'ETHUSDT'
TRADE_QUANTITY = 0.05
SOCKET = 'wss://stream.binance.com:9443/ws/ethusdt@kline_1m'

closes = []
in_position = True
client=BinanceAPI(BINANCE['key'],BINANCE['secret'])

def on_open(ws):
    logger('Opened connection')

def on_close(ws):
    logger('Closed connection')

def on_message(ws,message):
    global closes
    global in_position

    #logger('Received message')
    message = json.loads(message)
    candle = message['k']

    is_candle_close = candle['x']
    close = candle['c']


    if is_candle_close:
        closes.append(float(close))
        if len(closes) > RSI_PERIOD:

            np_closes = np.array(closes)
            rsi = talib.RSI(np_closes,RSI_PERIOD)
            last_rsi = rsi[-1]
            logger(f'Symbol: {TRADE_SYMBOL}  Close Price: {close} USD  RSI:{last_rsi}')
            

            if last_rsi > RSI_OVERBOUGHT:
                if in_position:
                    try:
                        logger('Overbought! Sell! Sell!','green')
                        logger('Sending order','green')
                        order = client.sell_market(TRADE_SYMBOL,TRADE_QUANTITY)
                        logger(f'Order number: {order}  Closed at: {close} RSI: {last_rsi}','green',True)
                        in_position = False
                    except Exception as e:
                        logger(f'Transaction could not be completed')
                else:
                    logger('It is overbought, but you already own it. Nothing to do')

            
            if last_rsi < RSI_OVERSOLD:
                if in_position:
                    logger('It is oversold, but you already own it. Nothing to do')
                else:
                    try:
                        logger('Overbought! Buy! Buy!','red')
                        logger('Sending order','red')
                        order = client.buy_market(TRADE_SYMBOL,TRADE_QUANTITY)
                        logger(f'Order number: {order}  Closed at: {close} RSI: {last_rsi}','red',True)
                        in_position = True
                    except Exception as e:
                        logger(f'Transaction could not be completed')
                    


if __name__ == '__main__':
    try:
        logger('Starting trading ','cyan',True)
        ws = websocket.WebSocketApp(SOCKET,
                                    on_open=on_open,
                                    on_close=on_close,
                                    on_message=on_message)
        ws.run_forever()
    except KeyboardInterrupt:
        logger('Bot finished by user','cyan',True)
        logger('Finished.')
    except Exception as err:
        logger(f'Bot finished with error: {err}','cyan',True)
    finally:
        logger('Lex finished','cyan',True)
