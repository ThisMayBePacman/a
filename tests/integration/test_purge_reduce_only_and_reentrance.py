# path: tests/integration/test_purge_reduce_only_and_reentrance.py
from execution.position_manager import PositionManager


def test_purge_reduce_only_cancels_only_exit_side(dummy_exchange, order_manager):
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    # Crée des ordres SELL reduceOnly + un BUY non-reduce
    o1 = dummy_exchange.create_order("BTC/USDT", "limit", "sell", 1.0, 120.0, {"reduceOnly": True})
    o2 = dummy_exchange.create_order("BTC/USDT", "limit", "sell", 1.0, 121.0, {"reduceOnly": True})
    _ = dummy_exchange.create_order("BTC/USDT", "limit", "buy", 1.0, 80.0, {})  # non-reduce
    pm._purge_stale_reduce_only("sell")
    # Les ordres reduceOnly SELL doivent être annulés
    assert o1["id"] in dummy_exchange.cancelled
    assert o2["id"] in dummy_exchange.cancelled


def test_emergency_exit_not_reentrant(dummy_exchange, order_manager, monkeypatch):
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    pm.open_position("buy", entry_price=100.0, size=1.0)
    assert pm.active is not None

    called = {"n": 0}

    def spy(side, qty, params=None):
        called["n"] += 1
        # laisse passer vers l'exchange
        return order_manager.place_market_order(side, qty, params=params)

    # Spy sur l'ordre marché de clôture
    monkeypatch.setattr(pm.om, "place_market_order", spy)

    # Double appel (quasi simultané) — la RLock + flag 'closing' empêche la 2e exécution
    pm._emergency_exit("test1")
    pm._emergency_exit("test2")
    assert called["n"] == 1
    assert pm.active is None
