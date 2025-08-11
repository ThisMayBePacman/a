# path: tests/integration/test_trade_flow.py
import pandas as pd
import pytest
from execution.position_manager import PositionManager

def dummy_calc(exchange, symbol, entry_price, side):
    # Simple SL/TP: 5% away from entry in each direction
    if side == 'buy':
        sl = entry_price * 0.95
        tp = entry_price * 1.05
    else:
        sl = entry_price * 1.05
        tp = entry_price * 0.95
    return { 'sl_price': sl, 'tp_price': tp, 'trail_dist': abs(entry_price - sl) }

def test_trade_flow_take_profit(monkeypatch, dummy_exchange, order_manager):
    # Patch calc_initial_sl_tp for determinism
    monkeypatch.setattr('execution.position_manager.calculate_initial_sl_tp', dummy_calc)
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    # 1. Open a long position
    entry_price = 100.0
    size = 1.0
    pm.open_position('buy', entry_price=entry_price, size=size)
    assert pm.active is not None
    initial_sl = pm.active['current_sl_price']
    initial_tp = pm.active['tp_price']
    # Verify initial SL and TP around 95 and 105
    assert pytest.approx(initial_sl, rel=1e-3) == 95.0
    assert pytest.approx(initial_tp, rel=1e-3) == 105.0
    # 2. Price rises gradually -> trailing stop updates
    # Price to 101 -> SL devrait remonter
    df = pd.DataFrame({'close': [101.0]})
    pm.update_trail(df)
    sl_after1 = pm.active['current_sl_price']
    assert sl_after1 > initial_sl
    # Price to 104 -> SL moves up again
    df['close'] = [104.0]
    pm.update_trail(df)
    sl_after2 = pm.active['current_sl_price']
    assert sl_after2 > sl_after1
    # 3. Price hits/exceeds TP -> simulate TP fill and position close
    dummy_exchange.positions["BTC/USDT"] = (0.0, dummy_exchange.positions["BTC/USDT"][1])
    ids = pm.active['ids']
    dummy_exchange.orders[ids['tp']]['status'] = 'closed'
    dummy_exchange.orders[ids['sl']]['status'] = 'canceled'
    pm.check_exit()
    # Position should be fully closed
    assert pm.active is None
    # Ensure DummyExchange reflects closed position and no open orders
    open_orders = dummy_exchange.fetch_open_orders(symbol="BTC/USDT")
    assert open_orders == []
    pos_list = dummy_exchange.fetch_positions(["BTC/USDT"])
    assert pos_list == []

def test_trade_flow_stop_loss(monkeypatch, dummy_exchange, order_manager):
    monkeypatch.setattr('execution.position_manager.calculate_initial_sl_tp', dummy_calc)
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    # Open a short position
    pm.open_position('sell', entry_price=100.0, size=1.0)
    assert pm.active is not None
    initial_sl = pm.active['current_sl_price']
    # SL should be above entry for short (around 105)
    assert pytest.approx(initial_sl, rel=1e-3) == 105.0
    # Price falls -> trailing stop lowers
    df = pd.DataFrame({'close': [97.0]})
    pm.update_trail(df)
    sl_after = pm.active['current_sl_price']
    assert sl_after < initial_sl
    # Price rises above SL -> triggers emergency exit via watchdog
    pm.watchdog(106.0)
    # Position should be closed by emergency exit
    assert pm.active is None
    # DummyExchange position closed and no open orders remain
    pos_list = dummy_exchange.fetch_positions(["BTC/USDT"])
    assert pos_list == []
    open_orders = dummy_exchange.fetch_open_orders(symbol="BTC/USDT")
    assert open_orders == []
