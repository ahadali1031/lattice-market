"""Performance metrics computed from an equity curve.

An equity curve is a polars DataFrame with columns ``date`` and ``equity`` (the
output of ``Backtest.run``). These functions turn that series into the headline
numbers: how much you made, how risky the ride was, and how bad the worst
drawdown got.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import cast

import polars as pl

# US equities trade ~252 days a year; used to annualize the Sharpe ratio.
TRADING_DAYS_PER_YEAR = 252


def daily_returns(curve: pl.DataFrame) -> pl.Series:
    """Day-over-day fractional change in equity (the first day is dropped)."""
    return curve["equity"].pct_change().drop_nulls()


def total_return(curve: pl.DataFrame) -> float:
    """Overall growth: final equity / starting equity - 1."""
    equity = curve["equity"]
    start = cast(float, equity.head(1).item())
    end = cast(float, equity.tail(1).item())
    return end / start - 1.0


def max_drawdown(curve: pl.DataFrame) -> float:
    """Worst peak-to-trough fall, as a negative fraction (e.g. -0.25 = -25%).

    At each point, drawdown = equity / running-peak - 1 (zero at new highs,
    negative below a prior peak). The max drawdown is the most negative of these.
    """
    equity = curve["equity"]
    running_peak = equity.cum_max()
    drawdown = equity / running_peak - 1.0
    return cast(float, drawdown.min())


def sharpe_ratio(curve: pl.DataFrame, periods_per_year: int = TRADING_DAYS_PER_YEAR) -> float:
    """Annualized Sharpe ratio (risk-free rate assumed 0 for Stage 0).

    Mean daily return divided by its volatility (std dev), scaled to a year by
    sqrt(periods). Returns 0.0 when there is too little data or no variation.
    """
    returns = daily_returns(curve)
    if returns.len() < 2:
        return 0.0
    std = cast(float, returns.std())
    if std == 0.0:
        return 0.0
    mean = cast(float, returns.mean())
    return mean / std * math.sqrt(periods_per_year)


@dataclass(frozen=True)
class Summary:
    """The three Stage 0 headline metrics, with a human-readable string form."""

    total_return: float
    sharpe: float
    max_drawdown: float

    def __str__(self) -> str:
        return (
            f"Total return : {self.total_return:+.2%}\n"
            f"Sharpe ratio : {self.sharpe:.2f}\n"
            f"Max drawdown : {self.max_drawdown:.2%}"
        )


def summarize(curve: pl.DataFrame) -> Summary:
    """Compute all three headline metrics at once."""
    return Summary(
        total_return=total_return(curve),
        sharpe=sharpe_ratio(curve),
        max_drawdown=max_drawdown(curve),
    )
