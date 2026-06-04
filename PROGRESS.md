# Lattice — Build Progress

A living checklist of what Lattice has accomplished, so work can resume even if a
working session is lost. See the project brief for the full vision and the
staged roadmap. **The non-negotiable principle:** a strategy may only ever see
data knowable as of the current simulated timestamp — no look-ahead, ever.

GitHub: https://github.com/ahadali1031/lattice-market

## Working mode
- Learning project. Pair-programming: **Ahad writes the conceptual-core pieces**
  (schema validation, the point-in-time accessor, the event loop, strategy /
  broker / portfolio); **Claude writes the plumbing** (sources, IO, tests,
  configs) and navigates/explains.
- Hygiene gate on every change: `uv run pytest`, `uv run mypy` (strict),
  `uv run ruff check .` must all be green before committing.

## Stage 0 — walking skeleton (IN PROGRESS)
One thin vertical slice through every layer, end to end.

- [x] **Scaffolding** — uv project (Py 3.12), package layout, tooling, README. `f131f48`
- [x] **Canonical schema** (`data/schema.py`) — column constants, pinned
      `SCHEMA`, and `enforce()` boundary guard (validate columns → strict-cast →
      reorder). *Validation guard written by Ahad.* Stores raw OHLCV **and**
      `adj_close`, with `adj_close` documented as NOT point-in-time safe. `b119adb`
- [x] **Data source** (`data/sources/`) — `DataSource` Protocol (the swappable
      "wall") + yfinance adapter splitting impure fetch from pure `_to_canonical`
      reshape; verified against a live AAPL fetch. `b1eeb18`
- [x] **Parquet store** (`data/store.py`) — write/read Hive-partitioned Parquet
      (`symbol=XXX/`); dumb byte IO, no notion of "as of T". Overwrite-per-symbol
      for Stage 0; round-trip / overwrite / filter / empty all tested.
- [x] **Point-in-time accessor** (`data/accessor.py`) — THE core piece: a
      forward-only cursor with no verb to reach the future. `history()` filters
      `date <= current_date`; `advance()` only moves forward. *history() and
      advance() written by Ahad.*
- [ ] **Event loop** (`engine/`) — Market → Signal → Order → Fill, forward-only.
- [x] **Strategy interface** + moving-average crossover (`engine/strategy.py`).
      Strategy gets a read-only `MarketView` (no `advance()`), so it cannot peek.
      Emits desired exposure (LONG/EXIT) each day; portfolio turns *changes* into
      trades. *generate_signals() written by Ahad.*
- [x] **Portfolio** (`engine/portfolio.py`) — cash + holdings, equal-weight
      sizing (1/N of equity, sized at entry), fills update cash/holdings.
      *apply_fill() and target_order() written by Ahad.*
- [x] **Simulated broker** (`engine/broker.py`) — fills at next open with
      adversarial slippage (buy up, sell down) and 1%-of-value commission.
      Pure: order + fill date + open price in, FillEvent out. *fill() written by Ahad.*
      Portfolio gained a `cash_buffer` (default 2%) so sizing leaves room for costs.
- [ ] **Metrics** (`metrics/`) — total return, Sharpe, max drawdown + equity-curve plot.
- [ ] **End-to-end script** (`scripts/`) — fetch ~10 equities → store → backtest → plot.

## Stage 1 — harden the data layer (NOT STARTED)
Idempotent ingestion, point-in-time correctness, corporate actions, survivorship,
data-quality framework, async ingestion, real provider behind the same interface.

## Stage 2 — backtesting engine (NOT STARTED)
Event-driven loop, simulated broker, PIT-only reads, full portfolio accounting,
metrics module, reference strategies as fixtures.

## Stage 3 — branch: ML or execution (NOT STARTED)
To be chosen when reached.

## Design decisions log
- **Prices:** store raw OHLCV + `adj_close`. `adj_close` is retroactively
  restated by splits/dividends, so it is leak-prone; the accessor must never
  serve it as the price a strategy acts on. Stage 0 strategy trades raw `close`.
- **Partitioning:** Hive-style by symbol (`data/ohlcv/symbol=AAPL/...`).
- **Source isolation:** only `data/sources/yfinance_source.py` knows yfinance
  exists; everything else depends on the `DataSource` Protocol.
- **Separation of concerns:** the store reads all bytes; only the accessor knows
  the time boundary — so no-look-ahead lives in exactly one place.
