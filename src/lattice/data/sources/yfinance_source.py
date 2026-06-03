"""yfinance implementation of the DataSource interface (Stage 0 only).

This is the ONLY module in Lattice that knows yfinance exists. It does two jobs,
deliberately kept separate:

* ``fetch_daily`` — the impure part: make the network call. Thin and untestable.
* ``_to_canonical`` — the pure part: reshape yfinance's pandas output into our
  canonical polars frame. No network, so it is fully unit-testable with a
  synthetic frame that mimics what yfinance returns.

Keeping the messy translation in a pure function is the whole point: when Stage 1
swaps in a real provider, only this file is rewritten, and its logic was provable
without a flaky live dependency.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import polars as pl
import yfinance as yf

from lattice.data import schema

# yfinance's column names -> our canonical names. yfinance capitalizes and puts a
# space in "Adj Close"; this map is the entire provider-specific vocabulary.
_YF_TO_CANONICAL: dict[str, str] = {
    "Date": schema.DATE,
    "Open": schema.OPEN,
    "High": schema.HIGH,
    "Low": schema.LOW,
    "Close": schema.CLOSE,
    "Adj Close": schema.ADJ_CLOSE,
    "Volume": schema.VOLUME,
}


class YFinanceSource:
    """Fetches daily bars from yfinance and returns them in canonical schema."""

    def fetch_daily(self, symbol: str, start: dt.date, end: dt.date) -> pl.DataFrame:
        # yfinance treats `end` as EXCLUSIVE; we promise an inclusive range, so
        # nudge it forward a day. auto_adjust=False is required to keep BOTH raw
        # OHLC and the separate "Adj Close" column (with auto_adjust=True yfinance
        # silently overwrites OHLC with adjusted values and drops "Adj Close").
        raw = yf.download(
            symbol,
            start=start,
            end=end + dt.timedelta(days=1),
            interval="1d",
            auto_adjust=False,
            actions=False,
            progress=False,
        )
        if raw is None or raw.empty:
            raise ValueError(f"yfinance returned no data for {symbol!r} in [{start}, {end}]")
        return _to_canonical(raw, symbol)


def _to_canonical(raw: pd.DataFrame, symbol: str) -> pl.DataFrame:
    """Reshape a yfinance daily frame into Lattice's canonical schema.

    Pure: takes the pandas frame yfinance produces and returns an enforced polars
    frame. All the provider-specific quirks are handled here.
    """
    df = raw.copy()

    # For a single ticker, recent yfinance returns MultiIndex columns of
    # (field, ticker), e.g. ("Open", "AAPL"). Flatten to just the field names.
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # The trading date lives in the DatetimeIndex; lift it into a real column.
    df = df.reset_index()

    # Rename provider columns to canonical, then keep only the ones we recognize.
    # An unexpected/missing provider column surfaces at schema.enforce below.
    df = df.rename(columns=_YF_TO_CANONICAL)
    known = [c for c in _YF_TO_CANONICAL.values() if c in df.columns]
    df = df[known]

    frame = pl.from_pandas(df)
    # yfinance does not include the symbol; it is the partition key, so add it.
    frame = frame.with_columns(pl.lit(symbol).alias(schema.SYMBOL))

    # Final boundary check: prove the frame matches the canonical schema (this is
    # where date-time gets cast to a plain Date, types are pinned, order is fixed).
    return schema.enforce(frame)
