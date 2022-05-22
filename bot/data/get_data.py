import csv
from binance.client import Client

from bot.config import API_KEY, API_SECRET


SYMBOL = 'ETHUSDT'


client = Client(API_KEY, API_SECRET)

# Listing criptocurrencies prices
# prices = client.get_all_tickers()
# for price in prices:
#     print(price)

with open(f'data/{SYMBOL}_data.csv', 'w', newline='') as csvfile:
    candlestick_writer = csv.writer(csvfile, delimiter=',')
    candlesticks = client.get_historical_klines(
        SYMBOL, Client.KLINE_INTERVAL_15MINUTE, "1 May, 2022", "17 May, 2022")
    #candlesticks = client.get_historical_klines("BTCUSDT", Client.KLINE_INTERVAL_1DAY, "1 Jan, 2020", "12 Jul, 2020")
    #candlesticks = client.get_historical_klines("BTCUSDT", Client.KLINE_INTERVAL_1DAY, "1 Jan, 2017", "12 Jul, 2020")

    for candlestick in candlesticks:
        candlestick[0] = candlestick[0] / 1000
        candlestick_writer.writerow(candlestick)
