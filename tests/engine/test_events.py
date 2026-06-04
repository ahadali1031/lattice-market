"""Smoke tests for the event vocabulary: construction and immutability."""

import dataclasses
import datetime as dt

import pytest

from lattice.engine.events import (
    FillEvent,
    MarketEvent,
    OrderEvent,
    Side,
    SignalEvent,
    SignalType,
)


def test_events_construct_with_expected_fields() -> None:
    d = dt.date(2020, 1, 6)
    assert MarketEvent(d).date == d
    assert SignalEvent(d, "AAPL", SignalType.LONG).signal is SignalType.LONG
    assert OrderEvent(d, "AAPL", Side.BUY, 100).quantity == 100

    fill = FillEvent(d, "AAPL", Side.BUY, 100, fill_price=101.0, commission=1.0)
    assert fill.fill_price == 101.0
    assert fill.commission == 1.0


def test_events_are_frozen() -> None:
    fill = FillEvent(dt.date(2020, 1, 6), "AAPL", Side.SELL, 50, 99.0, 1.0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        fill.quantity = 999  # type: ignore[misc]
