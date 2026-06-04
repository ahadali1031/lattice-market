"""Stage 0 end-to-end: fetch -> store -> point-in-time backtest -> metrics + plot.

Run with:  uv run python scripts/run_stage0.py
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from lattice.data import store
from lattice.data.accessor import PointInTimeAccessor
from lattice.data.sources.yfinance_source import YFinanceSource
from lattice.engine.broker import SimulatedBroker
from lattice.engine.loop import Backtest
from lattice.engine.portfolio import Portfolio
from lattice.engine.strategy import MovingAverageCrossover
from lattice.metrics.performance import summarize
from lattice.metrics.plotting import plot_equity_curve

SYMBOLS = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "JPM", "JNJ", "V", "PG"]
START = dt.date(2018, 1, 1)
END = dt.date(2023, 12, 31)

STORE_ROOT = Path("data/ohlcv")
PLOT_PATH = Path("reports/stage0_equity_curve.png")

STARTING_CASH = 100_000.0
FAST_WINDOW = 20
SLOW_WINDOW = 50
COMMISSION_RATE = 0.01
SLIPPAGE_RATE = 0.0005


def ingest(source: YFinanceSource) -> list[str]:
    """Fetch each symbol and persist it; return the symbols that succeeded."""
    ingested: list[str] = []
    for symbol in SYMBOLS:
        try:
            frame = source.fetch_daily(symbol, START, END)
        except Exception as exc:  # noqa: BLE001 - demo script: skip a flaky symbol
            print(f"  skipped {symbol}: {exc}")
            continue
        store.write(frame, STORE_ROOT)
        ingested.append(symbol)
        print(f"  {symbol}: {frame.height} bars")
    return ingested


def main() -> None:
    print("Fetching daily bars from yfinance...")
    symbols = ingest(YFinanceSource())
    if not symbols:
        raise SystemExit("no data ingested")

    print("\nLoading point-in-time store and running backtest...")
    frame = store.read(STORE_ROOT, symbols=symbols)
    accessor = PointInTimeAccessor(frame)
    strategy = MovingAverageCrossover(symbols, fast_window=FAST_WINDOW, slow_window=SLOW_WINDOW)
    portfolio = Portfolio(symbols, starting_cash=STARTING_CASH)
    broker = SimulatedBroker(commission_rate=COMMISSION_RATE, slippage_rate=SLIPPAGE_RATE)
    curve = Backtest(accessor, strategy, portfolio, broker, symbols).run()

    print("\n=== Results ===")
    print(f"Universe     : {len(symbols)} symbols, {START} -> {END}")
    print(f"Strategy     : MA crossover {FAST_WINDOW}/{SLOW_WINDOW}")
    print(summarize(curve))

    out = plot_equity_curve(curve, PLOT_PATH)
    print(f"\nEquity curve saved to {out}")


if __name__ == "__main__":
    main()
