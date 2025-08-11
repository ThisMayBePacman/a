import pytest
from execution.order_manager import OrderManager

class DummyExchange:
    def __init__(self):
        self.last_args = None
        self.orders = {}
        self.cancelled = set()
        self.order_id = 0

    def create_order(self, symbol, type, side, amount, price=None, params=None):
        self.order_id += 1
        order = {
            'id': str(self.order_id),
            'symbol': symbol,
            'type': type,
            'side': side,
            'amount': amount,
            'price': price,
            'params': params or {},
            'status': 'open'
        }
        self.orders[order['id']] = order
        self.last_args = (symbol, type, side, amount, price, params)
        return order

    def cancel_order(self, order_id, symbol):
        if order_id not in self.orders:
            raise Exception("Order not found")
        self.orders[order_id]['status'] = 'canceled'
        self.cancelled.add(order_id)
        return {'id': order_id, 'status': 'canceled'}

@pytest.fixture
def dummy_exchange():
    return DummyExchange()

@pytest.fixture
def order_manager(dummy_exchange):
    return OrderManager(dummy_exchange, "BTC/USDT")

def test_place_market_order_success(order_manager, dummy_exchange):
    order = order_manager.place_market_order("buy", 0.1)
    assert order['type'] == 'market'
    assert order['side'] == 'buy'
    assert order['amount'] == 0.1
    assert order['symbol'] == "BTC/USDT"

def test_place_market_order_with_leverage(order_manager, dummy_exchange):
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
        order_manager.cancel_order("99999")  # Not existent
