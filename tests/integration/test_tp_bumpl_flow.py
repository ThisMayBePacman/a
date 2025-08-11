import pandas as pd
import pytest
from execution.position_manager import PositionManager, TICK_SIZE
from risk.strategies.registry import make_strategy
from utils.price_utils import align_price

def _dummy_calc_long(exchange, symbol, entry_price, side):
    # entry=100 → sl=95, tp0=120, trail=5
    assert side == "buy"
    return {"sl_price": 95.0, "tp_price": 120.0, "trail_dist": 5.0}

def test_long_tp_bump_when_threshold_crossed(monkeypatch, dummy_exchange, order_manager):
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    # Déterminisme à l’ouverture
    monkeypatch.setattr("execution.position_manager.calculate_initial_sl_tp", _dummy_calc_long)
    # Stratégie SL+TP
    pm.strategy = make_strategy("trailing_sl_and_tp", theta=0.5, rho=1.0)

    pm.open_position("buy", entry_price=100.0, size=1.0)
    assert pm.active is not None

    old_tp_id = pm.active["ids"]["tp"]
    old_tp = pm.active["tp_price"]
    old_sl = pm.active["current_sl_price"]

    # Prix 116, dist=5 => sl_cand≈111 >= threshold(110) → bump ≈ +1.0
    pm.update_trail(pd.DataFrame({"close": [116.0]}))

    # SL monotone
    assert pm.active["current_sl_price"] >= old_sl

    # TP bumpé (aligné tick)
    expected = align_price(old_tp + 1.0, TICK_SIZE, mode="up")
    assert pytest.approx(pm.active["tp_price"], rel=1e-9) == expected

    # Cancel+replace TP
    assert pm.active["ids"]["tp"] != old_tp_id

def test_long_tp_bump_can_repeat(monkeypatch, dummy_exchange, order_manager):
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    monkeypatch.setattr("execution.position_manager.calculate_initial_sl_tp", _dummy_calc_long)
    pm.strategy = make_strategy("trailing_sl_and_tp", theta=0.5, rho=1.0)

    pm.open_position("buy", entry_price=100.0, size=1.0)

    # 1er bump à 116
    pm.update_trail(pd.DataFrame({"close": [116.0]}))
    tp1 = pm.active["tp_price"]
    tp1_id = pm.active["ids"]["tp"]

    # 2e bump à 118 (sl_cand≈113 → bump cumulé attendu)
    pm.update_trail(pd.DataFrame({"close": [118.0]}))
    assert pm.active["tp_price"] > tp1
    assert pm.active["ids"]["tp"] != tp1_id
