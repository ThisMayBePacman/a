# path: tests/test_indicators_compute.py
import pandas as pd
import numpy as np
import pytest

from indicators.compute import compute_indicators


def _dummy_ohlc(n: int = 50) -> pd.DataFrame:
    rng = pd.RangeIndex(n)
    base = 100.0
    close = pd.Series(base + np.sin(np.linspace(0, 10, n)), index=rng)
    high = close + 1.0
    low = close - 1.0
    open_ = close.shift(1, fill_value=base)
    vol = pd.Series(10.0, index=rng)
    return pd.DataFrame({"time": rng, "open": open_, "high": high, "low": low, "close": close, "volume": vol})


def test_compute_indicators_adds_atr14_column():
    df = _dummy_ohlc(60)
    out = compute_indicators(df, timeframe="1m")
    assert "ATR14" in out.columns
    # La série ne doit pas être entièrement NaN (après le burn-in)
    assert out["ATR14"].iloc[-1] == out["ATR14"].iloc[-1]  # not NaN


def test_compute_indicators_handles_short_input():
    df = _dummy_ohlc(5)
    out = compute_indicators(df, timeframe="1m")
    # Colonne présente même si courte; valeurs probablement NaN
    assert "ATR14" in out.columns
