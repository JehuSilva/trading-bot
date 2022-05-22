import os
from bot.common.telegram import TelegramBot
from bot.common.utils import logger
from bot.binance.api import BinanceAPI

ENV = os.getenv('ENV', 'development')


if __name__ == '__main__':
    if ENV == 'development':
        logger('Running in development mode')
    else:
        logger('Running in production mode')
        telegram = TelegramBot(
            telegram_channel=os.getenv('TELEGRAM_CHANNEL'),
            telegram_bot=os.getenv('TELEGRAM_BOT')
        )
        binance = BinanceAPI(
            binance_key=os.getenv('BINANCE_KEY'),
            binance_secret=os.getenv('BINANCE_SECRET'),
        )
        logger.info('Everything is ready. Let\'s trade!')
        telegram.send_message('Everything is ready. Let\'s trade!')
