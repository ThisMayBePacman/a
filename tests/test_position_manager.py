# path: tests/test_position_manager.py
import pandas as pd
import pytest
import ccxt
from execution.position_manager import PositionManager
from utils.price_utils import align_price
from config import TICK_SIZE
from risk.rules import RULES


def test_open_position_success(monkeypatch, dummy_exchange, order_manager):
    # Monkeypatch calculate_initial_sl_tp to avoid external data fetch
    def dummy_calc(exchange, symbol, entry_price, side):
        # Return SL at 90% of entry, TP at 110% of entry
        sl = entry_price * 0.9
        tp = entry_price * 1.1
        return {"sl_price": sl, "tp_price": tp, "trail_dist": abs(entry_price - sl)}

    monkeypatch.setattr("execution.position_manager.calculate_initial_sl_tp", dummy_calc)
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    pm.open_position("buy", entry_price=100.0, size=1.0)
    # Active position is set
    assert pm.active is not None
    assert pm.active["side"] == "buy"
    assert pytest.approx(pm.active["size"], rel=1e-3) == 1.0
    assert pytest.approx(pm.active["entry_price"], rel=1e-3) == 100.0
    # SL/TP should be around 90 and 110 given dummy_calc (with tick alignment)
    assert pm.active["current_sl_price"] < pm.active["entry_price"]
    assert pm.active["tp_price"] > pm.active["entry_price"]
    # Check orders placed via DummyExchange
    ids = pm.active["ids"]
    # Market order id recorded
    assert ids["mkt"] in dummy_exchange.orders
    # TP and SL orders recorded and open
    tp_order = dummy_exchange.orders[ids["tp"]]
    sl_order = dummy_exchange.orders[ids["sl"]]
    assert tp_order["type"] == "limit" and tp_order["status"] == "open"
    assert sl_order["params"].get("stopPrice") is not None and sl_order["status"] == "open"
    # DummyExchange position updated
    pos_size, entry_price = dummy_exchange.positions.get("BTC/USDT", (0, None))
    assert pytest.approx(pos_size, rel=1e-3) == 1.0
    assert entry_price is not None


def test_open_position_invalid(monkeypatch, dummy_exchange, order_manager):
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    # Invalid side
    with pytest.raises(ValueError):
        pm.open_position("invalid", entry_price=100.0, size=1.0)
    # Invalid size
    with pytest.raises(ValueError):
        pm.open_position("buy", entry_price=100.0, size=0.0)


def test_update_trail_no_change(monkeypatch, dummy_exchange, order_manager):
    # Setup position with known SL via dummy calc
    def dummy_calc(exchange, symbol, entry_price, side):
        return {"sl_price": entry_price * 0.9, "tp_price": entry_price * 1.1, "trail_dist": entry_price * 0.1}

    monkeypatch.setattr("execution.position_manager.calculate_initial_sl_tp", dummy_calc)
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    pm.open_position("buy", entry_price=100.0, size=1.0)
    old_sl = pm.active["current_sl_price"]
    old_sl_id = pm.active["ids"]["sl"]
    # Price increases but not enough to move SL (less than one tick above threshold)
    df = pd.DataFrame({"close": [old_sl + 0.2]})
    pm.update_trail(df)
    # SL should remain unchanged
    assert pm.active["current_sl_price"] == old_sl
    assert pm.active["ids"]["sl"] == old_sl_id
    # No cancellation happened (old SL still open)
    assert old_sl_id not in dummy_exchange.cancelled


def test_update_trail_updates_sl(monkeypatch, dummy_exchange, order_manager):
    # Setup position
    def dummy_calc(exchange, symbol, entry_price, side):
        return {"sl_price": entry_price * 0.9, "tp_price": entry_price * 1.1, "trail_dist": entry_price * 0.1}

    monkeypatch.setattr("execution.position_manager.calculate_initial_sl_tp", dummy_calc)
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    pm.open_position("buy", entry_price=100.0, size=1.0)
    old_sl = pm.active["current_sl_price"]
    old_sl_id = pm.active["ids"]["sl"]
    trail = pm.active["trail_dist"]
    # Set price high enough so that (price - trail) > old_sl, accounting for tick alignment
    new_price = old_sl + trail + TICK_SIZE
    df = pd.DataFrame({"close": [new_price]})
    pm.update_trail(df)
    # SL price should have increased
    assert pm.active["current_sl_price"] > old_sl
    # SL order id should have changed
    new_sl_id = pm.active["ids"]["sl"]
    assert new_sl_id != old_sl_id
    # Old SL should be canceled in DummyExchange
    assert old_sl_id in dummy_exchange.cancelled
    # New SL open with aligned expected price
    new_order = dummy_exchange.orders[new_sl_id]
    assert new_order["status"] == "open"
    expected_new_sl = align_price(new_price - trail, TICK_SIZE, mode="down")
    assert new_order["price"] == expected_new_sl


def test_update_trail_handles_ccxt_error(monkeypatch, dummy_exchange, order_manager):
    # Setup position
    def dummy_calc(exchange, symbol, entry_price, side):
        return {"sl_price": 90.0, "tp_price": 110.0, "trail_dist": 10.0}

    monkeypatch.setattr("execution.position_manager.calculate_initial_sl_tp", dummy_calc)
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    pm.open_position("buy", entry_price=100.0, size=1.0)
    # Force cancel_order to raise a ccxt.BaseError to exercise error branch
    monkeypatch.setattr(pm.exchange, "cancel_order", lambda *a, **k: (_ for _ in ()).throw(ccxt.BaseError("boom")))
    # Track emergency exit calls
    flag = {"called": False}

    def dummy_exit(self, reason):
        flag["called"] = True

    monkeypatch.setattr(PositionManager, "_emergency_exit", dummy_exit)
    # Price high enough to trigger trail update path
    df = pd.DataFrame({"close": [121.0]})
    pm.update_trail(df)
    assert flag["called"] is True


def test_check_exit_position_closed(monkeypatch, dummy_exchange, order_manager):
    # Use dummy calc for deterministic SL/TP
    monkeypatch.setattr(
        "execution.position_manager.calculate_initial_sl_tp",
        lambda *args, **kwargs: {"sl_price": 90.0, "tp_price": 110.0, "trail_dist": 10.0},
    )
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    pm.open_position("buy", entry_price=100.0, size=1.0)
    ids = pm.active["ids"]
    # Simulate TP hit: position closed and orders removed from order book
    dummy_exchange.positions["BTC/USDT"] = (0.0, dummy_exchange.positions["BTC/USDT"][1])
    dummy_exchange.orders[ids["tp"]]["status"] = "closed"
    dummy_exchange.orders[ids["sl"]]["status"] = "canceled"
    pm.check_exit()
    # Active position should be cleared
    assert pm.active is None


def test_check_exit_unprotected(monkeypatch, dummy_exchange, order_manager):
    monkeypatch.setattr(
        "execution.position_manager.calculate_initial_sl_tp",
        lambda *args, **kwargs: {"sl_price": 90.0, "tp_price": 110.0, "trail_dist": 10.0},
    )
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    pm.open_position("buy", entry_price=100.0, size=1.0)
    ids = pm.active["ids"]
    # Simulate manual cancellation of both SL and TP orders while position still open
    dummy_exchange.cancel_order(ids["sl"])
    dummy_exchange.cancel_order(ids["tp"])
    # Position still open in dummy (contracts != 0)
    contracts, _ = dummy_exchange.positions.get("BTC/USDT", (0.0, None))
    assert contracts != 0.0
    pm.check_exit()
    # Emergency exit should have closed the position
    assert pm.active is None
    # DummyExchange position now closed
    contracts, _ = dummy_exchange.positions.get("BTC/USDT", (0.0, None))
    assert contracts == 0.0


def test_check_exit_fetch_errors(monkeypatch, dummy_exchange, order_manager):
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    # When no active, check_exit returns early
    pm.check_exit()
    # Set active state
    pm.active = {"side": "buy", "size": 1.0, "ids": {"sl": "1", "tp": "2"}}
    # fetch_positions raises -> should just log and return without crashing
    monkeypatch.setattr(pm.exchange, "fetch_positions", lambda *a, **k: (_ for _ in ()).throw(Exception("oops")))
    pm.check_exit()
    # Now make fetch_positions OK but fetch_open_orders fails
    monkeypatch.setattr(pm.exchange, "fetch_positions", lambda *a, **k: [{"symbol": "BTC/USDT", "contracts": "1", "entryPrice": 100.0}])
    monkeypatch.setattr(pm.exchange, "fetch_open_orders", lambda *a, **k: (_ for _ in ()).throw(Exception("oops2")))
    pm.check_exit()


def test_load_active_recovers_state(monkeypatch, dummy_exchange, order_manager):
    # Prepare a position with SL/TP open orders
    monkeypatch.setattr(
        "execution.position_manager.calculate_initial_sl_tp",
        lambda *a, **k: {"sl_price": 90.0, "tp_price": 110.0, "trail_dist": 10.0},
    )
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    pm.open_position("buy", 100.0, 1.0)
    # Simulate restart: new PM with same exchange
    pm2 = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    pm2.load_active()
    assert pm2.active is not None
    assert pm2.active["side"] == "buy"
    assert pm2.active["ids"]["sl"]
    assert pm2.active["ids"]["tp"]


def test_load_active_fetch_errors(monkeypatch, dummy_exchange, order_manager):
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    # fetch_open_orders fails
    monkeypatch.setattr(pm.exchange, "fetch_open_orders", lambda *a, **k: (_ for _ in ()).throw(Exception("boom")))
    pm.load_active()
    assert pm.active is None
    # fetch_open_orders ok but positions fail
    monkeypatch.setattr(pm.exchange, "fetch_open_orders", lambda *a, **k: [{"id": "1", "symbol": "BTC/USDT", "price": 100.0, "info": {}, "status": "open"}])
    monkeypatch.setattr(pm.exchange, "fetch_positions", lambda *a, **k: (_ for _ in ()).throw(Exception("boom2")))
    pm.load_active()
    assert pm.active is None


def test_cancel_all_open_and_purge_stale(monkeypatch, dummy_exchange, order_manager):
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    # Create reduceOnly SELL orders and a non-reduce BUY order
    o1 = dummy_exchange.create_order("BTC/USDT", "limit", "sell", 1.0, 120.0, {"reduceOnly": True})
    o2 = dummy_exchange.create_order("BTC/USDT", "limit", "sell", 1.0, 121.0, {"reduceOnly": True})
    o3 = dummy_exchange.create_order("BTC/USDT", "limit", "buy", 1.0, 80.0, {})  # should not be touched
    pm._purge_stale_reduce_only("sell")
    assert o1["id"] in dummy_exchange.cancelled
    assert o2["id"] in dummy_exchange.cancelled
    assert o3["id"] not in dummy_exchange.cancelled
    # Now test _cancel_all_open cancels remaining open orders
    o4 = dummy_exchange.create_order("BTC/USDT", "limit", "buy", 1.0, 81.0, {})
    pm._cancel_all_open()
    assert o4["id"] in dummy_exchange.cancelled
    # fetch_open_orders error path
    monkeypatch.setattr(pm.exchange, "fetch_open_orders", lambda *a, **k: (_ for _ in ()).throw(Exception("err")))
    pm._cancel_all_open()  # should not raise


def test_emergency_exit_already_flat(dummy_exchange, order_manager):
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    # Create open orders but no position
    o1 = dummy_exchange.create_order("BTC/USDT", "limit", "sell", 1.0, 120.0, {"reduceOnly": True})
    pm.active = {"side": "buy", "size": 1.0, "ids": {"sl": o1["id"]}}
    pm._emergency_exit("flat")
    assert pm.active is None
    # All orders cancelled
    assert o1["id"] in dummy_exchange.cancelled


def test_emergency_exit_closes_position(monkeypatch, dummy_exchange, order_manager):
    # Open a long position to be closed by emergency exit
    monkeypatch.setattr(
        "execution.position_manager.calculate_initial_sl_tp",
        lambda *a, **k: {"sl_price": 90.0, "tp_price": 110.0, "trail_dist": 10.0},
    )
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    pm.open_position("buy", 100.0, 1.0)
    pm._emergency_exit("manual")
    assert pm.active is None
    # Position should be flat
    pos_list = dummy_exchange.fetch_positions(["BTC/USDT"])
    assert pos_list == []
    # No open orders remain
    assert dummy_exchange.fetch_open_orders("BTC/USDT") == []


def test_properties_when_no_active(dummy_exchange, order_manager):
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    assert pm.entry_price is None
    assert pm.tp_price is None


def test_watchdog_rule_error_is_caught(monkeypatch, dummy_exchange, order_manager):
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)

    def bad_action(state):
        raise RuntimeError("boom")

    monkeypatch.setitem(
        RULES,
        "failing_rule",
        {"condition": lambda s, p: True, "action": bad_action},
    )
    # Should not raise
    pm.watchdog(100.0)
    # Cleanup
    RULES.pop("failing_rule", None)
