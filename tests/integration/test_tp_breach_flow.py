# path: tests/integration/test_tp_breach_flow.py
import logging

from execution.position_manager import PositionManager


def test_tp_breach_only_logs_and_keeps_position(dummy_exchange, order_manager, monkeypatch, caplog):
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    pm.open_position("buy", entry_price=100.0, size=1.0)
    assert pm.active is not None

    # Fixe un TP proche pour provoquer rapidement le breach côté TP
    pm.active["tp_price"] = pm.active["entry_price"] * 1.001

    caplog.set_level(logging.INFO)
    pm.watchdog(pm.active["tp_price"] * 1.01)
    # Le watchdog tp_breach ne ferme pas la position (log seulement)
    assert pm.active is not None
    assert any("TP level breached." in rec.message for rec in caplog.records)
