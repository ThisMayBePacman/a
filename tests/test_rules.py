# path: tests/test_rules.py
import logging
import pytest
from execution.position_manager import PositionManager
from risk.rules import RULES

def test_sl_breach_triggers_emergency_exit(monkeypatch, dummy_exchange, order_manager):
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    # Setup active state for a long position with SL at 100
    pm.active = {'side': 'buy', 'current_sl_price': 100.0}
    # Patch emergency_exit to track calls
    called = {'flag': False}
    def dummy_exit(self, reason):
        called['flag'] = True
    monkeypatch.setattr(PositionManager, '_emergency_exit', dummy_exit)
    # Price below SL triggers sl_breach
    pm.watchdog(90.0)
    assert called['flag'] is True

def test_tp_breach_logs(monkeypatch, dummy_exchange, order_manager, caplog):
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    # Setup active for a long position with TP at 110
    pm.active = {'side': 'buy', 'tp_price': 110.0}
    caplog.set_level(logging.INFO)
    # Price above TP triggers tp_breach (no emergency exit, just log)
    pm.watchdog(115.0)
    # Verify log contains TP breach message
    logs = [rec.message for rec in caplog.records if "TP breach" in rec.message]
    assert any("TP breach" in msg for msg in logs)

def test_max_drawdown_triggers_handle(monkeypatch, dummy_exchange, order_manager):
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    pm.active = {'entry_price': 100.0}
    # Patch _handle_drawdown to track calls
    handled = {'flag': False}
    def dummy_drawdown(self):
        handled['flag'] = True
    monkeypatch.setattr(PositionManager, '_handle_drawdown', dummy_drawdown)
    # price drop > 2% triggers drawdown
    drop_price = 95.0  # 5% drop from 100
    pm.watchdog(drop_price)
    assert handled['flag'] is True

def test_watchdog_no_rule_trigger(monkeypatch, dummy_exchange, order_manager):
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    # Long position avec entry et SL tels que current_price ne déclenche aucune règle
    pm.active = {'side': 'buy', 'entry_price': 100.0, 'current_sl_price': 90.0, 'tp_price': 110.0}
    # Patch emergency_exit and handle_drawdown to detect if called
    pm.exit_called = False
    pm.drawdown_called = False
    def dummy_exit(self, reason):
        self.exit_called = True
    def dummy_draw(self):
        self.drawdown_called = True
    monkeypatch.setattr(PositionManager, '_emergency_exit', dummy_exit)
    monkeypatch.setattr(PositionManager, '_handle_drawdown', dummy_draw)
    # Price 105 (above SL for buy, below TP, not a drawdown) -> no rule triggers
    pm.watchdog(105.0)
    assert pm.exit_called is False
    assert pm.drawdown_called is False
