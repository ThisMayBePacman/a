# path: tests/integration/test_protective_orders_missing_and_failures.py
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
    
def test_missing_protective_orders_triggers_exit(dummy_exchange, order_manager, monkeypatch):
    _patch_sl_tp(monkeypatch)
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    pm.open_position("buy", entry_price=100.0, size=1.0)
    assert pm.active is not None

    # Simule perte des ordres SL/TP alors que la position reste ouverte
    monkeypatch.setattr(dummy_exchange, "fetch_open_orders", lambda symbol=None: [])
    pm.check_exit()
    assert pm.active is None


def test_open_position_fails_to_place_sl_tp_rolls_back(dummy_exchange, order_manager, monkeypatch):
    _patch_sl_tp(monkeypatch)
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)

    # Force un échec lors du placement du SL
    def boom(*a, **k):
        raise RuntimeError("cannot place stop")

    monkeypatch.setattr(pm.om, "place_stop_limit_order", boom)

    try:
        pm.open_position("buy", entry_price=100.0, size=1.0)
    except RuntimeError:
        pass
    assert pm.active is None
