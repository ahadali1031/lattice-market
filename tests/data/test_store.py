"""Tests for the Parquet store (round-trip, overwrite, filtering, empty)."""

import datetime as dt
from pathlib import Path

import polars as pl

from lattice.data import schema, store


def _frame(symbol: str, closes: list[float], start_day: int = 2) -> pl.DataFrame:
    n = len(closes)
    return schema.enforce(
        pl.DataFrame(
            {
                schema.SYMBOL: [symbol] * n,
                schema.DATE: [dt.date(2020, 1, start_day + i) for i in range(n)],
                schema.OPEN: closes,
                schema.HIGH: closes,
                schema.LOW: closes,
                schema.CLOSE: closes,
                schema.ADJ_CLOSE: closes,
                schema.VOLUME: [1000 * (i + 1) for i in range(n)],
            }
        )
    )


def test_round_trip_multiple_symbols(tmp_path: Path) -> None:
    frame = pl.concat([_frame("AAPL", [1.0, 2.0]), _frame("MSFT", [3.0, 4.0])])
    store.write(frame, tmp_path)

    out = store.read(tmp_path)
    assert out.schema == schema.SCHEMA
    assert out.columns == schema.COLUMNS
    assert out[schema.SYMBOL].to_list() == ["AAPL", "AAPL", "MSFT", "MSFT"]
    assert out[schema.CLOSE].to_list() == [1.0, 2.0, 3.0, 4.0]


def test_partition_layout_on_disk(tmp_path: Path) -> None:
    store.write(_frame("AAPL", [1.0]), tmp_path)
    assert (tmp_path / "symbol=AAPL" / "data.parquet").exists()


def test_overwrite_does_not_duplicate(tmp_path: Path) -> None:
    store.write(_frame("AAPL", [1.0, 2.0]), tmp_path)
    store.write(_frame("AAPL", [9.0]), tmp_path)  # re-write replaces the partition

    out = store.read(tmp_path)
    assert out.height == 1
    assert out[schema.CLOSE].to_list() == [9.0]


def test_read_filters_by_symbol(tmp_path: Path) -> None:
    store.write(pl.concat([_frame("AAPL", [1.0]), _frame("MSFT", [3.0])]), tmp_path)

    out = store.read(tmp_path, symbols=["MSFT"])
    assert out[schema.SYMBOL].unique().to_list() == ["MSFT"]


def test_read_empty_store_returns_empty_canonical_frame(tmp_path: Path) -> None:
    out = store.read(tmp_path / "does-not-exist")
    assert out.height == 0
    assert out.schema == schema.SCHEMA
