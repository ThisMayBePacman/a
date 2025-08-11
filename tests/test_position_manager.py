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


def test_opposite_invalid_raises(dummy_exchange, order_manager):
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    with pytest.raises(ValueError):
        pm.opposite("hold")


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


def test_update_trail_short_side_updates(monkeypatch, dummy_exchange, order_manager):
    # Short: SL doit descendre si le prix baisse suffisamment (new_sl < old_sl)
    monkeypatch.setattr(
        "execution.position_manager.calculate_initial_sl_tp",
        lambda *a, **k: {"sl_price": 110.0, "tp_price": 95.0, "trail_dist": 10.0},
    )
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    pm.open_position("sell", entry_price=100.0, size=1.0)  # SL initial ~110
    old_sl = pm.active["current_sl_price"]
    df = pd.DataFrame({"close": [85.0]})  # price + trail = 95 => < old_sl
    pm.update_trail(df)
    assert pm.active["current_sl_price"] < old_sl


def test_update_trail_order_not_found_triggers_exit(monkeypatch, dummy_exchange, order_manager):
    monkeypatch.setattr(
        "execution.position_manager.calculate_initial_sl_tp",
        lambda *a, **k: {"sl_price": 90.0, "tp_price": 110.0, "trail_dist": 10.0},
    )
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    pm.open_position("buy", entry_price=100.0, size=1.0)
    # cancel_order -> OrderNotFound
    monkeypatch.setattr(pm.exchange, "cancel_order", lambda *a, **k: (_ for _ in ()).throw(ccxt.OrderNotFound("x")))
    called = {"flag": False}

    def dummy_exit(self, reason):
        called["flag"] = True

    monkeypatch.setattr(PositionManager, "_emergency_exit", dummy_exit)
    df = pd.DataFrame({"close": [121.0]})
    pm.update_trail(df)
    assert called["flag"] is True


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


def test_check_exit_one_protective_still_open(monkeypatch, dummy_exchange, order_manager):
    # Cas où UNE seule protection reste ouverte => pas d'emergency_exit
    monkeypatch.setattr(
        "execution.position_manager.calculate_initial_sl_tp",
        lambda *args, **kwargs: {"sl_price": 90.0, "tp_price": 110.0, "trail_dist": 10.0},
    )
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    pm.open_position("buy", entry_price=100.0, size=1.0)
    ids = pm.active["ids"]
    # Annule seulement le SL, laisse le TP ouvert
    dummy_exchange.cancel_order(ids["sl"])
    pm.check_exit()
    assert pm.active is not None  # pas d'emergency_exit car TP encore présent


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


def test_load_active_orders_but_no_contracts(monkeypatch, dummy_exchange, order_manager):
    # SL/TP ouverts mais position à 0 => doit conclure qu'il n'y a pas de position active
    monkeypatch.setattr(
        "execution.position_manager.calculate_initial_sl_tp",
        lambda *a, **k: {"sl_price": 90.0, "tp_price": 110.0, "trail_dist": 10.0},
    )
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    pm.open_position("buy", 100.0, 1.0)
    # Rendre la position flat tout en laissant les ordres ouverts
    ids = pm.active["ids"]
    dummy_exchange.positions["BTC/USDT"] = (0.0, dummy_exchange.positions["BTC/USDT"][1])
    # Recharge un nouveau PM et load_active
    pm2 = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    pm2.load_active()
    assert pm2.active is None
    # (les ordres existent encore mais load_active ne doit pas prétendre à une position active)
    assert ids["sl"] in dummy_exchange.orders and ids["tp"] in dummy_exchange.orders


def test_load_active_no_orders(monkeypatch, dummy_exchange, order_manager):
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    monkeypatch.setattr(pm.exchange, "fetch_open_orders", lambda *a, **k: [])
    pm.load_active()
    assert pm.active is None


def test_load_active_only_sl_orders(monkeypatch, dummy_exchange, order_manager):
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    # Un seul ordre stop => pas de TP => pas de position active récupérable
    monkeypatch.setattr(
        pm.exchange,
        "fetch_open_orders",
        lambda *a, **k: [{"id": "1", "symbol": "BTC/USDT", "status": "open", "type": "limit", "side": "sell", "price": 100.0, "info": {"stopPrice": 100.0}}],
    )
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


def test_cancel_all_open_handles_cancel_error(monkeypatch, dummy_exchange, order_manager):
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    o = dummy_exchange.create_order("BTC/USDT", "limit", "buy", 1.0, 81.0, {})
    def fail_cancel(order_id, symbol=None):
        raise Exception("cannot cancel")
    monkeypatch.setattr(pm.exchange, "cancel_order", fail_cancel)
    pm._cancel_all_open()  # should log and continue, not raise
    # Order remains open because cancel failed
    assert dummy_exchange.orders[o["id"]]["status"] == "open"


def test_emergency_exit_reentrance_guard(monkeypatch, dummy_exchange, order_manager):
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    # Crée un ordre ouvert pour vérifier qu'il n'est pas touché
    o = dummy_exchange.create_order("BTC/USDT", "limit", "sell", 1.0, 120.0, {"reduceOnly": True})
    pm.closing = True  # Simule une fermeture en cours
    pm._emergency_exit("reentry")
    # L'ordre ne doit pas avoir été annulé (early return)
    assert o["status"] == "open"
    # Nettoyage
    pm.closing = False


def test_emergency_exit_open_sl_tp_failure_path(monkeypatch, dummy_exchange, order_manager):
    # Force un échec lors du placement du TP pour tester la voie d'urgence
    def dummy_calc(exchange, symbol, entry_price, side):
        return {"sl_price": 90.0, "tp_price": 110.0, "trail_dist": 10.0}
    monkeypatch.setattr("execution.position_manager.calculate_initial_sl_tp", dummy_calc)

    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)

    # Monkeypatch place_limit_order pour échouer (TP), après le market exécuté
    def fail_tp(*a, **k):
        raise RuntimeError("tp failed")
    monkeypatch.setattr(pm.om, "place_limit_order", fail_tp)

    # On laisse place_stop_limit_order intact pour vérifier qu'il n'est pas atteint
    with pytest.raises(RuntimeError):
        pm.open_position("buy", entry_price=100.0, size=1.0)

    # La position doit être fermée en urgence (flat)
    pos_list = dummy_exchange.fetch_positions(["BTC/USDT"])
    assert pos_list == []
    assert pm.active is None


def test_position_contracts_error_returns_zero(monkeypatch, dummy_exchange, order_manager):
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    monkeypatch.setattr(pm.exchange, "fetch_positions", lambda *a, **k: (_ for _ in ()).throw(Exception("x")))
    assert pm._position_contracts() == 0.0


def test_properties_when_no_active(dummy_exchange, order_manager):
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    assert pm.entry_price is None
    assert pm.tp_price is None


def test_handle_drawdown_noop(dummy_exchange, order_manager):
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    # Should not raise; just logs a warning
    pm._handle_drawdown()


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
def test_load_active_fetch_open_orders_error(monkeypatch, dummy_exchange, order_manager):
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    # fetch_open_orders lève -> load_active doit gérer et laisser active=None
    monkeypatch.setattr(pm.exchange, "fetch_open_orders", lambda *a, **k: (_ for _ in ()).throw(Exception("boom")))
    pm.load_active()
    assert pm.active is None

def test_load_active_positions_error(monkeypatch, dummy_exchange, order_manager):
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    # Simule un SL (avec stopPrice) et un TP (sans stopPrice)
    sl_like = {"id": "1", "symbol": "BTC/USDT", "status": "open", "type": "limit", "side": "sell", "price": 99.0, "info": {"stopPrice": 99.0}}
    tp_like = {"id": "2", "symbol": "BTC/USDT", "status": "open", "type": "limit", "side": "sell", "price": 110.0, "info": {}}
    monkeypatch.setattr(pm.exchange, "fetch_open_orders", lambda *a, **k: [sl_like, tp_like])
    # fetch_positions lève -> load_active doit gérer et laisser active=None
    monkeypatch.setattr(pm.exchange, "fetch_positions", lambda *a, **k: (_ for _ in ()).throw(Exception("oops")))
    pm.load_active()
    assert pm.active is None

def test_purge_stale_reduce_only_fetch_error(monkeypatch, dummy_exchange, order_manager):
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    # fetch_open_orders lève -> la méthode doit logger et retourner sans exception
    monkeypatch.setattr(pm.exchange, "fetch_open_orders", lambda *a, **k: (_ for _ in ()).throw(Exception("err")))
    pm._purge_stale_reduce_only("sell")  # ne doit pas lever

def test_purge_stale_reduce_only_cancel_error(monkeypatch, dummy_exchange, order_manager):
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    # Ordre reduceOnly SELL
    o = dummy_exchange.create_order("BTC/USDT", "limit", "sell", 1.0, 120.0, {"reduceOnly": True})
    # cancel_order échoue -> on prend le chemin d'erreur (warning) sans lever
    monkeypatch.setattr(pm.exchange, "cancel_order", lambda *a, **k: (_ for _ in ()).throw(Exception("nope")))
    pm._purge_stale_reduce_only("sell")
    # L'ordre reste ouvert (échec d'annulation), mais surtout on a couvert la branche except
    assert dummy_exchange.orders[o["id"]]["status"] == "open"

    # path: tests/test_position_manager.py
# --- AJOUTS pour viser 100% position_manager.py ---

def test_update_trail_no_active_returns_early(dummy_exchange, order_manager):
    # Couvre le early-return 'if not self.active' dans update_trail
    import pandas as pd
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    df = pd.DataFrame({"close": [100.0]})
    # Ne doit pas lever, juste sortir tôt
    pm.update_trail(df)

def test_load_active_only_tp_orders(monkeypatch, dummy_exchange, order_manager):
    # Couvre la branche "pas de SL" => pas de position récupérable
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    tp_like = {"id": "1", "symbol": "BTC/USDT", "status": "open", "type": "limit", "side": "sell", "price": 110.0, "info": {}}
    monkeypatch.setattr(pm.exchange, "fetch_open_orders", lambda *a, **k: [tp_like])
    pm.load_active()
    assert pm.active is None

def test_check_exit_positions_empty_path(monkeypatch, dummy_exchange, order_manager):
    # Couvre explicitement: positions=[] -> cancel_all_open + active=None
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    pm.active = {"side": "buy", "size": 1.0, "ids": {"sl": "x", "tp": "y"}}
    monkeypatch.setattr(pm.exchange, "fetch_positions", lambda *a, **k: [])
    # fetch_open_orders ne doit pas être appelé dans cette branche, mais on le laisse safe
    monkeypatch.setattr(pm.exchange, "fetch_open_orders", lambda *a, **k: [])
    pm.check_exit()
    assert pm.active is None

def test_open_position_uses_fill_price_from_average(monkeypatch, dummy_exchange, order_manager):
    """Couvre la voie fill_price = order['average'] dans open_position."""
    from execution.position_manager import PositionManager
    monkeypatch.setattr(
        "execution.position_manager.calculate_initial_sl_tp",
        lambda *a, **k: {"sl_price": 90.0, "tp_price": 110.0, "trail_dist": 10.0},
    )
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)

    # Remplace uniquement l'ordre marché pour forcer average
    def fake_mkt(side, size, leverage=None, params=None):
        return {"id": "m1", "status": "closed", "average": 101.5, "price": None}
    monkeypatch.setattr(pm.om, "place_market_order", fake_mkt)

    pm.open_position("buy", entry_price=100.0, size=1.0)
    assert pm.active is not None
    assert pm.active["entry_price"] == 101.5  # couvre la branche average


def test_purge_stale_reduce_only_detects_info_flag(dummy_exchange, order_manager):
    """Couvre la détection reduceOnly via o['info']['reduceOnly'] dans _purge_stale_reduce_only."""
    from execution.position_manager import PositionManager
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)

    # Injecte un ordre 'open' avec le flag reduceOnly dans info
    dummy_exchange.orders["99"] = {
        "id": "99",
        "symbol": "BTC/USDT",
        "type": "limit",
        "side": "sell",
        "amount": 1.0,
        "price": 120.0,
        "params": {},            # pas de reduceOnly ici
        "info": {"reduceOnly": True},  # le flag est ici
        "status": "open",
    }

    pm._purge_stale_reduce_only("sell")
    assert "99" in dummy_exchange.cancelled

# path: tests/test_position_manager.py
# --- AJOUTS pour viser 100% sur execution/position_manager.py ---

def test_open_position_uses_fill_price_from_price(monkeypatch, dummy_exchange, order_manager):
    """Couvre la branche fill_price = order['price'] (sans 'average')."""
    from execution.position_manager import PositionManager
    # SL/TP déterministes
    monkeypatch.setattr(
        "execution.position_manager.calculate_initial_sl_tp",
        lambda *a, **k: {"sl_price": 90.0, "tp_price": 110.0, "trail_dist": 10.0},
    )
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)

    # ordre marché renvoie uniquement 'price' (pas 'average')
    def fake_mkt(side, size, leverage=None, params=None):
        return {"id": "m2", "status": "closed", "price": 102.25}
    monkeypatch.setattr(pm.om, "place_market_order", fake_mkt)

    pm.open_position("buy", entry_price=100.0, size=1.0)
    assert pm.active is not None
    assert pm.active["entry_price"] == 102.25  # branche `price` couverte


def test_purge_stale_reduce_only_info_and_finally(dummy_exchange, order_manager):
    """Couvre la voie reduceOnly via info + s'assure de la fin de routine (_finally de _emergency_exit déjà couvert)."""
    from execution.position_manager import PositionManager
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)

    # Injecte un ordre 'open' avec reduceOnly dans info (pas dans params)
    dummy_exchange.orders["100"] = {
        "id": "100",
        "symbol": "BTC/USDT",
        "type": "limit",
        "side": "sell",
        "amount": 1.0,
        "price": 120.0,
        "params": {},
        "info": {"reduceOnly": True},
        "status": "open",
    }

    pm._purge_stale_reduce_only("sell")
    assert "100" in dummy_exchange.cancelled
def test_open_position_uses_entry_price_fallback(monkeypatch, dummy_exchange, order_manager):
    """Couvre la branche fill_price = entry_price (ni 'average' ni 'price' dans l'ordre marché)."""
    from execution.position_manager import PositionManager
    monkeypatch.setattr(
        "execution.position_manager.calculate_initial_sl_tp",
        lambda *a, **k: {"sl_price": 90.0, "tp_price": 110.0, "trail_dist": 10.0},
    )
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)

    # Ordre marché minimal: pas de 'average', pas de 'price'
    def fake_mkt(side, size, leverage=None, params=None):
        return {"id": "m3", "status": "closed"}
    monkeypatch.setattr(pm.om, "place_market_order", fake_mkt)

    pm.open_position("buy", entry_price=100.0, size=1.0)
    assert pm.active is not None
    assert pm.active["entry_price"] == 100.0  # fallback sur entry_price couvert


def test_purge_stale_reduce_only_info_flag(dummy_exchange, order_manager):
    """Couvre la détection reduceOnly via o['info']['reduceOnly'] et l’annulation associée."""
    from execution.position_manager import PositionManager
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)

    # Ordre OPEN avec reduceOnly dans info (pas dans params)
    dummy_exchange.orders["200"] = {
        "id": "200",
        "symbol": "BTC/USDT",
        "type": "limit",
        "side": "sell",
        "amount": 1.0,
        "price": 120.0,
        "params": {},                 # pas de reduceOnly ici
        "info": {"reduceOnly": True}, # flag ici
        "status": "open",
    }

    pm._purge_stale_reduce_only("sell")
    assert "200" in dummy_exchange.cancelled