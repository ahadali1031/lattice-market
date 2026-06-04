"""Tests for the point-in-time accessor — the no-look-ahead guarantee."""

import datetime as dt

import polars as pl
import pytest

from lattice.data import schema
from lattice.data.accessor import PointInTimeAccessor

# Three consecutive trading days, two symbols.
_DATES = [dt.date(2020, 1, 6), dt.date(2020, 1, 7), dt.date(2020, 1, 8)]


def _frame() -> pl.DataFrame:
    parts = []
    for sym, base in [("AAPL", 1.0), ("MSFT", 10.0)]:
        closes = [base + i for i in range(len(_DATES))]
        parts.append(
            schema.enforce(
                pl.DataFrame(
                    {
                        schema.SYMBOL: [sym] * len(_DATES),
                        schema.DATE: _DATES,
                        schema.OPEN: closes,
                        schema.HIGH: closes,
                        schema.LOW: closes,
                        schema.CLOSE: closes,
                        schema.ADJ_CLOSE: closes,
                        schema.VOLUME: [1000] * len(_DATES),
                    }
                )
            )
        )
    return pl.concat(parts)


def test_starts_on_earliest_date() -> None:
    acc = PointInTimeAccessor(_frame())
    assert acc.current_date == _DATES[0]


def test_history_hides_the_future() -> None:
    acc = PointInTimeAccessor(_frame())
    # On day 0, only day 0's bar is visible for AAPL.
    hist = acc.history("AAPL")
    assert hist.height == 1
    assert hist[schema.DATE].to_list() == [_DATES[0]]
    assert hist.columns == schema.COLUMNS


def test_history_filters_by_symbol() -> None:
    acc = PointInTimeAccessor(_frame())
    assert acc.history("MSFT")[schema.SYMBOL].unique().to_list() == ["MSFT"]


def test_window_grows_as_time_advances() -> None:
    acc = PointInTimeAccessor(_frame())
    assert acc.history("AAPL").height == 1
    assert acc.advance() is True
    assert acc.current_date == _DATES[1]
    assert acc.history("AAPL").height == 2
    assert acc.advance() is True
    assert acc.history("AAPL").height == 3
    # All three dates visible, in ascending order, none after current.
    assert acc.history("AAPL")[schema.DATE].to_list() == _DATES


def test_advance_stops_at_the_end() -> None:
    acc = PointInTimeAccessor(_frame())
    assert acc.advance() is True  # -> day 1
    assert acc.advance() is True  # -> day 2 (last)
    assert acc.advance() is False  # nothing left
    assert acc.current_date == _DATES[-1]  # cursor did not move past the end


def test_history_never_exceeds_current_date() -> None:
    acc = PointInTimeAccessor(_frame())
    while True:
        hist = acc.history("AAPL")
        # Every visible row must be dated on or before the cursor.
        assert (hist[schema.DATE] <= acc.current_date).all()
        if not acc.advance():
            break


def test_empty_frame_raises() -> None:
    empty = pl.DataFrame(schema=schema.SCHEMA)
    with pytest.raises(ValueError, match="empty"):
        PointInTimeAccessor(empty)
