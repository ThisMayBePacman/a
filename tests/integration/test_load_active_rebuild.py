# path: tests/integration/test_load_active_rebuild.py
from typing import Any, Dict

from execution.position_manager import PositionManager


def test_load_active_rebuilds_state_from_exchange(dummy_exchange, order_manager, monkeypatch):
    def dummy_calc(exchange: Any, symbol: str, entry_price: float, side: str) -> Dict[str, float]:
        trail = 1.0
        if side == "buy":
            return {"sl_price": entry_price - trail, "tp_price": entry_price + 2 * trail, "trail_dist": trail}
        return {"sl_price": entry_price + trail, "tp_price": entry_price - 2 * trail, "trail_dist": trail}

    monkeypatch.setattr("risk.sl_tp.calculate_initial_sl_tp", dummy_calc, raising=False)
    monkeypatch.setattr("execution.position_manager.calculate_initial_sl_tp", dummy_calc, raising=False)  # <= AJOUTER
    # Ouvre une position pour peupler l’exchange (positions + ordres)
    pm1 = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    pm1.open_position("buy", entry_price=100.0, size=1.0)
    assert pm1.active is not None

    # Nouveau PM vierge puis reconstruction via load_active()
    pm2 = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    assert pm2.active is None
    pm2.load_active()
    assert pm2.active is not None
    assert pm2.active["size"] > 0
    assert {"sl", "tp"}.issubset(pm2.active["ids"])
