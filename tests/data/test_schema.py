"""Tests for the canonical OHLCV schema contract."""

import datetime as dt

import polars as pl
import pytest

from lattice.data import schema


def _valid_frame() -> pl.DataFrame:
    """A minimal frame already in canonical column order and types."""
    return pl.DataFrame(
        {
            schema.SYMBOL: ["AAPL"],
            schema.DATE: [dt.date(2020, 1, 2)],
            schema.OPEN: [74.06],
            schema.HIGH: [75.15],
            schema.LOW: [73.80],
            schema.CLOSE: [75.09],
            schema.ADJ_CLOSE: [72.88],
            schema.VOLUME: [135480400],
        },
        schema=schema.SCHEMA,
    )


def test_enforce_accepts_canonical_frame() -> None:
    frame = _valid_frame()
    out = schema.enforce(frame)
    assert out.schema == schema.SCHEMA
    assert out.columns == schema.COLUMNS


def test_enforce_reorders_and_casts() -> None:
    # Columns shuffled and prices arriving as strings; enforce should fix both.
    frame = pl.DataFrame(
        {
            schema.VOLUME: [135480400],
            schema.SYMBOL: ["AAPL"],
            schema.DATE: ["2020-01-02"],
            schema.OPEN: ["74.06"],
            schema.HIGH: ["75.15"],
            schema.LOW: ["73.80"],
            schema.CLOSE: ["75.09"],
            schema.ADJ_CLOSE: ["72.88"],
        }
    )
    out = schema.enforce(frame)
    assert out.columns == schema.COLUMNS
    assert out.schema == schema.SCHEMA
    assert out[schema.OPEN][0] == pytest.approx(74.06)


def test_enforce_rejects_missing_column() -> None:
    frame = _valid_frame().drop(schema.ADJ_CLOSE)
    with pytest.raises(ValueError, match="missing required columns"):
        schema.enforce(frame)


def test_enforce_rejects_extra_column() -> None:
    frame = _valid_frame().with_columns(pl.lit(1.0).alias("dividends"))
    with pytest.raises(ValueError, match="unexpected columns"):
        schema.enforce(frame)


def test_enforce_raises_on_unparseable_value() -> None:
    frame = _valid_frame().with_columns(pl.lit("not-a-number").alias(schema.OPEN))
    with pytest.raises(Exception):  # noqa: B017 - polars raises a typed error; any is fine here
        schema.enforce(frame)
