'''
General setup for the trading bot
'''

import os

environment = os.getenv('ENVIRONMENT')


class Config():
    '''
    General configuration    
    '''
    RSI_PERIOD = 14
    RSI_OVERSOLD = 30
    RSI_OVERBOUGHT = 70
    TRADE_SYMBOL = 'ETHUSDT'
    TRADE_QUANTITY = 0.013
    SOCKET = 'wss://stream.binance.com:9443/ws/ethusdt@kline_1m'
    RECV_WINDOW = 5000


class Development(Config):
    '''
    Development configuration
    '''
    DEBUG = True


class Production(Config):
    '''
    Production configuration
    '''
    DEBUG = False
    BINANCE_API_KEY = os.getenv('BINANCE_KEY')
    BINANCE_API_SECRET = os.getenv('BINANCE_SECRET')
    TELEGRAM_CHANNEL = os.getenv('TELEGRAM_CHANNEL')
    TELEGRAM_BOT = os.getenv('TELEGRAM_BOT')


config = Production() if environment == 'production' else Development()
