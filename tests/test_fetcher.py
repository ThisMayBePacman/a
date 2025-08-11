# path: tests/test_fetcher.py
import pandas as pd
import pytest
import math
from data.fetcher import fetch_ohlcv


def _parse_timeframe(tf: str) -> int:
    # secondes par unité
    if tf.endswith("m"):
        return int(tf[:-1]) * 60
    if tf.endswith("h"):
        return int(tf[:-1]) * 60 * 60
    if tf.endswith("d"):
        return int(tf[:-1]) * 24 * 60 * 60
    raise ValueError(f"Unsupported timeframe: {tf}")


class FXBase:
    def milliseconds(self) -> int:
        return 1_700_000_000_000  # fixe/déterministe

    def parse_timeframe(self, timeframe: str) -> int:
        return _parse_timeframe(timeframe)


class FXOK(FXBase):
    """Exchange simulé qui renvoie des chandelles OHLCV (désordonnées)."""
    def fetch_ohlcv(self, symbol: str, timeframe: str, since=None, limit: int | None = None):
        limit = int(limit or 100)
        base = self.milliseconds()
        rows = []
        for i in range(limit):
            ts = base - (limit - 1 - i) * 60_000  # décroissant
            # Mélange de types pour vérifier la conversion (str/float/int)
            o = float(100 + i)
            h = o + 1
            l = o - 1
            c = str(o + 0.5)  # string - le fetcher peut ne pas caster
            v = 10 + i
            rows.append([ts, o, h, l, c, v])
        return rows


class FXEmpty(FXBase):
    def fetch_ohlcv(self, symbol: str, timeframe: str, since=None, limit: int | None = None):
        return []


class FXError(FXBase):
    def fetch_ohlcv(self, symbol: str, timeframe: str, since=None, limit: int | None = None):
        raise RuntimeError("rate limit")


class FXMalformed(FXBase):
    """Renvoie une ligne malformée (pas 6 colonnes)."""
    def fetch_ohlcv(self, symbol: str, timeframe: str, since=None, limit: int | None = None):
        base = self.milliseconds()
        # Une ligne correcte + une incomplète (manque volume)
        return [
            [base, 100.0, 101.0, 99.0, 100.5, 10.0],
            [base + 60_000, 101.0, 102.0, 100.0, 101.5],  # 5 colonnes -> sera complétée par NaN
        ]


class FXSpy(FXBase):
    """Espionne les arguments passés à fetch_ohlcv."""
    def __init__(self):
        self.calls = []

    def fetch_ohlcv(self, symbol: str, timeframe: str, since=None, limit: int | None = None):
        self.calls.append((symbol, timeframe, since, limit))
        # renvoie un unique point valide
        return [[self.milliseconds(), 1.0, 2.0, 0.5, 1.5, 10.0]]


def test_fetch_ohlcv_returns_dataframe_sorted_and_casts_types():
    df = fetch_ohlcv(FXOK(), "BTC/USDT", "1m", lookback=20)
    # Colonnes attendues et tri croissant par timestamp
    assert list(df.columns)[:6] == ["time", "open", "high", "low", "close", "volume"]
    assert df["time"].is_monotonic_increasing
    assert len(df) == 20
    # Types: time en datetime64[ns] (comportement actuel du fetcher)
    assert pd.api.types.is_datetime64_any_dtype(df["time"])
    # Colonnes OHLCV convertibles en numériques
    for col in ["open", "high", "low", "close", "volume"]:
        converted = pd.to_numeric(df[col], errors="coerce")
        assert converted.notna().all()
    # Index reseté
    assert df.index[0] == 0


def test_fetch_ohlcv_empty_returns_empty_dataframe():
    # Comportement actuel: pas d'exception, mais DF vide
    df = fetch_ohlcv(FXEmpty(), "BTC/USDT", "1m", lookback=5)
    assert isinstance(df, pd.DataFrame)
    assert df.empty


def test_fetch_ohlcv_exchange_error_propagates():
    with pytest.raises(Exception):
        fetch_ohlcv(FXError(), "BTC/USDT", "1m", lookback=5)


def test_fetch_ohlcv_malformed_rows_are_kept_with_nans():
    # Les lignes incomplètes sont gardées avec NaN sur les colonnes manquantes
    df = fetch_ohlcv(FXMalformed(), "BTC/USDT", "1m", lookback=2)
    assert len(df) == 2
    assert list(df.columns)[:6] == ["time", "open", "high", "low", "close", "volume"]
    # La deuxième ligne doit avoir au moins un NaN (ex: volume)
    assert df.iloc[1].isna().any()
    assert pd.api.types.is_datetime64_any_dtype(df["time"])


def test_fetch_ohlcv_passes_timeframe_and_limit_to_exchange():
    spy = FXSpy()
    df = fetch_ohlcv(spy, "ETH/USDT", "5m", lookback=1)
    symbol, timeframe, since, limit = spy.calls[-1]
    assert symbol == "ETH/USDT"
    assert timeframe == "5m"
    assert limit == 1
    assert since is not None
    # Et le DF retourné est valide
    assert len(df) == 1
    assert list(df.columns)[:6] == ["time", "open", "high", "low", "close", "volume"]
# Fakes CCXT pour introspecter 'since' et 'limit'
def _parse_timeframe(tf: str) -> int:
    if tf.endswith("m"):
        return int(tf[:-1]) * 60
    if tf.endswith("h"):
        return int(tf[:-1]) * 60 * 60
    if tf.endswith("d"):
        return int(tf[:-1]) * 24 * 60 * 60
    raise ValueError(tf)

class FXSpySince:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, int | None, int | None]] = []
    def milliseconds(self) -> int:
        # fixe pour test déterministe
        return 1_700_000_000_000
    def parse_timeframe(self, timeframe: str) -> int:
        return _parse_timeframe(timeframe)
    def fetch_ohlcv(self, symbol: str, timeframe: str, since=None, limit: int | None = None):
        self.calls.append((symbol, timeframe, since, limit))
        # renvoie exactement 'limit' lignes pour valider le passage du paramètre
        limit = int(limit or 0)
        base = self.milliseconds()
        rows = []
        for i in range(limit):
            ts = base + i * 60_000
            rows.append([ts, 1.0, 2.0, 0.5, 1.5, 10.0])
        return rows

def test_fetch_ohlcv_since_calculation_hours():
    fx = FXSpySince()
    df = fetch_ohlcv(fx, "BTC/USDT", "1h", lookback=3)
    symbol, tf, since, limit = fx.calls[-1]
    assert symbol == "BTC/USDT" and tf == "1h" and limit == 3
    # since = now - lookback * seconds(tf) * 1000
    expected = fx.milliseconds() - 3 * _parse_timeframe("1h") * 1000
    assert since == expected
    # 3 lignes retournées
    assert len(df) == 3

def test_fetch_ohlcv_since_calculation_days():
    fx = FXSpySince()
    df = fetch_ohlcv(fx, "ETH/USDT", "2d", lookback=2)
    symbol, tf, since, limit = fx.calls[-1]
    assert symbol == "ETH/USDT" and tf == "2d" and limit == 2
    expected = fx.milliseconds() - 2 * _parse_timeframe("2d") * 1000
    assert since == expected
    assert len(df) == 2