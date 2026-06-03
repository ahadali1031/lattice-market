# Lattice

A quant data + backtesting platform. Lattice turns raw market data into a clean,
point-in-time-correct historical store, then replays it through an event-driven
engine to evaluate trading strategies under realistic constraints — commissions,
slippage, and strictly **no look-ahead bias**. It is built for correctness and
reproducibility first.

## The non-negotiable principle

> A strategy may only ever see data that was knowable as of the current
> simulated timestamp. No look-ahead, ever.

The architecture is designed to make peeking at the future *structurally
awkward*, not merely discouraged by a comment.

## Stage 0 pipeline (the walking skeleton)

```
~10 liquid US stocks
  → fetched via yfinance, behind a swappable source interface
  → cleaned & stored as partitioned Parquet (one folder per symbol)
  → read through a point-in-time accessor (never reveals data after date T)
  → driven by a forward-only event loop (Market → Signal → Order → Fill)
  → strategy: moving-average crossover, trading next-open w/ slippage + commission
  → portfolio tracked → equity curve
  → judged by total return, max drawdown, Sharpe ratio
```

## Project layout

```
src/lattice/
  data/
    sources/   the "wall": provider-specific code (yfinance) behind an interface
    schema.py  the canonical shape of one OHLCV row
    store.py   dumb Parquet read/write
    accessor.py  point-in-time gatekeeper (the heart of "no look-ahead")
  engine/
    events.py    Market / Signal / Order / Fill
    loop.py      the event loop
    strategy.py  the Strategy interface
    broker.py    simulated fills, slippage, commission
    portfolio.py cash + holdings accounting
  metrics/     returns, Sharpe, drawdown, plotting
  execution/   reserved for Stage 3 (paper trading) — empty for now
  ml/          reserved for Stage 3 (feature store + models) — empty for now
scripts/       runnable end-to-end demos
tests/         mirrors the package layout
data/ohlcv/    local Parquet store (gitignored)
```

## Development

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12.

```bash
uv sync                 # create the virtual env and install everything
uv run pytest           # run tests
uv run ruff check .     # lint
uv run ruff format .    # format
uv run mypy             # type-check (strict)
```
