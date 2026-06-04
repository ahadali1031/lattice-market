"""Spec for the moving-average crossover strategy."""

import datetime as dt

import polars as pl
import pytest

from lattice.data import schema
from lattice.data.accessor import PointInTimeAccessor
from lattice.engine.events import SignalType
from lattice.engine.strategy import MovingAverageCrossover

_DATES = [dt.date(2020, 1, d) for d in (6, 7, 8, 9, 10)]


def _frame(symbol: str, closes: list[float]) -> pl.DataFrame:
    n = len(closes)
    return schema.enforce(
        pl.DataFrame(
            {
                schema.SYMBOL: [symbol] * n,
                schema.DATE: _DATES[:n],
                schema.OPEN: closes,
                schema.HIGH: closes,
                schema.LOW: closes,
                schema.CLOSE: closes,
                schema.ADJ_CLOSE: closes,
                schema.VOLUME: [1000] * n,
            }
        )
    )


def _run(
    strategy: MovingAverageCrossover, frame: pl.DataFrame
) -> list[tuple[dt.date, str, SignalType]]:
    """Drive the accessor day by day, collecting (date, symbol, signal) tuples."""
    acc = PointInTimeAccessor(frame)
    collected: list[tuple[dt.date, str, SignalType]] = []
    while True:
        for s in strategy.generate_signals(acc):
            collected.append((s.date, s.symbol, s.signal))
        if not acc.advance():
            break
    return collected


def test_crossover_signal_sequence() -> None:
    # closes 10,11,12,11,10 with fast=2 slow=3:
    #   days 0-1: too little history -> no signal
    #   day 2: fast(11.5) > slow(11.0)   -> LONG
    #   day 3: fast(11.5) > slow(11.33)  -> LONG
    #   day 4: fast(10.5) < slow(11.0)   -> EXIT
    strat = MovingAverageCrossover(["AAPL"], fast_window=2, slow_window=3)
    out = _run(strat, _frame("AAPL", [10, 11, 12, 11, 10]))
    assert out == [
        (_DATES[2], "AAPL", SignalType.LONG),
        (_DATES[3], "AAPL", SignalType.LONG),
        (_DATES[4], "AAPL", SignalType.EXIT),
    ]


def test_no_signal_before_enough_history() -> None:
    strat = MovingAverageCrossover(["AAPL"], fast_window=2, slow_window=3)
    out = _run(strat, _frame("AAPL", [10, 11]))  # only 2 bars, slow needs 3
    assert out == []


def test_rejects_bad_windows() -> None:
    with pytest.raises(ValueError, match="strictly shorter"):
        MovingAverageCrossover(["AAPL"], fast_window=5, slow_window=5)
    with pytest.raises(ValueError, match="positive"):
        MovingAverageCrossover(["AAPL"], fast_window=0, slow_window=3)
