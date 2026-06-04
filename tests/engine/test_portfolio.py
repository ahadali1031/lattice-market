"""Spec for the portfolio: sizing, fills, and mark-to-market."""

import datetime as dt

from lattice.engine.events import FillEvent, Side, SignalEvent, SignalType
from lattice.engine.portfolio import Portfolio

_DAY = dt.date(2020, 1, 6)


def _portfolio() -> Portfolio:
    # Two symbols -> N=2, so each long position targets half of equity.
    return Portfolio(["AAPL", "MSFT"], starting_cash=100_000.0)


def test_starts_with_equity_equal_to_cash() -> None:
    p = _portfolio()
    assert p.equity({}) == 100_000.0
    assert p.shares("AAPL") == 0


def test_long_when_flat_sizes_to_half_equity() -> None:
    p = _portfolio()
    order = p.target_order(
        SignalEvent(_DAY, "AAPL", SignalType.LONG), price=100.0, equity=100_000.0
    )
    assert order is not None
    assert order.side is Side.BUY
    assert order.quantity == 500  # 50_000 target / 100 price


def test_long_when_already_long_holds() -> None:
    p = _portfolio()
    p.apply_fill(FillEvent(_DAY, "AAPL", Side.BUY, 500, fill_price=100.0, commission=1.0))
    order = p.target_order(
        SignalEvent(_DAY, "AAPL", SignalType.LONG), price=110.0, equity=100_000.0
    )
    assert order is None


def test_exit_sells_whole_position() -> None:
    p = _portfolio()
    p.apply_fill(FillEvent(_DAY, "AAPL", Side.BUY, 500, fill_price=100.0, commission=1.0))
    order = p.target_order(
        SignalEvent(_DAY, "AAPL", SignalType.EXIT), price=110.0, equity=100_000.0
    )
    assert order is not None
    assert order.side is Side.SELL
    assert order.quantity == 500


def test_exit_when_flat_does_nothing() -> None:
    p = _portfolio()
    order = p.target_order(SignalEvent(_DAY, "MSFT", SignalType.EXIT), price=50.0, equity=100_000.0)
    assert order is None


def test_buy_fill_reduces_cash_and_adds_shares() -> None:
    p = _portfolio()
    p.apply_fill(FillEvent(_DAY, "AAPL", Side.BUY, 500, fill_price=100.0, commission=1.0))
    assert p.cash == 100_000.0 - 500 * 100.0 - 1.0  # 49_999.0
    assert p.shares("AAPL") == 500
    # Mark-to-market: cash + 500 shares @ 100 = back to ~starting minus commission.
    assert p.equity({"AAPL": 100.0}) == 99_999.0


def test_sell_fill_raises_cash_and_removes_shares() -> None:
    p = _portfolio()
    p.apply_fill(FillEvent(_DAY, "AAPL", Side.BUY, 500, fill_price=100.0, commission=1.0))
    p.apply_fill(FillEvent(_DAY, "AAPL", Side.SELL, 500, fill_price=110.0, commission=1.0))
    assert p.shares("AAPL") == 0
    assert p.cash == 49_999.0 + 500 * 110.0 - 1.0  # 104_998.0
