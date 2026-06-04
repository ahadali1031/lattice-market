"""The event-driven backtest loop — the conductor.

This wires together the four components you built — accessor, strategy, portfolio,
broker — and steps through time one trading day at a time. The *order* of the
steps within each day is the whole no-look-ahead guarantee, so read it carefully:

    1. FILL orders that were decided YESTERDAY at TODAY's open.
    2. MARK the portfolio to market at today's close; record the equity point.
    3. ASK the strategy for signals using only what is knowable today.
    4. SIZE those signals into orders and QUEUE them for TOMORROW's open.
    5. ADVANCE the clock.

The key invariant: an order is *decided* on one day and *filled* on the next.
A decision made today can never be filled at a price seen today — it waits for
tomorrow's open, a price that did not exist when the decision was made. That,
plus the accessor only revealing ``date <= today``, makes peeking impossible.

Stage 0 assumes all symbols share one trading calendar (true for liquid US
equities), so every held symbol has a bar every day the loop steps on.
"""

from __future__ import annotations

import datetime as dt

import polars as pl

from lattice.data import schema
from lattice.data.accessor import PointInTimeAccessor
from lattice.engine.broker import SimulatedBroker
from lattice.engine.events import OrderEvent
from lattice.engine.portfolio import Portfolio
from lattice.engine.strategy import Strategy


class Backtest:
    """Drives accessor -> strategy -> portfolio -> broker forward through time."""

    def __init__(
        self,
        accessor: PointInTimeAccessor,
        strategy: Strategy,
        portfolio: Portfolio,
        broker: SimulatedBroker,
        symbols: list[str],
    ) -> None:
        self._accessor = accessor
        self._strategy = strategy
        self._portfolio = portfolio
        self._broker = broker
        self._symbols = symbols

    def _todays_prices(self) -> tuple[dict[str, float], dict[str, float]]:
        """Open and close for each symbol that has a bar on the current date.

        Returns two dicts keyed by symbol: ``(opens, closes)``. A symbol without a
        bar today (shouldn't happen under the shared-calendar assumption) is simply
        absent from both.
        """
        today = self._accessor.current_date
        opens: dict[str, float] = {}
        closes: dict[str, float] = {}
        for symbol in self._symbols:
            hist = self._accessor.history(symbol)
            if hist.height == 0:
                continue
            last = hist.tail(1)
            if last.item(0, schema.DATE) != today:
                continue  # no bar for this symbol today
            opens[symbol] = last.item(0, schema.OPEN)
            closes[symbol] = last.item(0, schema.CLOSE)
        return opens, closes

    def run(self) -> pl.DataFrame:
        """Run the backtest and return the equity curve (columns: date, equity).

        Write a `while True:` loop. Each iteration, in THIS ORDER:

          today = self._accessor.current_date
          opens, closes = self._todays_prices()

          1. FILL yesterday's queued orders at TODAY's open, then clear the queue:
               for order in pending:
                   fill = self._broker.fill(order, today, opens[order.symbol])
                   self._portfolio.apply_fill(fill)
               pending = []
             (This must run BEFORE step 3, or today's decision could leak into
             today's fill.)

          2. MARK to market and record one equity point:
               equity = self._portfolio.equity(closes)
               dates.append(today); equities.append(equity)

          3. ASK the strategy, given only data <= today:
               signals = self._strategy.generate_signals(self._accessor)

          4. SIZE each signal and QUEUE it for TOMORROW's open:
               for signal in signals:
                   order = self._portfolio.target_order(
                       signal, closes[signal.symbol], equity)
                   if order is not None:
                       pending.append(order)
             (Name this local something other than the step-1 `order`, e.g.
             `new_order`, or mypy will complain about the type.)

          5. ADVANCE; stop when history is exhausted:
               if not self._accessor.advance():
                   break

        Then return: pl.DataFrame({"date": dates, "equity": equities})
        """
        pending: list[OrderEvent] = []  # orders decided yesterday, await today's open
        dates: list[dt.date] = []
        equities: list[float] = []

        while True:
            today = self._accessor.current_date
            opens, closes = self._todays_prices()

            # Fill broker and protfoilio orders
            for order in pending:
                fill = self._broker.fill(order, today, opens[order.symbol])
                self._portfolio.apply_fill(fill)
            pending = []

            # Mark and record equity
            equity = self._portfolio.equity(closes)
            dates.append(today)
            equities.append(equity)

            # Execute our strategy
            generated_signals = self._strategy.generate_signals(self._accessor)

            # Queue orders for the next open
            for generated_signal in generated_signals:
                new_order = self._portfolio.target_order(
                    generated_signal, closes[generated_signal.symbol], equity
                )
                if new_order is not None:
                    pending.append(new_order)

            # Next day
            if not self._accessor.advance():
                break
        return pl.DataFrame({"date": dates, "equity": equities})
