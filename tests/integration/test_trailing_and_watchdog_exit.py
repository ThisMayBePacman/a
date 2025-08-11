# path: tests/integration/test_trailing_and_watchdog_exit.py
import pandas as pd

from execution.position_manager import PositionManager


def test_trailing_then_sl_breach_triggers_emergency_exit(dummy_exchange, order_manager, monkeypatch):
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    pm.open_position("buy", entry_price=100.0, size=1.0)
    assert pm.active is not None
    old_sl_id = pm.active["ids"]["sl"]
    old_sl = pm.active["current_sl_price"]

    # Prix monte -> amélioration du SL
    df = pd.DataFrame({"close": [old_sl + 10.0]})
    pm.update_trail(df)
    assert pm.active is not None
    assert pm.active["ids"]["sl"] != old_sl_id
    assert pm.active["current_sl_price"] > old_sl

    # Watchdog: breach du SL (prix <= SL) -> emergency exit et position fermée
    pm.watchdog(pm.active["current_sl_price"] - 0.01)  # breach
    assert pm.active is None


def test_update_trail_idempotent_same_price(dummy_exchange, order_manager):
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    pm.open_position("buy", entry_price=100.0, size=1.0)
    assert pm.active is not None
    sl_id = pm.active["ids"]["sl"]
    sl_price = pm.active["current_sl_price"]

    df_same = pd.DataFrame({"close": [pm.active["entry_price"]]})
    pm.update_trail(df_same)
    # même prix -> aucune mise à jour
    assert pm.active["ids"]["sl"] == sl_id
    assert pm.active["current_sl_price"] == sl_price
