'''
Binance API definition
'''
import time
import hmac
import hashlib
import requests
from urllib.parse import urlencode


class BinanceAPI:
    '''
    It class models the Binance API endpoints.

    Parameters:
    -----------
    key: str
        The API key.
    secret: str
        The API secret.
    recv_window: int
        The time in milliseconds the request is valid for.
        Defaults to 5000.
    '''

    BASE_URL = 'https://www.binance.com/api/v1'
    BASE_URL_V3 = 'https://api.binance.com/api/v3'
    PUBLIC_URL = 'https://www.binance.com/exchange/public/product'

    def __init__(self, config: object, recv_window: int = 5000) -> None:
        self.key = config.BINANCE_API_KEY
        self.secret = config.BINANCE_API_SECRET
        self.recv_window = recv_window

    def ping(self):
        '''
        Test connectivity to the Rest API.
        '''
        path = '%s/ping' % self.BASE_URL_V3
        return requests.get(path, timeout=30, verify=True).json()

    def get_history(self, market, limit=50):
        '''
        Get the latest trades that occurred on a market.
        '''
        path = '%s/historicalTrades' % self.BASE_URL
        params = {'symbol': market, 'limit': limit}
        return self._get_no_sign(path, params)

    def get_trades(self, market, limit=50):
        '''
        Get the latest trades that occurred on a market.
        '''
        path = '%s/trades' % self.BASE_URL
        params = {'symbol': market, 'limit': limit}
        return self._get_no_sign(path, params)

    def get_klines(self, market, interval, startTime, endTime):
        '''
        Kline/Candlestick bars for a symbol. Klines are uniquely identified by their open time.
        '''
        path = '%s/klines' % self.BASE_URL_V3
        params = {'symbol': market, 'interval': interval,
                  'startTime': startTime, 'endTime': endTime}
        return self._get_no_sign(path, params)

    def get_ticker(self, market):
        '''
        Get ticker info.
        '''
        path = '%s/ticker/24hr' % self.BASE_URL
        params = {'symbol': market}
        return self._get_no_sign(path, params)

    def get_order_books(self, market, limit=50):
        '''
        Get the order book for a market.
        '''
        path = '%s/depth' % self.BASE_URL
        params = {'symbol': market, 'limit': limit}
        return self._get_no_sign(path, params)

    def get_account(self):
        '''
        Get current account information.
        '''
        path = '%s/account' % self.BASE_URL_V3
        _account = self._get(path, {})
        # Sorting the balances by asset quantity
        _account['balances'] = sorted(
            _account['balances'], key=lambda x: x['free'], reverse=True
        )[0:5]
        return _account

    def get_products(self):
        '''
        Get the list of products/symbols.
        '''
        return requests.get(self.PUBLIC_URL, timeout=30, verify=True).json()

    def get_server_time(self):
        '''
        Get the server time.
        '''
        path = '%s/time' % self.BASE_URL_V3
        return requests.get(path, timeout=30, verify=True).json()

    def get_exchange_info(self):
        '''
        Get the exchange information.
        '''
        path = '%s/exchangeInfo' % self.BASE_URL
        return requests.get(path, timeout=30, verify=True).json()

    def get_open_orders(self, market, limit=100):
        '''
        Get the open orders for a symbol.
        '''
        path = '%s/openOrders' % self.BASE_URL_V3
        params = {'symbol': market}
        return self._get(path, params)

    def get_my_trades(self, market, limit=50):
        '''
        Get trades for a specific account and symbol.
        '''
        path = '%s/myTrades' % self.BASE_URL_V3
        params = {'symbol': market, 'limit': limit}
        return self._get(path, params)

    def buy_limit(self, market, quantity, rate):
        '''
        Buy a market.
        '''
        path = '%s/order' % self.BASE_URL_V3
        params = self._order(market, quantity, 'BUY', rate)
        return self._post(path, params)

    def sell_limit(self, market, quantity, rate):
        '''
        Sell a market.
        '''
        path = '%s/order' % self.BASE_URL_V3
        params = self._order(market, quantity, 'SELL', rate)
        return self._post(path, params)

    def buy_market(self, market, quantity):
        '''
        Buy a market.
        '''
        path = '%s/order' % self.BASE_URL_V3
        params = self._order(market, quantity)
        return self._post(path, params)
        path = '%s/order' % self.BASE_URL_V3
        params = self._order(market, quantity, 'BUY')
        return self._post(path, params)

    def sell_market(self, market, quantity):
        '''
        Sell a market.
        '''
        path = '%s/order' % self.BASE_URL_V3
        params = self._order(market, quantity, 'SELL')
        return self._post(path, params)

    def query_order(self, market, orderId):
        '''
        Query an order.
        '''
        path = '%s/order' % self.BASE_URL_V3
        params = {'symbol': market, 'orderId': orderId}
        return self._get(path, params)

    def cancel(self, market, order_id):
        '''
        Cancel an order.
        '''
        path = '%s/order' % self.BASE_URL_V3
        params = {'symbol': market, 'orderId': order_id}
        return self._delete(path, params)

    def _get_no_sign(self, path, params={}):
        '''
        Get request without sign.
        '''
        query = urlencode(params)
        url = '%s?%s' % (path, query)
        return requests.get(url, timeout=30, verify=True).json()

    def _sign(self, params={}):
        '''
        Sign a request.
        '''
        data = params.copy()

        ts = int(1000 * time.time())
        data.update({'timestamp': ts})
        h = urlencode(data)
        b = bytearray()
        b.extend(self.secret.encode())
        signature = hmac.new(b, msg=h.encode('utf-8'),
                             digestmod=hashlib.sha256).hexdigest()
        data.update({'signature': signature})
        return data

    def _order(self, market, quantity, side, rate=None):
        '''
        Generate order params.
        '''
        params = {}

        if rate is not None:
            params['type'] = 'LIMIT'
            params['price'] = self._format(rate)
            params['timeInForce'] = 'GTC'
        else:
            params['type'] = 'MARKET'

        params['symbol'] = market
        params['side'] = side
        params['quantity'] = quantity
        #params['quantity'] =  '%.8f' % quantity

        return params

    def _delete(self, path, params={}):
        '''
        Delete request.
        '''
        params.update({'recvWindow': self.recv_window})
        query = urlencode(self._sign(params))
        url = '%s?%s' % (path, query)
        header = {'X-MBX-APIKEY': self.key}
        return requests.delete(url, headers=header,
                               timeout=30, verify=True).json()

    def _format(self, price):
        '''
        Format a price.
        '''
        return '{:.8f}'.format(price)

    def _get(self, path, params={}):
        '''
        Get request.
        '''
        params.update({'recvWindow': self.recv_window})
        query = urlencode(self._sign(params))
        url = '%s?%s' % (path, query)
        header = {'X-MBX-APIKEY': self.key}
        return requests.get(url, headers=header,
                            timeout=30, verify=True).json()

    def _post(self, path, params={}):
        '''
        Post request.
        '''
        params.update({'recvWindow': self.recv_window})
        query = urlencode(self._sign(params))
        url = '%s' % (path)
        header = {'X-MBX-APIKEY': self.key}
        return requests.post(url, headers=header, data=query,
                             timeout=30, verify=True).json()
