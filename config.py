import os

PRODUCTION = 'production'
DEVELOPMENT = 'development'

COIN_TARGET = 'BTC'
COIN_REFER = 'USDT'

ENV = os.getenv('ENVIRONMENT', PRODUCTION)
DEBUG = True

BINANCE = {
  'key': '',
  'secret': ''
}

TELEGRAM = {
  'channel': '',
  'bot': ''
}

# recvWindow should less than 60000
recv_window = 5000


print('ENV = ', ENV)
