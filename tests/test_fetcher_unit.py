# path: tests/test_fetcher_unit.py
import types
import pytest

from data.fetcher import create_exchange, resolve_symbol


def test_create_exchange_builds_client(monkeypatch):
    """
    Vérifie que create_exchange instancie bien krakenfutures avec les bons
    paramètres et appelle load_markets().
    """
    created = {"cfg": None, "load_markets_called": False}

    class FakeKrakenFutures:
        def __init__(self, cfg):
            created["cfg"] = cfg
            # sera rempli par load_markets()
            self.markets = {}

        def load_markets(self):
            created["load_markets_called"] = True
            # un mini-catalogue
            self.markets = {
                "ETH/USD": {"id": "PF_ETHUSD"},
                "BTC/USDT": {"id": "PF_XBTUSDT"},
            }

    # Remplace ccxt.krakenfutures par notre fake
    fake_ccxt = types.SimpleNamespace(krakenfutures=FakeKrakenFutures)
    monkeypatch.setattr("data.fetcher.ccxt", fake_ccxt)

    ex = create_exchange()
    # le client est bien notre fake
    assert isinstance(ex, FakeKrakenFutures)
    # load_markets a été appelé
    assert created["load_markets_called"] is True
    # la config passée à ccxt contient enableRateLimit (peu importe les clés exactes)
    assert created["cfg"].get("enableRateLimit") is True


def test_resolve_symbol_found(monkeypatch):
    """resolve_symbol retrouve le symbole CCXT depuis l'id de marché."""
    class FakeEx:
        def __init__(self):
            self.markets = {
                "ETH/USD": {"id": "PF_ETHUSD"},
                "BTC/USDT": {"id": "PF_XBTUSDT"},
            }

    ex = FakeEx()
    sym = resolve_symbol(ex, "PF_ETHUSD")
    assert sym == "ETH/USD"


def test_resolve_symbol_not_found_raises():
    class FakeEx:
        def __init__(self):
            self.markets = {"ETH/USD": {"id": "PF_ETHUSD"}}

    with pytest.raises(ValueError):
        resolve_symbol(FakeEx(), "UNKNOWN_ID")
