from termcolor import colored
from datetime import datetime


def logger(text: str, color: str = 'white', send_telegram: bool = False):
    value = datetime.now()
    text_color = colored(text, color)
    print('[%s] %s' % (value.strftime('%d-%m-%y %H:%M'), text_color))
