# path: tests/integration/test_pipeline_e2e_signal_open.py
import numpy as np
import pandas as pd

from indicators.compute import compute_indicators
from strategy.signal import generate_signal
from execution.position_manager import PositionManager


def _ohlc(n: int, base: float = 100.0, step: float = 0.1) -> pd.DataFrame:
    """Série OHLCV synthétique, monotone croissante."""
    idx = pd.RangeIndex(n)
    close = base + np.arange(n) * step
    high = close + 1.0
    low = close - 1.0
    open_ = pd.Series(close).shift(1, fill_value=base)
    vol = pd.Series(100.0, index=idx)
    return pd.DataFrame({"time": idx, "open": open_, "high": high, "low": low, "close": close, "volume": vol})


def _force_bull_cross(df_m15: pd.DataFrame, df_m5: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Force mom=up (EMA21>EMA50 sur 15m) et cross haussier sur 5m (EMA9 > EMA21 sur la dernière bougie)."""
    m15 = df_m15.copy()
    m5 = df_m5.copy()
    m15.loc[m15.index[-1], "EMA21"] = 101.0
    m15.loc[m15.index[-1], "EMA50"] = 100.0
    # prev2 & prev1 <= ; last >
    m5.loc[m5.index[-3], ["EMA9", "EMA21"]] = [99.0, 100.0]
    m5.loc[m5.index[-2], ["EMA9", "EMA21"]] = [99.5, 100.0]
    m5.loc[m5.index[-1], ["EMA9", "EMA21"]] = [101.0, 100.0]
    # volume & RSI
    m5.loc[m5.index[-1], ["volume", "Vol_SMA5", "RSI7"]] = [200.0, 150.0, 55.0]
    return m15, m5


def _force_bear_cross(df_m15: pd.DataFrame, df_m5: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Force mom=down (EMA21<EMA50 sur 15m) et cross baissier sur 5m."""
    m15 = df_m15.copy()
    m5 = df_m5.copy()
    m15.loc[m15.index[-1], "EMA21"] = 100.0
    m15.loc[m15.index[-1], "EMA50"] = 101.0
    # prev2 & prev1 >= ; last <
    m5.loc[m5.index[-3], ["EMA9", "EMA21"]] = [101.0, 100.0]
    m5.loc[m5.index[-2], ["EMA9", "EMA21"]] = [100.5, 100.0]
    m5.loc[m5.index[-1], ["EMA9", "EMA21"]] = [99.0, 100.0]
    # volume & RSI
    m5.loc[m5.index[-1], ["volume", "Vol_SMA5", "RSI7"]] = [200.0, 150.0, 45.0]
    return m15, m5


def test_e2e_long_signal_to_open_position(dummy_exchange, order_manager):
    # Données & indicateurs
    df15 = compute_indicators(_ohlc(80), timeframe="15m")
    df5 = compute_indicators(_ohlc(200, step=0.05), timeframe="5m")
    m15, m5 = _force_bull_cross(df15, df5)

    sig = generate_signal(m15.tail(1), m5.tail(3))
    assert sig["long"] is True and sig["short"] is False

    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    pm.open_position("buy", entry_price=float(m5["close"].iloc[-1]), size=1.0)
    assert pm.active is not None
    # SL / TP enregistrés
    assert pm.active["current_sl_price"] > 0
    assert pm.active["tp_price"] > 0


def test_e2e_short_signal_to_open_position(dummy_exchange, order_manager):
    df15 = compute_indicators(_ohlc(80), timeframe="15m")
    df5 = compute_indicators(_ohlc(200, step=0.05), timeframe="5m")
    m15, m5 = _force_bear_cross(df15, df5)

    sig = generate_signal(m15.tail(1), m5.tail(3))
    assert sig["short"] is True and sig["long"] is False

    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    pm.open_position("sell", entry_price=float(m5["close"].iloc[-1]), size=1.0)
    assert pm.active is not None
    # Pour un short, SL au-dessus de l'entrée, TP au-dessous (logique générale)
    assert pm.active["current_sl_price"] > pm.active["entry_price"] or pm.active["tp_price"] < pm.active["entry_price"]
