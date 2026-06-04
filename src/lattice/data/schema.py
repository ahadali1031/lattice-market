"""The canonical shape of one daily OHLCV bar in Lattice.

Every row that enters the store passes through this module, so the rest of the
system can assume a single, fixed schema no matter which provider produced the
data. This file is the *contract*: `sources/` adapt raw provider output to it,
`store.py` enforces it on write, and everything downstream trusts it blindly.

Point-in-time note
------------------
For daily bars the `date` column doubles as the "knowable as of" key: a bar for
date T (including its close) is knowable only after T's market close, so an
as-of-T accessor returns rows where ``date <= T`` and a strategy that trades the
*next* open never acts on a bar it could not have seen. Stage 1 may add a
separate ingestion timestamp for stricter point-in-time semantics; we do not
need one yet.

WARNING — adj_close is NOT point-in-time safe
---------------------------------------------
`adj_close` is retroactively restated every time a split or dividend occurs:
the adjusted price of a past date changes depending on *when you ask*. Feeding
`adj_close` into an as-of-T backtest therefore leaks the future. It is stored
here only as a reference column and a bridge to Stage 1's proper corporate-
actions handling. The Stage 0 strategy trades off raw `close`; the point-in-time
accessor must never serve `adj_close` as the price a strategy acts on.
"""

from __future__ import annotations

import polars as pl

# --- Column names -----------------------------------------------------------
# Names live as constants, not bare strings scattered through the codebase, so a
# rename is a single edit and a typo becomes a NameError instead of a silently
# empty column select.
SYMBOL = "symbol"
DATE = "date"
OPEN = "open"
HIGH = "high"
LOW = "low"
CLOSE = "close"
ADJ_CLOSE = "adj_close"
VOLUME = "volume"

# --- The canonical schema ---------------------------------------------------
# Every dtype is pinned explicitly so a bar means the same thing regardless of
# source: `date` is a calendar date (no time, no timezone — these are daily
# bars), prices are 64-bit floats (the quant-standard choice; decimals add
# friction for no real gain on equity prices), and `volume` is a 64-bit integer
# count of shares.
SCHEMA: pl.Schema = pl.Schema(
    {
        SYMBOL: pl.String,
        DATE: pl.Date,
        OPEN: pl.Float64,
        HIGH: pl.Float64,
        LOW: pl.Float64,
        CLOSE: pl.Float64,
        ADJ_CLOSE: pl.Float64,
        VOLUME: pl.Int64,
    }
)

COLUMNS: list[str] = list(SCHEMA.keys())
PRICE_COLUMNS: list[str] = [OPEN, HIGH, LOW, CLOSE, ADJ_CLOSE]


def enforce(frame: pl.DataFrame) -> pl.DataFrame:
    """Coerce ``frame`` to the canonical schema, or raise loudly.

    The single choke point every write passes through: it proves the frame has
    exactly the canonical columns, casts each to its canonical dtype, and returns
    them in canonical order. A malformed frame fails here, at the boundary,
    rather than silently corrupting the store.
    """
    received = set(frame.columns)
    required = set(COLUMNS)

    missing = required - received
    if missing:
        raise ValueError(f"frame is missing required columns: {sorted(missing)}")

    unexpected = received - required
    if unexpected:
        raise ValueError(f"frame has unexpected columns: {sorted(unexpected)}")
    return frame.select(
        pl.col(name).cast(dtype, strict=True) for name, dtype in SCHEMA.items()
    )
