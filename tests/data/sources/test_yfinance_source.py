"""Tests for the pure yfinance -> canonical reshaping (no network)."""

import datetime as dt

import pandas as pd
import polars as pl

from lattice.data import schema
from lattice.data.sources.yfinance_source import _to_canonical


def _yf_frame_flat() -> pd.DataFrame:
    """A yfinance daily frame with simple columns and a DatetimeIndex."""
    idx = pd.DatetimeIndex([dt.date(2020, 1, 2), dt.date(2020, 1, 3)], name="Date")
    return pd.DataFrame(
        {
            "Open": [74.06, 74.29],
            "High": [75.15, 75.14],
            "Low": [73.80, 74.13],
            "Close": [75.09, 74.36],
            "Adj Close": [72.88, 72.17],
            "Volume": [135480400, 146322800],
        },
        index=idx,
    )


def _yf_frame_multiindex() -> pd.DataFrame:
    """Same data, but with the (field, ticker) MultiIndex newer yfinance emits."""
    flat = _yf_frame_flat()
    flat.columns = pd.MultiIndex.from_product([flat.columns, ["AAPL"]])
    return flat


def test_to_canonical_matches_schema() -> None:
    out = _to_canonical(_yf_frame_flat(), "AAPL")
    assert out.schema == schema.SCHEMA
    assert out.columns == schema.COLUMNS


def test_to_canonical_values_and_symbol() -> None:
    out = _to_canonical(_yf_frame_flat(), "AAPL")
    assert out.height == 2
    assert out[schema.SYMBOL].to_list() == ["AAPL", "AAPL"]
    assert out[schema.DATE].to_list() == [dt.date(2020, 1, 2), dt.date(2020, 1, 3)]
    assert out[schema.CLOSE][0] == 75.09
    # Date arrived as a pandas Timestamp and must end up as a plain Date.
    assert out.schema[schema.DATE] == pl.Date


def test_to_canonical_flattens_multiindex() -> None:
    out = _to_canonical(_yf_frame_multiindex(), "AAPL")
    assert out.schema == schema.SCHEMA
    assert out[schema.CLOSE].to_list() == [75.09, 74.36]
