"""Equity-curve plotting (matplotlib)."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless backend; must be set before importing pyplot

import matplotlib.pyplot as plt  # noqa: E402
import polars as pl  # noqa: E402


def plot_equity_curve(
    curve: pl.DataFrame, path: Path, title: str = "Lattice — Equity Curve"
) -> Path:
    """Plot the (date, equity) curve and save it to ``path``; returns ``path``."""
    dates = curve["date"].to_list()
    equity = curve["equity"].to_list()

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(dates, equity, color="#2563eb", linewidth=1.5)
    ax.set_title(title)
    ax.set_xlabel("Date")
    ax.set_ylabel("Equity ($)")
    ax.grid(True, alpha=0.3)
    fig.autofmt_xdate()

    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path
