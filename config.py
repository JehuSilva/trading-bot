import os

PRODUCTION = 'production'
DEVELOPMENT = 'development'

COIN_TARGET = 'BTC'
COIN_REFER = 'USDT'

ENV = os.getenv('ENVIRONMENT', PRODUCTION)
DEBUG = True

BINANCE = {
  'key': os.environ['API_KEY'],
  'secret': os.environ['API_SECRET']
}

TELEGRAM = {
  'channel': os.environ['TEL_CHANNEL'],
  'bot': os.environ['TEL_BOT']
}

print('ENV = ', ENV)