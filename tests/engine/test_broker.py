"""Spec for the simulated broker: slippage direction and commission."""

import datetime as dt

import pytest

from lattice.engine.broker import SimulatedBroker
from lattice.engine.events import OrderEvent, Side

_DAY = dt.date(2020, 1, 7)


def test_commission_is_one_percent_of_value() -> None:
    broker = SimulatedBroker(commission_rate=0.01, slippage_rate=0.0)
    order = OrderEvent(_DAY, "AAPL", Side.BUY, 100)
    fill = broker.fill(order, fill_date=_DAY, open_price=100.0)
    assert fill.fill_price == 100.0  # no slippage
    assert fill.commission == 100.0  # 0.01 * 100 shares * 100.0


def test_buy_slips_up() -> None:
    broker = SimulatedBroker(commission_rate=0.0, slippage_rate=0.01)
    fill = broker.fill(OrderEvent(_DAY, "AAPL", Side.BUY, 100), _DAY, open_price=100.0)
    assert fill.fill_price == 101.0  # buy fills higher
    assert fill.commission == 0.0


def test_sell_slips_down() -> None:
    broker = SimulatedBroker(commission_rate=0.0, slippage_rate=0.01)
    fill = broker.fill(OrderEvent(_DAY, "AAPL", Side.SELL, 100), _DAY, open_price=100.0)
    assert fill.fill_price == 99.0  # sell fills lower


def test_fill_carries_order_details() -> None:
    broker = SimulatedBroker(commission_rate=0.01, slippage_rate=0.01)
    order = OrderEvent(_DAY, "MSFT", Side.BUY, 10)
    fill = broker.fill(order, fill_date=_DAY, open_price=200.0)
    assert fill.symbol == "MSFT"
    assert fill.side is Side.BUY
    assert fill.quantity == 10
    assert fill.date == _DAY
    assert fill.fill_price == 202.0  # 200 * 1.01
    assert fill.commission == pytest.approx(0.01 * 10 * 202.0)  # 20.2


def test_rejects_negative_rates() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        SimulatedBroker(commission_rate=-0.01)
