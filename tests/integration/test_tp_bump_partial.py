import pandas as pd
import pytest
from execution.position_manager import PositionManager
from risk.strategies.registry import make_strategy

@pytest.mark.xfail(reason="Quantity-aware TP replace after partial fills not wired in PM state yet.")
def test_tp_bump_after_partial_fill(monkeypatch, dummy_exchange, order_manager):
    def calc(exchange, symbol, entry_price, side):
        return {"sl_price": 95.0, "tp_price": 120.0, "trail_dist": 5.0}

    monkeypatch.setattr("execution.position_manager.calculate_initial_sl_tp", calc)
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    pm.strategy = make_strategy("trailing_sl_and_tp", theta=0.5, rho=1.0)

    pm.open_position("buy", entry_price=100.0, size=1.0)
    # Simule un fill partiel sur le TP (ex: 0.4 restant)
    pm.active["qty_remaining"] = 0.4

    old_tp_id = pm.active["ids"]["tp"]
    # Déclenche un bump
    pm.update_trail(pd.DataFrame({"close": [118.0]}))
    assert pm.active["ids"]["tp"] != old_tp_id
