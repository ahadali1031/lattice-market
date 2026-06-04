"""Simulated broker: turns orders into fills under realistic frictions.

The broker is where a backtest stops being a fantasy. It models two real costs:

* slippage — you do not fill at the quoted price; the market moves against you a
  little. Adversarial by construction: a BUY fills slightly above the open, a
  SELL slightly below.
* commission — a fee charged on every trade (Stage 0: 1% of the trade's value).

It is deliberately pure: given an order, the fill date, and the open price the
loop hands it (T+1's open — the price the strategy could not peek at), it returns
a FillEvent. It holds no data and no clock of its own.
"""

from __future__ import annotations

import datetime as dt

from lattice.engine.events import FillEvent, OrderEvent, Side


class SimulatedBroker:
    """Fills orders at the next open, applying slippage and commission."""

    def __init__(self, commission_rate: float = 0.01, slippage_rate: float = 0.0005) -> None:
        if commission_rate < 0 or slippage_rate < 0:
            raise ValueError("commission_rate and slippage_rate must be non-negative")
        self._commission_rate = commission_rate
        self._slippage_rate = slippage_rate

    def fill(self, order: OrderEvent, fill_date: dt.date, open_price: float) -> FillEvent:
        """Execute ``order`` at ``open_price`` on ``fill_date``, with frictions.

        Steps:
          1. Apply slippage to ``open_price``, adversarially by side:
               - a BUY  fills HIGHER: open_price * (1 + self._slippage_rate)
               - a SELL fills LOWER:  open_price * (1 - self._slippage_rate)
             (``order.side`` is ``Side.BUY`` or ``Side.SELL``.)
          2. Commission = self._commission_rate * order.quantity * fill_price
             (1% of the trade's value).
          3. Return FillEvent(fill_date, order.symbol, order.side, order.quantity,
             fill_price, commission).
        """
        if order.side is Side.BUY:
            fill_price = open_price * (1 + self._slippage_rate)
        else:
            fill_price = open_price * (1 - self._slippage_rate)

        commission = self._commission_rate * order.quantity * fill_price
        return FillEvent(
            fill_date,
            order.symbol,
            order.side,
            order.quantity,
            fill_price=fill_price,
            commission=commission,
        )
