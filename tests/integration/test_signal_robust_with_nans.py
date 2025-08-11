# path: tests/integration/test_signal_robust_with_nans.py
import numpy as np
import pandas as pd

from indicators.compute import compute_indicators
from strategy.signal import generate_signal


def _ohlc_with_nans(n: int) -> pd.DataFrame:
    idx = pd.RangeIndex(n)
    close = pd.Series(100.0 + np.linspace(0, 1, n), index=idx)
    high = close + 1.0
    low = close - 1.0
    open_ = close.shift(1, fill_value=100.0)
    vol = pd.Series(100.0, index=idx)
    df = pd.DataFrame({"time": idx, "open": open_, "high": high, "low": low, "close": close, "volume": vol})
    # Injecte des NaN
    df.loc[5:7, ["high", "low", "close"]] = np.nan
    return df


def test_generate_signal_handles_nans_and_returns_neutral():
    m15 = compute_indicators(_ohlc_with_nans(80), timeframe="15m")
    m5 = compute_indicators(_ohlc_with_nans(50), timeframe="5m")
    out = generate_signal(m15.tail(1), m5.tail(3))
    # Le signal ne doit pas planter et reste neutre si conditions non réunies
    assert out["long"] is False
    assert out["short"] is False
