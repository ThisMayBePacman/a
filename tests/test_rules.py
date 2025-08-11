# path: tests/test_rules.py
import logging

from risk.rules import RULES
from execution.position_manager import PositionManager


def test_tp_breach_logs(monkeypatch, dummy_exchange, order_manager, caplog):
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    pm.active = {"side": "buy", "tp_price": 110.0}
    caplog.set_level(logging.INFO)
    pm.watchdog(115.0)
    # Le message vient du logger risk.rules
    assert any("TP level breached." in rec.message for rec in caplog.records)


def test_drawdown_triggers_handle(monkeypatch, dummy_exchange, order_manager):
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    pm.active = {"entry_price": 100.0}

    handled = {"flag": False}

    def dummy_drawdown(self):
        handled["flag"] = True

    # Condition de drawdown personnalisée: -2% ou plus
    monkeypatch.setitem(
        RULES,
        "drawdown",
        {
            "condition": lambda state, price: bool(state.active) and price <= state.active.get("entry_price", 0) * 0.98,  # type: ignore[call-arg]
            "action": dummy_drawdown,
        },
    )
    pm.watchdog(95.0)  # 5% de baisse
    assert handled["flag"] is True
