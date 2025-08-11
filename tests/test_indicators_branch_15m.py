# path: tests/test_indicators_branch_15m.py
import numpy as np
import pandas as pd

from indicators.compute import compute_indicators


def _make_df(n: int = 60) -> pd.DataFrame:
    idx = pd.RangeIndex(n)
    base = 100.0
    # petite sinusoïde pour des valeurs non constantes
    close = base + np.sin(np.linspace(0, 10, n))
    high = close + 1.0
    low = close - 1.0
    open_ = pd.Series(close).shift(1, fill_value=base)
    vol = pd.Series(10.0, index=idx)
    return pd.DataFrame(
        {"time": idx, "open": open_, "high": high, "low": low, "close": close, "volume": vol}
    )


def test_compute_indicators_15m_branch_adds_expected_columns():
    df = _make_df(80)
    out = compute_indicators(df, timeframe="15m")
    # Colonnes spécifiques à la branche 15m
    for col in ("EMA21", "EMA50", "RSI14"):
        assert col in out.columns
    # La dernière valeur ne doit pas être NaN (fenêtre suffisante)
    assert out["EMA21"].iloc[-1] == out["EMA21"].iloc[-1]
    assert out["EMA50"].iloc[-1] == out["EMA50"].iloc[-1]
    assert out["RSI14"].iloc[-1] == out["RSI14"].iloc[-1]
    # Les colonnes de l'autre branche ne sont pas requises ici
    assert "ATR14" not in out.columns
