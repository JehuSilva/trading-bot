import os


class Config:
    COIN_TARGET = 'BTC'
    COIN_REFER = 'USDT'

    # recvWindow should less than 60000
    recv_window = 5000


BINANCE = {
    'key': os.environ['BINANCE_KEY'],
    'secret': os.environ['BINANCE_SECRET'],
}
TELEGRAM = {
    'channel': os.environ['TELEGRAM_CHANNEL'],
    'bot': os.environ['TELEGRAM_BOT'],
}


DEBUG = True
ENV = os.getenv('ENV', 'development')
print('ENV = ', ENV)
