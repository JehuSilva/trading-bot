'''
Robot strategy definition
'''
import talib
import numpy as np


class Strategy():
    '''
    Currently, the strategy is set to use only the RSI indicator

    Parameters
    ----------
    rsi_period : int
        The period of the RSI indicator
    rsi_oversold : int
        The oversold value where the strategy will sell
    rsi_overbought : int
        The overbought value where the strategy will buy
    trade_symbol : str
        The symbol to trade
    trade_quantity : int   
        The quantity to trade
    socket : str
        The stream socket to connect to the Binance API 
    '''

    def __init__(self, config: object) -> None:
        self.rsi_period = config.RSI_PERIOD
        self.rsi_oversold = config.RSI_OVERSOLD
        self.rsi_overbought = config.RSI_OVERBOUGHT
        self.trade_symbol = config.TRADE_SYMBOL
        self.trade_quantity = config.TRADE_QUANTITY
        self.socket = config.SOCKET
        self.in_position = True

    def set_quantities(self, assets):
        '''
        It sets the quantity to trade
        '''
        # TODO: Implement this method
        pass

    def get_trade_recommendation(self, closes: list) -> tuple:
        '''
        It calculates the RSI value and return a recommendation

        Parameters
        ----------
        closes : list
            The list of closes values

        Returns
        -------
        str
            The recommendation
        '''
        rsi = talib.RSI(np.array(closes), self.rsi_period)
        last_rsi = rsi[-1]
        if (last_rsi >= self.rsi_overbought) and self.in_position:
            return 'SELL'
        elif (last_rsi <= self.rsi_oversold) and not self.in_position:
            return 'BUY'
        return (last_rsi, 'HOLD')

    def change_position(self, position):
        '''
        It changes the position of the robot

        Parameters
        ----------
        position : str
            The new position
        '''
        self.in_position = position
