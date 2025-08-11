# path: tests/test_order_manager.py
import pytest

def test_place_market_order_success(order_manager):
    order = order_manager.place_market_order("buy", 0.1)
    assert order['type'] == 'market'
    assert order['side'] == 'buy'
    assert order['amount'] == 0.1
    assert order['symbol'] == "BTC/USDT"

def test_place_market_order_with_leverage(order_manager):
    order = order_manager.place_market_order("sell", 0.2, leverage=3)
    assert order['params']['leverage'] == 3

def test_place_market_order_invalid_side(order_manager):
    with pytest.raises(ValueError):
        order_manager.place_market_order("invalid", 1)

def test_place_market_order_invalid_size(order_manager):
    with pytest.raises(ValueError):
        order_manager.place_market_order("buy", 0)

def test_place_limit_order_success(order_manager):
    order = order_manager.place_limit_order("sell", 0.5, 30000)
    assert order['type'] == 'limit'
    assert order['side'] == 'sell'
    assert order['price'] == 30000

def test_place_limit_order_invalid_side(order_manager):
    with pytest.raises(ValueError):
        order_manager.place_limit_order("foo", 1, 10000)

def test_place_limit_order_invalid_size_or_price(order_manager):
    with pytest.raises(ValueError):
        order_manager.place_limit_order("buy", -1, 10000)
    with pytest.raises(ValueError):
        order_manager.place_limit_order("buy", 1, 0)

def test_place_stop_limit_order_success(order_manager):
    params = {'stopPrice': 29000}
    order = order_manager.place_stop_limit_order("buy", 0.3, 29500, params=params)
    assert order['type'] == 'limit'
    assert order['params']['stopPrice'] == 29000

def test_place_stop_limit_order_missing_stop_price(order_manager):
    with pytest.raises(ValueError):
        order_manager.place_stop_limit_order("buy", 0.3, 29500, params={})

def test_place_stop_limit_order_invalid(order_manager):
    with pytest.raises(ValueError):
        order_manager.place_stop_limit_order("buy", 0, 29500, params={'stopPrice': 29000})
    with pytest.raises(ValueError):
        order_manager.place_stop_limit_order("buy", 0.3, 0, params={'stopPrice': 29000})

def test_cancel_order_success(order_manager, dummy_exchange):
    order = order_manager.place_market_order("buy", 0.1)
    result = order_manager.cancel_order(order['id'])
    assert result['status'] == 'canceled'
    assert order['id'] in dummy_exchange.cancelled

def test_cancel_order_invalid(order_manager):
    with pytest.raises(ValueError):
        order_manager.cancel_order("")
    with pytest.raises(Exception):
        order_manager.cancel_order("99999")
