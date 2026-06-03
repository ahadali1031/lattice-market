"""The data-source interface — the 'wall' the rest of Lattice depends on.

Everything upstream of the store talks to a ``DataSource``, never to yfinance (or
any future provider) directly. Swapping providers in Stage 1 means writing a new
class that satisfies this Protocol; nothing else in the codebase changes.

Why a Protocol instead of an abstract base class?
-------------------------------------------------
A Protocol is *structural*: any class with a matching ``fetch_daily`` method
counts as a ``DataSource`` — it does not have to inherit from anything. That
keeps providers decoupled (a third-party class could satisfy it without knowing
Lattice exists) and is the idiomatic Python way to express "anything shaped like
this". The contract is the method signature, not an inheritance chain.
"""

from __future__ import annotations

import datetime as dt
from typing import Protocol, runtime_checkable

import polars as pl


@runtime_checkable
class DataSource(Protocol):
    """Anything that can yield daily OHLCV bars in Lattice's canonical schema."""

    def fetch_daily(self, symbol: str, start: dt.date, end: dt.date) -> pl.DataFrame:
        """Return daily OHLCV bars for ``symbol`` over the inclusive ``[start, end]``.

        The returned frame MUST conform to ``lattice.data.schema`` (exactly the
        canonical columns, correct dtypes, canonical order) — i.e. it has already
        passed ``schema.enforce``. Callers may therefore trust its shape without
        re-checking. Rows are expected in ascending date order.
        """
        ...
