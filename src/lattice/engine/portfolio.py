"""Portfolio accounting: cash, holdings, sizing, and mark-to-market.

The portfolio is the only component that knows about money. It tracks how much
cash and how many shares of each symbol we hold, turns a strategy's intent into a
concretely-sized order, and absorbs fills coming back from the broker.

Sizing rule (Stage 0, equal-weight): a fresh long position targets 1/N of total
equity (N = size of the universe), bought at the latest price; an exit sells the
whole position. We size at entry and do not continuously rebalance — that is a
later-stage refinement.

A small ``cash_buffer`` shrinks each target slightly so there is headroom for the
commission and slippage the broker charges; without it, a fully-invested
portfolio would overspend by ~1% and run a negative cash balance.
"""

from __future__ import annotations

from lattice.engine.events import FillEvent, OrderEvent, Side, SignalEvent, SignalType


class Portfolio:
    """Tracks cash and holdings, sizes orders, and applies fills."""

    def __init__(
        self,
        symbols: list[str],
        starting_cash: float = 100_000.0,
        cash_buffer: float = 0.02,
    ) -> None:
        if not symbols:
            raise ValueError("portfolio needs a non-empty universe of symbols")
        if not 0.0 <= cash_buffer < 1.0:
            raise ValueError("cash_buffer must be in [0, 1)")
        self._n = len(symbols)
        self._cash = starting_cash
        self._cash_buffer = cash_buffer
        # Every symbol starts flat (zero shares).
        self._holdings: dict[str, int] = {symbol: 0 for symbol in symbols}

    @property
    def cash(self) -> float:
        return self._cash

    def shares(self, symbol: str) -> int:
        """How many shares of ``symbol`` we currently hold (0 if flat)."""
        return self._holdings[symbol]

    def equity(self, prices: dict[str, float]) -> float:
        """Total worth: cash plus every open position valued at ``prices``.

        Only non-zero positions are valued, so ``prices`` need only cover symbols
        actually held on the day this is called.
        """
        holdings_value = sum(
            count * prices[symbol] for symbol, count in self._holdings.items() if count
        )
        return self._cash + holdings_value

    def apply_fill(self, fill: FillEvent) -> None:
        """Update cash and holdings to reflect an executed trade.

        A BUY spends cash: subtract (quantity * fill_price) AND the commission,
        and increase the holding by quantity.
        A SELL raises cash: add (quantity * fill_price) and subtract the
        commission, and decrease the holding by quantity.
        (``fill.side`` is ``Side.BUY`` or ``Side.SELL``.)
        """
        if fill.side is Side.BUY:
            self._cash -= fill.quantity * fill.fill_price + fill.commission
            self._holdings[fill.symbol] += fill.quantity
        else:
            self._cash += fill.quantity * fill.fill_price - fill.commission
            self._holdings[fill.symbol] -= fill.quantity

    def target_order(self, signal: SignalEvent, price: float, equity: float) -> OrderEvent | None:
        """Translate a signal into an order, or None if no trade is needed.

        Let ``held = self.shares(signal.symbol)``.

        If the signal is LONG:
          - if already holding (held > 0): return None (hold — no new trade)
          - else size a fresh position: target value = equity / self._n, scaled
            down by the buffer, i.e. multiplied by (1 - self._cash_buffer); the
            share count is that value divided by ``price``, floored to a whole
            number (hint: int(value // price))
          - if that share count is 0 or less, return None (can't afford one share)
          - otherwise return an OrderEvent(signal.date, signal.symbol, Side.BUY, qty)

        If the signal is EXIT:
          - if already flat (held <= 0): return None
          - else return an OrderEvent selling the whole position:
            OrderEvent(signal.date, signal.symbol, Side.SELL, held)
        """
        if signal.signal is SignalType.LONG:
            if self.shares(signal.symbol) > 0:
                return None
            share_count = int((equity / self._n * (1 - self._cash_buffer)) // price)
            if share_count <= 0:
                return None
            return OrderEvent(signal.date, signal.symbol, Side.BUY, share_count)
        # EXIT
        if self.shares(signal.symbol) <= 0:
            return None
        return OrderEvent(signal.date, signal.symbol, Side.SELL, self.shares(signal.symbol))
