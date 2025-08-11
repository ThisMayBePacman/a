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
def _make_ohlc(n: int, noise: float = 0.0) -> pd.DataFrame:
    rng = pd.RangeIndex(n)
    base = 100.0
    # bruit contrôlé pour éventuelle volatilité
    close = base + pd.Series(np.cumsum(np.random.default_rng(0).normal(0, noise, n)), index=rng)
    high = close + 1.0
    low = close - 1.0
    open_ = close.shift(1, fill_value=base)
    vol = pd.Series(10.0, index=rng)
    return pd.DataFrame({"time": rng, "open": open_, "high": high, "low": low, "close": close, "volume": vol})

def test_compute_indicators_handles_nans_gracefully():
    df = _make_ohlc(30, noise=0.0)
    # injecte quelques NaN
    df.loc[5:7, ["high", "low", "close"]] = np.nan
    out = compute_indicators(df, timeframe="1m")
    # Colonne présente et pas d'exception ; fin de série définie (ou NaN si très courte)
    assert "ATR14" in out.columns
    # tant que suffisamment de points existent, le dernier devrait être numérique
    assert out["ATR14"].iloc[-1] == out["ATR14"].iloc[-1]  # not NaN

def test_compute_indicators_atr_increases_with_volatility():
    df_low = _make_ohlc(100, noise=0.01)
    df_high = _make_ohlc(100, noise=0.50)
    atr_low = compute_indicators(df_low, timeframe="1m")["ATR14"].iloc[-1]
    atr_high = compute_indicators(df_high, timeframe="1m")["ATR14"].iloc[-1]
    # ATR doit être plus grand sur la série plus volatile
    assert atr_high > atr_low