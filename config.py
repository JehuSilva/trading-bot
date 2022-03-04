import os


class Config:
    COIN_TARGET = 'BTC'
    COIN_REFER = 'USDT'

    # recvWindow should less than 60000
    recv_window = 5000


BINANCE = {
    'key': 'TqrQVAN8EBQzJmpPzmNPO93KgWPRbyobF2GjXhYWGBTef722caoR2alGGeiTZmtk',
    'secret': 'fIzotblfE6m8RLPWn65PAYCcGpokUBoDVi3rVQy50E3bgDqhzIxE2QEYl8Kl9Z2E'
}
TELEGRAM = {
    'channel': '-1001519367131',
    'bot': '1635215508:AAEyC0Kj0uSxu8TlIR90GXCBnmsegd1jP0U'
}


DEBUG = True
ENV = os.getenv('ENV', 'development')
print('ENV = ', ENV)
