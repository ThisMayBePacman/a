# path: tests/test_signal.py
import pandas as pd
import pytest

from strategy.signal import generate_signal


def df_m15(ema21: float, ema50: float) -> pd.DataFrame:
    return pd.DataFrame([{"EMA21": ema21, "EMA50": ema50}])


def df_m5(rows: list[dict]) -> pd.DataFrame:
    """
    rows: trois dicts min. avec clés: EMA9, EMA21, volume, Vol_SMA5, RSI7
    """
    return pd.DataFrame(rows)


def test_generate_signal_long_bullish_cross_volume_ok():
    m15 = df_m15(ema21=101.0, ema50=100.0)  # momentum up
    m5 = df_m5([
        {"EMA9": 99.0,  "EMA21": 100.0, "volume": 120.0, "Vol_SMA5": 100.0, "RSI7": 55.0},  # prev2 (<=)
        {"EMA9": 99.5,  "EMA21": 100.0, "volume": 130.0, "Vol_SMA5": 100.0, "RSI7": 55.0},  # prev1 (<=)
        {"EMA9": 101.0, "EMA21": 100.0, "volume": 200.0, "Vol_SMA5": 150.0, "RSI7": 55.0},  # last  (>)
    ])
    out = generate_signal(m15, m5)
    assert out["mom"] == "up"
    assert out["cross"] == 1
    assert bool(out["vol_ok"])
    assert out["rsi"] == 55.0
    assert bool(out["long"])
    assert not bool(out["short"])


def test_generate_signal_short_bearish_cross_volume_ok():
    m15 = df_m15(ema21=100.0, ema50=101.0)  # momentum down
    m5 = df_m5([
        {"EMA9": 101.0, "EMA21": 100.0, "volume": 150.0, "Vol_SMA5": 100.0, "RSI7": 45.0},  # prev2 (>=)
        {"EMA9": 100.5, "EMA21": 100.0, "volume": 160.0, "Vol_SMA5": 100.0, "RSI7": 45.0},  # prev1 (>=)
        {"EMA9": 99.0,  "EMA21": 100.0, "volume": 200.0, "Vol_SMA5": 150.0, "RSI7": 45.0},  # last  (<)
    ])
    out = generate_signal(m15, m5)
    assert out["mom"] == "down"
    assert out["cross"] == -1
    assert bool(out["vol_ok"])
    assert bool(out["short"])
    assert not bool(out["long"])


def test_generate_signal_neutral_no_cross_volume_bad():
    m15 = df_m15(ema21=100.0, ema50=100.0)  # neutral
    m5 = df_m5([
        {"EMA9": 99.0,  "EMA21": 100.0, "volume": 80.0, "Vol_SMA5": 100.0, "RSI7": 40.0},  # prev2 below
        {"EMA9": 99.5,  "EMA21": 100.0, "volume": 90.0, "Vol_SMA5": 100.0, "RSI7": 40.0},  # prev1 below
        {"EMA9": 99.8,  "EMA21": 100.0, "volume": 90.0, "Vol_SMA5": 100.0, "RSI7": 40.0},  # last  still below
    ])
    out = generate_signal(m15, m5)
    assert out["mom"] == "neutral"
    assert out["cross"] == 0
    assert not bool(out["vol_ok"])
    assert not bool(out["long"])
    assert not bool(out["short"])
    assert out["rsi"] == 40.0


def test_generate_signal_prev2_based_cross_detection():
    """
    Cas où prev1 est déjà > (ou <) donc pas de croisement entre prev1 et last,
    mais prev2 avait l'autre signe : la logique doit quand même détecter le cross.
    """
    m15 = df_m15(ema21=101.0, ema50=100.0)  # momentum up
    m5 = df_m5([
        {"EMA9": 99.0,  "EMA21": 100.0, "volume": 120.0, "Vol_SMA5": 100.0, "RSI7": 60.0},  # prev2 (<=)
        {"EMA9": 101.0, "EMA21": 100.0, "volume": 130.0, "Vol_SMA5": 100.0, "RSI7": 60.0},  # prev1 (>) déjà au-dessus
        {"EMA9": 102.0, "EMA21": 100.0, "volume": 180.0, "Vol_SMA5": 150.0, "RSI7": 60.0},  # last  (>)
    ])
    out = generate_signal(m15, m5)
    assert out["cross"] == 1
    assert bool(out["long"])  # momentum up + cross haussier + RSI ok


def test_generate_signal_requires_three_rows_m5():
    m15 = df_m15(ema21=101.0, ema50=100.0)
    m5_too_short = df_m5([
        {"EMA9": 99.0, "EMA21": 100.0, "volume": 100.0, "Vol_SMA5": 100.0, "RSI7": 50.0},
        {"EMA9": 101.0, "EMA21": 100.0, "volume": 100.0, "Vol_SMA5": 100.0, "RSI7": 50.0},
    ])
    with pytest.raises(IndexError):
        generate_signal(m15, m5_too_short)
