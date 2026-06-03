"""Dumb Parquet store: persist and load canonical OHLCV, partitioned by symbol.

The store knows how to read and write bytes. It deliberately does NOT know about
"as of date T" — it can see *all* the data, all the time. The point-in-time
boundary lives one layer up, in ``accessor.py``. Keeping "read the bytes" apart
from "what are you allowed to see" is what keeps the no-look-ahead rule in
exactly one place instead of smeared across the codebase.

Layout — Hive-style partitioning by symbol::

    {root}/symbol=AAPL/data.parquet
    {root}/symbol=MSFT/data.parquet

The symbol lives in the *directory name*, not inside the file; on read it is
reconstructed from the path. This is the standard Hive convention, so external
tools (pyarrow, DuckDB, Spark) understand the same layout for free.
"""

from __future__ import annotations

import shutil
from collections.abc import Iterable
from pathlib import Path

import polars as pl

from lattice.data import schema

_PART_GLOB = f"{schema.SYMBOL}=*/*.parquet"


def write(frame: pl.DataFrame, root: Path) -> None:
    """Persist ``frame`` (one or many symbols), overwriting each symbol's partition.

    Stage 0 is a dumb overwrite-per-symbol: re-writing a symbol replaces its
    partition wholesale. (Idempotent gap-filling is a Stage 1 concern.) The frame
    is enforced first, so only canonical data ever reaches disk.
    """
    frame = schema.enforce(frame)

    for key, part in frame.partition_by(schema.SYMBOL, as_dict=True).items():
        symbol = key[0] if isinstance(key, tuple) else key
        part_dir = root / f"{schema.SYMBOL}={symbol}"

        # Overwrite this symbol's partition wholesale.
        if part_dir.exists():
            shutil.rmtree(part_dir)
        part_dir.mkdir(parents=True, exist_ok=True)

        # Drop the symbol column — it is encoded in the directory name and would
        # be redundant in the file. Sort by date so the file is in ascending
        # order, the contract every reader downstream relies on.
        out = part.sort(schema.DATE).drop(schema.SYMBOL)
        out.write_parquet(part_dir / "data.parquet")


def read(root: Path, symbols: Iterable[str] | None = None) -> pl.DataFrame:
    """Load bars from the store as one canonical frame, sorted by (symbol, date).

    With ``symbols=None`` every symbol in the store is returned; otherwise only
    the requested ones. An empty or missing store yields an empty canonical frame
    rather than raising, so callers can treat "no data yet" uniformly.
    """
    if not root.exists() or not any(root.glob(_PART_GLOB)):
        return pl.DataFrame(schema=schema.SCHEMA)

    # hive_partitioning=True reconstructs the `symbol` column from each path.
    frame = pl.read_parquet(root / _PART_GLOB, hive_partitioning=True)

    if symbols is not None:
        frame = frame.filter(pl.col(schema.SYMBOL).is_in(list(symbols)))

    # enforce fixes what Hive reading leaves loose: the partition column may come
    # back as a different dtype and the column order is not guaranteed.
    return schema.enforce(frame).sort(schema.SYMBOL, schema.DATE)
