'''
Miscellaneous functions

    - logger: Logs messages to the console with pretty colors
    - RSI: Calculates the Relative Strength Index
'''
from termcolor import colored
from datetime import datetime


def logger(text: str, color: str = 'white') -> None:
    value = datetime.now()
    text_color = colored(text, color)
    print('[%s] %s' % (value.strftime('%d-%m-%y %H:%M'), text_color))
