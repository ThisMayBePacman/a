# path: tests/integration/test_purge_reduce_only_and_reentrance.py
from typing import Any, Dict

from execution.position_manager import PositionManager


def _patch_sl_tp(monkeypatch):
    def dummy_calc(exchange, symbol, entry_price, side):
        trail = 1.0
        if side == "buy":
            return {"sl_price": entry_price - trail, "tp_price": entry_price + 2 * trail, "trail_dist": trail}
        return {"sl_price": entry_price + trail, "tp_price": entry_price - 2 * trail, "trail_dist": trail}

    # ⚠️ Patch BOTH places
    monkeypatch.setattr("risk.sl_tp.calculate_initial_sl_tp", dummy_calc, raising=False)
    monkeypatch.setattr("execution.position_manager.calculate_initial_sl_tp", dummy_calc, raising=False)

def test_purge_reduce_only_cancels_only_exit_side(dummy_exchange, order_manager):
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    # Crée des ordres SELL reduceOnly + un BUY non-reduce
    o1 = dummy_exchange.create_order("BTC/USDT", "limit", "sell", 1.0, 120.0, {"reduceOnly": True})
    o2 = dummy_exchange.create_order("BTC/USDT", "limit", "sell", 1.0, 121.0, {"reduceOnly": True})
    _ = dummy_exchange.create_order("BTC/USDT", "limit", "buy", 1.0, 80.0, {})  # non-reduce
    pm._purge_stale_reduce_only("sell")
    assert o1["id"] in dummy_exchange.cancelled
    assert o2["id"] in dummy_exchange.cancelled


def test_emergency_exit_not_reentrant(dummy_exchange, order_manager, monkeypatch):
    _patch_sl_tp(monkeypatch)
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    pm.open_position("buy", entry_price=100.0, size=1.0)

    called = {"n": 0}
    orig_place_market = pm.om.place_market_order  # sauvegarde l’original

    def spy(side, qty, params=None):
        called["n"] += 1
        return orig_place_market(side, qty, params=params)  # appelle l’original, pas order_manager.place_market_order

    monkeypatch.setattr(pm.om, "place_market_order", spy)


    pm._emergency_exit("test1")
    pm._emergency_exit("test2")
    assert called["n"] == 1
    assert pm.active is None
