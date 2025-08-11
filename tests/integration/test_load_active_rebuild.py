# path: tests/integration/test_load_active_rebuild.py
from execution.position_manager import PositionManager


def test_load_active_rebuilds_state_from_exchange(dummy_exchange, order_manager):
    # Ouvre une position pour remplir l'état côté exchange (positions + ordres SL/TP)
    pm1 = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    pm1.open_position("buy", entry_price=100.0, size=1.0)
    assert pm1.active is not None
    # Nouveau PM sans état, puis reconstruction
    pm2 = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    assert pm2.active is None
    pm2.load_active()
    assert pm2.active is not None
    assert pm2.active["size"] > 0
    assert {"sl", "tp"}.issubset(set(pm2.active["ids"].keys()))
