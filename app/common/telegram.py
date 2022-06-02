'''
Telegram messenger interface
'''
import requests


class TelegramBot():
    '''
    It class models the Telegram API endpoints to send messages
    to the user.
    '''

    def __init__(self, config: object) -> None:
        self.bot_id = config.TELEGRAM_BOT
        self.channel_id = config.TELEGRAM_CHANNEL

    def send_message(self, message: str) -> None:
        '''
        Send message to the user
        '''
        endpoint = f'https://api.telegram.org/bot{self.bot_id}/sendMessage'
        params = {
            'chat_id': self.channel_id,
            'parse_mode': 'Markdown',
            'text': message
        }
        response = requests.get(endpoint, params=params)

    def send_photo(self, photo_url: str):
        '''
        Send photo from the  internet to the user
        '''
        endpoint = f'https://api.telegram.org/bot{self.bot_id}/sendPhoto'
        params = {
            'chat_id': self.channel_id,
            'photo': photo_url
        }
        response = requests.get(endpoint, params=params)
