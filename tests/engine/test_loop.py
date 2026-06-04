"""Integration tests for the backtest loop."""

import datetime as dt

import polars as pl

from lattice.data import schema
from lattice.data.accessor import PointInTimeAccessor
from lattice.engine.broker import SimulatedBroker
from lattice.engine.loop import Backtest
from lattice.engine.portfolio import Portfolio
from lattice.engine.strategy import MovingAverageCrossover


def _frame(symbol: str, closes: list[float]) -> pl.DataFrame:
    n = len(closes)
    dates = [dt.date(2020, 1, 6) + dt.timedelta(days=i) for i in range(n)]
    return schema.enforce(
        pl.DataFrame(
            {
                schema.SYMBOL: [symbol] * n,
                schema.DATE: dates,
                schema.OPEN: closes,  # O=H=L=C keeps fills predictable
                schema.HIGH: closes,
                schema.LOW: closes,
                schema.CLOSE: closes,
                schema.ADJ_CLOSE: closes,
                schema.VOLUME: [1_000] * n,
            }
        )
    )


def _backtest(frame: pl.DataFrame, symbols: list[str], cash: float = 100_000.0) -> Backtest:
    accessor = PointInTimeAccessor(frame)
    strategy = MovingAverageCrossover(symbols, fast_window=2, slow_window=3)
    portfolio = Portfolio(symbols, starting_cash=cash)
    broker = SimulatedBroker(commission_rate=0.01, slippage_rate=0.0005)
    return Backtest(accessor, strategy, portfolio, broker, symbols)


def test_equity_curve_has_one_row_per_trading_day() -> None:
    frame = _frame("AAPL", [100.0 + i for i in range(10)])
    curve = _backtest(frame, ["AAPL"]).run()
    assert curve.height == 10
    assert curve.columns == ["date", "equity"]


def test_first_day_equity_equals_starting_cash() -> None:
    frame = _frame("AAPL", [100.0 + i for i in range(10)])
    curve = _backtest(frame, ["AAPL"]).run()
    # Day 0: no trades yet, all cash.
    assert curve["equity"][0] == 100_000.0


def test_uptrend_takes_a_position_and_grows() -> None:
    # Monotonic rise -> fast MA stays above slow -> go long early and hold.
    frame = _frame("AAPL", [100.0 + i for i in range(12)])
    bt = _backtest(frame, ["AAPL"])
    portfolio = bt._portfolio
    curve = bt.run()
    assert portfolio.shares("AAPL") > 0  # ended holding a position
    assert curve["equity"][-1] > 100_000.0  # net positive despite costs


def test_insufficient_history_never_trades() -> None:
    # Only 2 bars but slow window is 3 -> no signal ever -> equity stays flat.
    frame = _frame("AAPL", [100.0, 101.0])
    bt = _backtest(frame, ["AAPL"])
    curve = bt.run()
    assert curve["equity"].to_list() == [100_000.0, 100_000.0]
    assert bt._portfolio.shares("AAPL") == 0
