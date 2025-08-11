# path: tests/test_fetcher.py
import pandas as pd
import pytest

from data.fetcher import fetch_ohlcv


class FXOK:
    """Exchange simulé qui renvoie des chandelles OHLCV (désordonnées)."""
    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int):
        base = 1_700_000_000_000
        rows = []
        for i in range(limit):
            ts = base + (limit - 1 - i) * 60_000  # décroissant
            # Mélange de types pour vérifier la conversion (str/float/int)
            o = float(100 + i)
            h = o + 1
            l = o - 1
            c = str(o + 0.5)  # string - doit être cast en float
            v = 10 + i
            rows.append([ts, o, h, l, c, v])
        return rows


class FXEmpty:
    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int):
        return []


class FXError:
    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int):
        raise RuntimeError("rate limit")


class FXMalformed:
    """Renvoie une ligne malformée (pas 6 colonnes)."""
    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int):
        base = 1_700_000_000_000
        # Une ligne correcte + une incorrecte
        return [
            [base, 100.0, 101.0, 99.0, 100.5, 10.0],
            [base + 60_000, 101.0, 102.0, 100.0, 101.5],  # 5 colonnes -> malformée
        ]


class FXSpy:
    """Espionne les arguments passés à fetch_ohlcv."""
    def __init__(self):
        self.calls = []

    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int):
        self.calls.append((symbol, timeframe, limit))
        # renvoie un unique point valide
        return [[1_700_000_000_000, 1.0, 2.0, 0.5, 1.5, 10.0]]


def test_fetch_ohlcv_returns_dataframe_sorted_and_casts_types():
    df = fetch_ohlcv(FXOK(), "BTC/USDT", "1m", lookback=20)
    # Colonnes attendues et tri croissant par timestamp
    assert list(df.columns)[:6] == ["time", "open", "high", "low", "close", "volume"]
    assert df["time"].is_monotonic_increasing
    assert len(df) == 20
    # Types numériques
    assert pd.api.types.is_integer_dtype(df["time"])
    assert pd.api.types.is_float_dtype(df["close"])
    # Index reseté
    assert df.index[0] == 0


def test_fetch_ohlcv_empty_raises():
    with pytest.raises(Exception):
        fetch_ohlcv(FXEmpty(), "BTC/USDT", "1m", lookback=5)


def test_fetch_ohlcv_exchange_error_propagates():
    with pytest.raises(Exception):
        fetch_ohlcv(FXError(), "BTC/USDT", "1m", lookback=5)


def test_fetch_ohlcv_malformed_row_raises():
    # Une ligne mal formée doit déclencher une exception explicite
    with pytest.raises(Exception):
        fetch_ohlcv(FXMalformed(), "BTC/USDT", "1m", lookback=2)


def test_fetch_ohlcv_passes_timeframe_and_limit_to_exchange():
    spy = FXSpy()
    df = fetch_ohlcv(spy, "ETH/USDT", "5m", lookback=1)
    assert spy.calls[-1] == ("ETH/USDT", "5m", 1)
    # Et le DF retourné est valide
    assert len(df) == 1
    assert list(df.columns)[:6] == ["time", "open", "high", "low", "close", "volume"]
