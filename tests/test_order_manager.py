# path: tests/test_order_manager.py
import pytest
def test_place_market_order_params_leverage_not_overwritten(order_manager):
    # leverage fourni ET déjà présent dans params -> on ne doit PAS l’écraser
    order = order_manager.place_market_order(
        "buy", 0.1, leverage=5, params={"leverage": 3, "reduceOnly": True}
    )
    assert order["params"]["leverage"] == 3
    assert order["params"]["reduceOnly"] is True

def test_place_stop_limit_order_with_explicit_stop_arg(order_manager):
    # stop_price passé via l’argument (pas via params) -> doit être recopié dans params['stopPrice']
    order = order_manager.place_stop_limit_order(
        "sell", 1.0, price=95.0, stop_price=90.0
    )
    assert order["params"]["stopPrice"] == 90.0
    assert order["price"] == 95.0
    assert order["type"] == "limit"

def test_place_market_order_success(order_manager):
    order = order_manager.place_market_order("buy", 0.1)
    assert order["type"] == "market"
    assert order["side"] == "buy"
    assert order["amount"] == 0.1
    assert order["symbol"] == "BTC/USDT"


def test_place_market_order_with_leverage(order_manager):
    order = order_manager.place_market_order("sell", 0.2, leverage=3)
    assert order["params"]["leverage"] == 3


def test_place_market_order_invalid_side(order_manager):
    with pytest.raises(ValueError):
        order_manager.place_market_order("invalid", 1)


def test_place_market_order_invalid_size(order_manager):
    with pytest.raises(ValueError):
        order_manager.place_market_order("buy", 0)


def test_place_limit_order_success(order_manager):
    order = order_manager.place_limit_order("sell", 0.5, 30000)
    assert order["type"] == "limit"
    assert order["side"] == "sell"
    assert order["price"] == 30000


def test_place_limit_order_invalid_side(order_manager):
    with pytest.raises(ValueError):
        order_manager.place_limit_order("foo", 1, 10000)


def test_place_limit_order_invalid_size_or_price(order_manager):
    with pytest.raises(ValueError):
        order_manager.place_limit_order("buy", -1, 10000)
    with pytest.raises(ValueError):
        order_manager.place_limit_order("buy", 1, 0)


def test_place_stop_limit_order_success(order_manager):
    params = {"stopPrice": 29000}
    order = order_manager.place_stop_limit_order("buy", 0.3, 29500, params=params)
    assert order["type"] == "limit"
    assert order["params"]["stopPrice"] == 29000


def test_place_stop_limit_order_missing_stop_price(order_manager):
    with pytest.raises(ValueError):
        order_manager.place_stop_limit_order("buy", 0.3, 29500, params={})


def test_place_stop_limit_order_invalid(order_manager):
    with pytest.raises(ValueError):
        order_manager.place_stop_limit_order("buy", 0, 29500, params={"stopPrice": 29000})
    with pytest.raises(ValueError):
        order_manager.place_stop_limit_order("buy", 0.3, 0, params={"stopPrice": 29000})


def test_cancel_order_success(order_manager, dummy_exchange):
    order = order_manager.place_market_order("buy", 0.1)
    result = order_manager.cancel_order(order["id"])
    assert result["status"] == "canceled"
    assert order["id"] in dummy_exchange.cancelled


def test_cancel_order_invalid(order_manager):
    with pytest.raises(ValueError):
        order_manager.cancel_order("")
    with pytest.raises(Exception):
        order_manager.cancel_order("99999")


def test_verify_order_rejected_status(monkeypatch, order_manager):
    # Force exchange to return a rejected order
    monkeypatch.setattr(
        order_manager.exchange,
        "create_order",
        lambda *a, **k: {"id": "x", "status": "rejected", "symbol": "BTC/USDT", "type": "limit", "side": "buy"},
    )
    with pytest.raises(RuntimeError):
        order_manager.place_limit_order("buy", 1.0, 10.0)


def test_verify_order_missing_id(monkeypatch, order_manager):
    # Force exchange to return an invalid payload (no id)
    monkeypatch.setattr(
        order_manager.exchange,
        "create_order",
        lambda *a, **k: {"status": "open", "symbol": "BTC/USDT", "type": "limit", "side": "buy"},
    )
    with pytest.raises(RuntimeError):
        order_manager.place_limit_order("buy", 1.0, 10.0)
# path: tests/test_order_manager.py
# --- AJOUTS pour viser 100% order_manager.py ---

def test_place_stop_limit_order_invalid_side(order_manager):
    # Couvre la validation 'side' dans stop-limit
    import pytest
    with pytest.raises(ValueError):
        order_manager.place_stop_limit_order("foo", 1.0, price=95.0, stop_price=90.0)
