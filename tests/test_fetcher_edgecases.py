# path: tests/test_fetcher_edgecases.py
from data.fetcher import fetch_ohlcv

# Fakes CCXT déterministes
def _parse_timeframe(tf: str) -> int:
    if tf.endswith("m"):
        return int(tf[:-1]) * 60
    if tf.endswith("h"):
        return int(tf[:-1]) * 60 * 60
    if tf.endswith("d"):
        return int(tf[:-1]) * 24 * 60 * 60
    raise ValueError(tf)

class FXSpy:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, int | None, int | None]] = []

    def milliseconds(self) -> int:
        return 1_700_000_000_000

    def parse_timeframe(self, timeframe: str) -> int:
        return _parse_timeframe(timeframe)

    def fetch_ohlcv(self, symbol: str, timeframe: str, since=None, limit: int | None = None):
        self.calls.append((symbol, timeframe, since, limit))
        return [[self.milliseconds(), 1.0, 2.0, 0.5, 1.5, 10.0] for _ in range(int(limit or 0))]

class FXBadTF(FXSpy):
    def parse_timeframe(self, timeframe: str) -> int:
        # Simule un timeframe invalide
        raise ValueError("unsupported timeframe")


def test_fetch_ohlcv_invalid_timeframe_raises():
    fx = FXBadTF()
    import pytest
    with pytest.raises(Exception):
        fetch_ohlcv(fx, "BTC/USDT", "7x", lookback=3)


def test_fetch_ohlcv_lookback_zero_passes_since_and_limit():
    fx = FXSpy()
    df = fetch_ohlcv(fx, "ETH/USDT", "1h", lookback=0)
    # Un appel effectué
    assert len(fx.calls) == 1
    symbol, tf, since, limit = fx.calls[0]
    assert symbol == "ETH/USDT" and tf == "1h"
    # since = now - 0 => now
    assert since == fx.milliseconds()
    # La plupart des implémentations passent limit=0 dans ce cas; on accepte 0
    assert limit == 0
    # Et donc aucun point renvoyé
    assert df.empty
