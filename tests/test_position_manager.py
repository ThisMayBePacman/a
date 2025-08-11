# path: tests/test_position_manager.py
import pandas as pd
import pytest
from execution.position_manager import PositionManager

def test_open_position_success(monkeypatch, dummy_exchange, order_manager):
    # Monkeypatch calculate_initial_sl_tp to avoid external data fetch
    def dummy_calc(exchange, symbol, entry_price, side):
        # Return SL at 90% of entry, TP at 110% of entry
        sl = entry_price * 0.9
        tp = entry_price * 1.1
        return { 'sl_price': sl, 'tp_price': tp, 'trail_dist': abs(entry_price - sl) }
    monkeypatch.setattr('execution.position_manager.calculate_initial_sl_tp', dummy_calc)
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    pm.open_position('buy', entry_price=100.0, size=1.0)
    # Active position is set
    assert pm.active is not None
    assert pm.active['side'] == 'buy'
    assert pytest.approx(pm.active['size'], rel=1e-3) == 1.0
    assert pytest.approx(pm.active['entry_price'], rel=1e-3) == 100.0
    # SL/TP should be around 90 and 110 given dummy_calc (with tick alignment) 
    assert pm.active['current_sl_price'] < pm.active['entry_price']
    assert pm.active['tp_price'] > pm.active['entry_price']
    # Check orders placed via DummyExchange
    ids = pm.active['ids']
    # Market order id recorded
    assert ids['mkt'] in dummy_exchange.orders
    # TP and SL orders recorded and open
    tp_order = dummy_exchange.orders[ids['tp']]
    sl_order = dummy_exchange.orders[ids['sl']]
    assert tp_order['type'] == 'limit' and tp_order['status'] == 'open'
    assert sl_order['params'].get('stopPrice') is not None and sl_order['status'] == 'open'
    # DummyExchange position updated
    pos_size, entry_price = dummy_exchange.positions.get("BTC/USDT", (0, None))
    assert pytest.approx(pos_size, rel=1e-3) == 1.0
    assert entry_price is not None

def test_open_position_invalid(monkeypatch, dummy_exchange, order_manager):
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    # Invalid side
    with pytest.raises(ValueError):
        pm.open_position('invalid', entry_price=100.0, size=1.0)
    # Invalid size
    with pytest.raises(ValueError):
        pm.open_position('buy', entry_price=100.0, size=0.0)

def test_update_trail_no_change(monkeypatch, dummy_exchange, order_manager):
    # Setup position with known SL via dummy calc
    def dummy_calc(exchange, symbol, entry_price, side):
        return { 'sl_price': entry_price * 0.9, 'tp_price': entry_price * 1.1, 'trail_dist': entry_price * 0.1 }
    monkeypatch.setattr('execution.position_manager.calculate_initial_sl_tp', dummy_calc)
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    pm.open_position('buy', entry_price=100.0, size=1.0)
    old_sl = pm.active['current_sl_price']
    old_sl_id = pm.active['ids']['sl']
    # Price increases but not enough to move SL (less than one tick above old_sl)
    df = pd.DataFrame({'close': [old_sl + 0.2]})
    pm.update_trail(df)
    # SL should remain unchanged
    assert pm.active['current_sl_price'] == old_sl
    assert pm.active['ids']['sl'] == old_sl_id
    # No cancellation happened (old SL still open)
    assert old_sl_id not in dummy_exchange.cancelled

def test_update_trail_updates_sl(monkeypatch, dummy_exchange, order_manager):
    # Setup position
    def dummy_calc(exchange, symbol, entry_price, side):
        return { 'sl_price': entry_price * 0.9, 'tp_price': entry_price * 1.1, 'trail_dist': entry_price * 0.1 }
    monkeypatch.setattr('execution.position_manager.calculate_initial_sl_tp', dummy_calc)
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    pm.open_position('buy', entry_price=100.0, size=1.0)
    old_sl = pm.active['current_sl_price']
    old_sl_id = pm.active['ids']['sl']
    # Simulate price high enough to trigger trailing SL update
    new_price = old_sl + 5.0  # significantly above old SL
    df = pd.DataFrame({'close': [new_price]})
    pm.update_trail(df)
    # SL price should have increased
    assert pm.active['current_sl_price'] > old_sl
    # SL order id should have changed
    new_sl_id = pm.active['ids']['sl']
    assert new_sl_id != old_sl_id
    # Old SL should be canceled in DummyExchange
    assert old_sl_id in dummy_exchange.cancelled
    # DummyExchange should have a new SL order open with updated price
    new_order = dummy_exchange.orders[new_sl_id]
    assert new_order['status'] == 'open'
    # New SL price aligns with expected new_sl (price - trail, rounded to tick)
    expected_new_sl = pytest.approx(new_price - (100.0 * 0.1), rel=1e-3)
    assert new_order['price'] == expected_new_sl

def test_check_exit_position_closed(monkeypatch, dummy_exchange, order_manager):
    # Use dummy calc for deterministic SL/TP
    monkeypatch.setattr('execution.position_manager.calculate_initial_sl_tp', lambda *args, **kwargs: { 'sl_price': 90.0, 'tp_price': 110.0, 'trail_dist': 10.0 })
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    pm.open_position('buy', entry_price=100.0, size=1.0)
    ids = pm.active['ids']
    # Simulate TP hit: position closed and orders removed from order book
    dummy_exchange.positions["BTC/USDT"] = (0.0, dummy_exchange.positions["BTC/USDT"][1])
    dummy_exchange.orders[ids['tp']]['status'] = 'closed'
    dummy_exchange.orders[ids['sl']]['status'] = 'canceled'
    pm.check_exit()
    # Active position should be cleared
    assert pm.active is None

def test_check_exit_unprotected(monkeypatch, dummy_exchange, order_manager):
    monkeypatch.setattr('execution.position_manager.calculate_initial_sl_tp', lambda *args, **kwargs: { 'sl_price': 90.0, 'tp_price': 110.0, 'trail_dist': 10.0 })
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    pm.open_position('buy', entry_price=100.0, size=1.0)
    ids = pm.active['ids']
    # Simulate manual cancellation of both SL and TP orders while position still open
    dummy_exchange.cancel_order(ids['sl'])
    dummy_exchange.cancel_order(ids['tp'])
    # Position still open in dummy (contracts != 0)
    contracts, _ = dummy_exchange.positions.get("BTC/USDT", (0.0, None))
    assert contracts != 0.0
    pm.check_exit()
    # Emergency exit should have closed the position
    assert pm.active is None
    # DummyExchange position now closed
    contracts, _ = dummy_exchange.positions.get("BTC/USDT", (0.0, None))
    assert contracts == 0.0
