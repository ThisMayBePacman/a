# path: tests/integration/test_tp_breach_flow.py
import logging
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

def test_tp_breach_only_logs_and_keeps_position(dummy_exchange, order_manager, monkeypatch, caplog):
    _patch_sl_tp(monkeypatch)
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    pm.open_position("buy", entry_price=100.0, size=1.0)
    assert pm.active is not None

    pm.active["tp_price"] = pm.active["entry_price"] * 1.001

    caplog.set_level(logging.INFO)
    pm.watchdog(pm.active["tp_price"] * 1.01)
    assert pm.active is not None
    assert any("TP level breached." in rec.message for rec in caplog.records)
