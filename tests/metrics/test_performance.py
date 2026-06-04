"""Tests for the performance metrics."""

import datetime as dt

import polars as pl
import pytest

from lattice.metrics.performance import (
    max_drawdown,
    sharpe_ratio,
    summarize,
    total_return,
)


def _curve(equities: list[float]) -> pl.DataFrame:
    dates = [dt.date(2020, 1, 6) + dt.timedelta(days=i) for i in range(len(equities))]
    return pl.DataFrame({"date": dates, "equity": [float(e) for e in equities]})


def test_total_return() -> None:
    assert total_return(_curve([100, 110, 121])) == pytest.approx(0.21)


def test_max_drawdown_finds_worst_fall() -> None:
    # peak 120 then trough 90 -> -25%.
    assert max_drawdown(_curve([100, 120, 90, 100])) == pytest.approx(-0.25)


def test_no_drawdown_when_monotonic() -> None:
    assert max_drawdown(_curve([100, 110, 120])) == pytest.approx(0.0)


def test_sharpe_positive_for_steady_gains() -> None:
    assert sharpe_ratio(_curve([100, 101, 102, 103])) > 0


def test_sharpe_zero_when_flat() -> None:
    assert sharpe_ratio(_curve([100, 100, 100])) == 0.0


def test_summarize_bundles_all_three() -> None:
    summary = summarize(_curve([100, 120, 90, 100]))
    assert summary.total_return == pytest.approx(0.0)
    assert summary.max_drawdown == pytest.approx(-0.25)
    assert isinstance(str(summary), str)
