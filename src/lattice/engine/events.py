"""The events that flow through the backtest loop.

An event-driven backtest is a chain of facts, each one triggering the next::

    MarketEvent  ->  SignalEvent  ->  OrderEvent  ->  FillEvent
    (new bars        (strategy's      (portfolio's     (broker's
     are visible)     intent)          sized order)     execution)

Each stage is owned by a different component, and they only ever communicate
through these objects — never by reaching into each other's internals. That
keeps the pipeline decoupled: the strategy knows nothing about commissions, the
broker knows nothing about moving averages.

Every event is a frozen dataclass: an event is a *fact that happened*, so it must
not be mutated after the fact. ``slots=True`` also forbids tacking on stray
attributes, turning a typo like ``fill.pric`` into an error instead of a silent
new field.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from enum import Enum


class Side(Enum):
    """Whether an order/fill buys or sells."""

    BUY = "BUY"
    SELL = "SELL"


class SignalType(Enum):
    """A strategy's desired exposure for a symbol.

    Stage 0's moving-average strategy only emits LONG and EXIT (it is long-only);
    SHORT exists for later stages and is not acted on yet.
    """

    LONG = "LONG"
    SHORT = "SHORT"
    EXIT = "EXIT"


@dataclass(frozen=True, slots=True)
class MarketEvent:
    """A new trading day's bars have become visible (the cursor advanced)."""

    date: dt.date


@dataclass(frozen=True, slots=True)
class SignalEvent:
    """A strategy's intent for one symbol, decided as of ``date``.

    Intent only — no share count. Translating intent into a sized order is the
    portfolio's job, not the strategy's.
    """

    date: dt.date
    symbol: str
    signal: SignalType


@dataclass(frozen=True, slots=True)
class OrderEvent:
    """A concrete instruction to trade a whole number of shares."""

    date: dt.date
    symbol: str
    side: Side
    quantity: int


@dataclass(frozen=True, slots=True)
class FillEvent:
    """The result of a broker executing an order.

    ``date`` is the day the fill actually happened (for next-open execution this
    is the day *after* the signal). ``commission`` is in cash; ``fill_price`` is
    the per-share price actually paid/received, slippage already applied.
    """

    date: dt.date
    symbol: str
    side: Side
    quantity: int
    fill_price: float
    commission: float
