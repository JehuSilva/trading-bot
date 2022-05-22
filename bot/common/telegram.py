import requests


class TelegramBot():
    def __init__(self, telegram_bot: str, telegram_channel: str) -> None:
        self.bot_id = telegram_bot
        self.channel_id = telegram_channel

    def send_message(self, message):
        endpoint = f'https://api.telegram.org/bot{self.bot_id}/sendMessage'
        params = {
            'chat_id': self.channel_id,
            # 'parse_mode': 'Markdown',
            'text': message
        }
        response = requests.get(endpoint, params=params)
