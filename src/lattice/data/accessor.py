"""Point-in-time accessor: the structural guarantee against look-ahead.

A forward-only cursor over already-stored history. It holds a *current date* (the
simulation's "now") and can ONLY move forward through the trading calendar. There
is deliberately no method to seek to a future date, rewind, or read a bar dated
after the cursor — the *absence* of those verbs is the guarantee. A strategy
physically cannot ask for the future, because the API to express it does not
exist.

The store (one layer down) can see all of history. This accessor is the gate on
top of it that hides everything after `current_date`. That is the only place in
Lattice where the time boundary is enforced.
"""

from __future__ import annotations

import datetime as dt

import polars as pl

from lattice.data import schema


class PointInTimeAccessor:
    """A forward-only, point-in-time view over stored OHLCV history."""

    def __init__(self, frame: pl.DataFrame) -> None:
        # Enforce and keep the full history. The cursor only ever *reveals* slices
        # of this; it never mutates it.
        self._frame = schema.enforce(frame)

        # The simulation timeline: every distinct trading date, ascending. These
        # are the "nows" the cursor is allowed to occupy.
        self._dates: list[dt.date] = (
            self._frame.get_column(schema.DATE).unique().sort().to_list()
        )
        if not self._dates:
            raise ValueError("cannot build a point-in-time accessor over empty data")

        # The cursor starts on the earliest date.
        self._i = 0

    @property
    def current_date(self) -> dt.date:
        """The simulation's 'now' — data is visible only up to and including this."""
        return self._dates[self._i]

    def history(self, symbol: str) -> pl.DataFrame:
        """Bars for ``symbol`` knowable as of ``current_date`` (i.e. date <= now).

        Whole bars only, ascending by date. The ``date <= current_date`` filter is
        the no-look-ahead guarantee: nothing dated after the cursor can come out.
        """
        return self._frame.filter(
            (pl.col(schema.SYMBOL) == symbol) & (pl.col(schema.DATE) <= self.current_date)
        ).sort(schema.DATE)

    def advance(self) -> bool:
        """Step the cursor to the next trading date.

        Returns True if the cursor moved, or False if it is already on the last
        date (the simulation is over). The only verb that moves time, and it only
        ever moves forward.
        """
        if self._i == len(self._dates) - 1:
            return False
        self._i += 1
        return True
