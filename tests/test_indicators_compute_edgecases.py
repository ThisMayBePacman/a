# path: tests/test_indicators_compute_edgecases.py
import numpy as np
import pandas as pd

from indicators.compute import compute_indicators


def _df_len(n: int) -> pd.DataFrame:
    idx = pd.RangeIndex(n)
    close = pd.Series(100.0, index=idx)
    high = close + 1.0
    low = close - 1.0
    open_ = close
    vol = pd.Series(10.0, index=idx)
    return pd.DataFrame({"time": idx, "open": open_, "high": high, "low": low, "close": close, "volume": vol})


def test_compute_indicators_min_length_all_nan():
    # Série trop courte pour ATR14 -> colonne présente mais NaN
    df = _df_len(3)
    out = compute_indicators(df, timeframe="1m")
    assert "ATR14" in out.columns
    assert out["ATR14"].isna().all()


def test_compute_indicators_exact_window_stabilizes():
    # Longueur exactement 14 puis 15: la dernière valeur ne doit pas être NaN au second cas
    df14 = _df_len(14)
    out14 = compute_indicators(df14, timeframe="1m")
    assert "ATR14" in out14.columns
    # suivant: 15 points
    df15 = _df_len(15)
    out15 = compute_indicators(df15, timeframe="1m")
    assert not out15["ATR14"].iloc[-1] != out15["ATR14"].iloc[-1]  # not NaN
