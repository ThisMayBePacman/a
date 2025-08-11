import pandas as pd
import pytest
from execution.position_manager import PositionManager, TICK_SIZE
from risk.strategies.registry import make_strategy
from utils.price_utils import align_price

def _dummy_calc_short(exchange, symbol, entry_price, side):
    # short: entry=100 → sl=110, tp0=80, dist=5
    assert side == "sell"
    return {"sl_price": 110.0, "tp_price": 80.0, "trail_dist": 5.0}

@pytest.mark.xfail(reason="Short mirror bump requires PM to use strategy logic for short trailing.")
def test_short_tp_bump_mirror(monkeypatch, dummy_exchange, order_manager):
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    monkeypatch.setattr("execution.position_manager.calculate_initial_sl_tp", _dummy_calc_short)
    pm.strategy = make_strategy("trailing_sl_and_tp", theta=0.5, rho=1.0)

    pm.open_position("sell", entry_price=100.0, size=1.0)
    old_tp_id = pm.active["ids"]["tp"]
    old_tp = pm.active["tp_price"]

    # prix=84, dist=5 → sl_cand ~ 79, threshold=90 → bump TP vers le bas de ≈11
    pm.update_trail(pd.DataFrame({"close": [84.0]}))
    expected = align_price(old_tp - 11.0, TICK_SIZE, mode="down")
    assert pytest.approx(pm.active["tp_price"], rel=1e-9) == expected
    assert pm.active["ids"]["tp"] != old_tp_id

def _dummy_calc_edge(exchange, symbol, entry_price, side):
    # long: entry=100, tp0=120, dist=5 ; à 114 → sl_cand aligne à 110 (seuil) → pas de bump
    return {"sl_price": 95.0, "tp_price": 120.0, "trail_dist": 5.0}

def test_no_bump_at_exact_threshold(monkeypatch, dummy_exchange, order_manager):
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    monkeypatch.setattr("execution.position_manager.calculate_initial_sl_tp", _dummy_calc_edge)
    pm.strategy = make_strategy("trailing_sl_and_tp", theta=0.5, rho=1.0)

    pm.open_position("buy", entry_price=100.0, size=1.0)
    old_tp_id = pm.active["ids"]["tp"]
    old_tp = pm.active["tp_price"]

    pm.update_trail(pd.DataFrame({"close": [114.0]}))
    assert pm.active["tp_price"] == old_tp
    assert pm.active["ids"]["tp"] == old_tp_id

def test_noop_does_not_cancel_orders(monkeypatch, dummy_exchange, order_manager):
    # Variation trop faible : aucun cancel inutile
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    monkeypatch.setattr(
        "execution.position_manager.calculate_initial_sl_tp",
        lambda *a, **k: {"sl_price": 90.0, "tp_price": 110.0, "trail_dist": 10.0},
    )
    pm.strategy = make_strategy("trailing_sl_and_tp", theta=0.5, rho=1.0)

    pm.open_position("buy", entry_price=100.0, size=1.0)
    old = pm.active.copy()

    pm.update_trail(pd.DataFrame({"close": [old["current_sl_price"] + 0.2]}))
    assert pm.active["current_sl_price"] == old["current_sl_price"]
    assert pm.active["ids"]["sl"] == old["ids"]["sl"]
    assert pm.active["tp_price"] == old["tp_price"]
    assert pm.active["ids"]["tp"] == old["ids"]["tp"]
