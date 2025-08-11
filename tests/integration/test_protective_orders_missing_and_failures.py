# path: tests/integration/test_protective_orders_missing_and_failures.py
from execution.position_manager import PositionManager


def test_missing_protective_orders_triggers_exit(dummy_exchange, order_manager, monkeypatch):
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    pm.open_position("buy", entry_price=100.0, size=1.0)
    assert pm.active is not None

    # Simule perte des ordres SL/TP alors que la position reste ouverte
    monkeypatch.setattr(dummy_exchange, "fetch_open_orders", lambda symbol=None: [])
    pm.check_exit()
    assert pm.active is None


def test_open_position_fails_to_place_sl_tp_rolls_back(dummy_exchange, order_manager, monkeypatch):
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)

    # Force un échec lors du placement du SL (après MKT et TP potentiellement)
    def boom(*a, **k):
        raise RuntimeError("cannot place stop")
    monkeypatch.setattr(pm.om, "place_stop_limit_order", boom)

    try:
        pm.open_position("buy", entry_price=100.0, size=1.0)
    except RuntimeError:
        pass
    # Après rollback d'urgence, aucune position active
    assert pm.active is None
