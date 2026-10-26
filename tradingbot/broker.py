"""Brokers.

`Broker` is the interface the engine trades through. `PaperBroker`
simulates a spot account (long only) with virtual money, fees and
slippage. A real Binance broker can be added later by implementing the
same interface; it is intentionally not included yet.
"""

from __future__ import annotations

from typing import Protocol

from .models import Action, Fill, Trade


class Broker(Protocol):
    @property
    def in_position(self) -> bool: ...

    @property
    def entry_price(self) -> float | None: ...

    def buy(self, price: float, time: int, fraction: float = 1.0, reason: str = "") -> Fill | None: ...

    def sell(self, price: float, time: int, reason: str = "") -> Fill | None: ...

    def equity(self, price: float) -> float: ...


class PaperBroker:
    """Virtual spot account.

    Buys spend `fraction` of the available cash; sells close the whole
    position. Fees are charged in the quote currency (e.g. USDT).
    """

    def __init__(
        self,
        initial_cash: float = 1000.0,
        fee_rate: float = 0.001,
        slippage: float = 0.0005,
        min_notional: float = 5.0,
    ) -> None:
        if initial_cash <= 0:
            raise ValueError("El saldo inicial debe ser positivo")
        self.initial_cash = float(initial_cash)
        self.fee_rate = float(fee_rate)
        self.slippage = float(slippage)
        self.min_notional = float(min_notional)
        self.cash = float(initial_cash)
        self.quantity = 0.0
        self.fills: list[Fill] = []
        self.trades: list[Trade] = []
        self._entry_cost = 0.0  # quote spent on the open position, fees included
        self._entry_time: int | None = None

    @property
    def in_position(self) -> bool:
        return self.quantity > 0

    @property
    def entry_price(self) -> float | None:
        if not self.in_position:
            return None
        return self._entry_cost / self.quantity

    def equity(self, price: float) -> float:
        return self.cash + self.quantity * price

    def buy(self, price: float, time: int, fraction: float = 1.0, reason: str = "") -> Fill | None:
        fraction = min(max(fraction, 0.0), 1.0)
        spend = self.cash * fraction
        if spend < self.min_notional:
            return None
        fill_price = price * (1 + self.slippage)
        fee = spend * self.fee_rate
        qty = (spend - fee) / fill_price
        self.cash -= spend
        if self.quantity == 0:
            self._entry_time = time
        self.quantity += qty
        self._entry_cost += spend
        fill = Fill(time, Action.BUY, fill_price, qty, fee, reason)
        self.fills.append(fill)
        return fill

    def sell(self, price: float, time: int, reason: str = "") -> Fill | None:
        if not self.in_position:
            return None
        fill_price = price * (1 - self.slippage)
        qty = self.quantity
        gross = qty * fill_price
        fee = gross * self.fee_rate
        proceeds = gross - fee
        self.cash += proceeds
        pnl = proceeds - self._entry_cost
        self.trades.append(
            Trade(
                entry_time=self._entry_time or time,
                exit_time=time,
                entry_price=self._entry_cost / qty,
                exit_price=fill_price,
                quantity=qty,
                pnl=pnl,
                return_pct=pnl / self._entry_cost * 100 if self._entry_cost else 0.0,
            )
        )
        self.quantity = 0.0
        self._entry_cost = 0.0
        self._entry_time = None
        fill = Fill(time, Action.SELL, fill_price, qty, fee, reason)
        self.fills.append(fill)
        return fill

    def snapshot(self, price: float) -> dict:
        return {
            "cash": self.cash,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "equity": self.equity(price),
            "initial_cash": self.initial_cash,
        }
