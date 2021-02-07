from config import TELEGRAM, ENV,DEBUG
from termcolor import colored
from datetime import datetime
import requests


def send_msg(bot_message):
    endpoint='https://api.telegram.org/bot%s/sendMessage'% TELEGRAM['bot']
    params = {
        'chat_id': TELEGRAM['channel'],
        #'parse_mode': 'Markdown',
        'text': bot_message
    }
    response = requests.get(endpoint,params=params)

def logger(txt,color='white',send_telegram=False):
        if not DEBUG:
            return

        value = datetime.now()
        txt_color = colored(txt, color)
        print('[%s] %s' % (value.strftime('%d-%m-%y %H:%M'), txt_color))

        if send_telegram:
            send_msg(txt)