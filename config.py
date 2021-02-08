import os

PRODUCTION = 'production'
DEVELOPMENT = 'development'

COIN_TARGET = 'BTC'
COIN_REFER = 'USDT'

ENV = os.getenv('ENVIRONMENT', PRODUCTION)
DEBUG = True

BINANCE = {
  'key': '6M7a3xBlWC0dDYMZtzsu86iK04t5MGWhUwV3gRKA07EYreC5msdyAFMlNQynejnV',
  'secret': 'MZWKwkzISLhxs6CqHFStvAGzPorADleZN9RkdxuF7D4c2Lxr6XcYq8IbDqxXGFtg'
}

TELEGRAM = {
  'channel': '-1001176684417',
  'bot': '1635215508:AAEyC0Kj0uSxu8TlIR90GXCBnmsegd1jP0U'
}

# recvWindow should less than 60000
recv_window = 5000


print('ENV = ', ENV)
