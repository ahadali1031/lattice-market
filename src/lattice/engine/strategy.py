"""The Strategy interface and the Stage 0 moving-average crossover.

A strategy turns *what is knowable now* into *intent*. It is handed a
``MarketView`` (read-only, no way to advance time) and returns ``SignalEvent``s.
It never sizes orders or knows about cash — that is the portfolio's job.

The crossover rule (long-only, Stage 0): compare a short ("fast") moving average
of closes to a longer ("slow") one. Fast above slow → want to be LONG; otherwise
→ want to be flat (EXIT). The strategy reports the desired exposure each day; the
portfolio decides when that means actually trading.
"""

from __future__ import annotations

from typing import Protocol, cast

from lattice.data import schema
from lattice.data.accessor import MarketView
from lattice.engine.events import SignalEvent, SignalType


class Strategy(Protocol):
    """Anything that converts a point-in-time market view into trading intent."""

    def generate_signals(self, view: MarketView) -> list[SignalEvent]:
        """Return this day's signals (possibly empty) given what is knowable now."""
        ...


class MovingAverageCrossover:
    """Long-only fast/slow moving-average crossover over closing prices."""

    def __init__(self, symbols: list[str], fast_window: int, slow_window: int) -> None:
        if fast_window <= 0 or slow_window <= 0:
            raise ValueError("moving-average windows must be positive")
        if fast_window >= slow_window:
            raise ValueError("fast_window must be strictly shorter than slow_window")
        self._symbols = symbols
        self._fast_window = fast_window
        self._slow_window = slow_window

    def generate_signals(self, view: MarketView) -> list[SignalEvent]:
        """Emit one signal per symbol that has enough history.

        For each symbol:
          - read its point-in-time history: ``view.history(symbol)``
          - skip it if there are fewer than ``self._slow_window`` bars (the slow
            average isn't defined yet)
          - take the close column (``hist[schema.CLOSE]``)
          - fast MA  = mean of the last ``self._fast_window`` closes
          - slow MA  = mean of the last ``self._slow_window`` closes
            (hint: a polars Series has ``.tail(n)`` and ``.mean()``)
          - choose ``SignalType.LONG`` if fast > slow else ``SignalType.EXIT``
          - append ``SignalEvent(view.current_date, symbol, signal)``
        Return the collected list.
        """
        signals: list[SignalEvent] = []
        for symbol in self._symbols:
            history = view.history(symbol)
            if len(history) < self._slow_window:
                continue
            close = history[schema.CLOSE]
            fast_ma = cast(float, close.tail(self._fast_window).mean())
            slow_ma = cast(float, close.tail(self._slow_window).mean())
            if fast_ma > slow_ma:
                signals.append(SignalEvent(view.current_date, symbol, SignalType.LONG))
            else:
                signals.append(SignalEvent(view.current_date, symbol, SignalType.EXIT))
        return signals
