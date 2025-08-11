# path: tests/conftest.py
import pytest
import ccxt

class DummyExchange:
    def __init__(self):
        # Track orders and positions by symbol
        self.orders = {}  # order_id -> order dict
        self.positions = {}  # symbol -> (position_size, entry_price)
        self.cancelled = set()
        self._order_id = 0

    def create_order(self, symbol, type, side, amount, price=None, params=None):
        params = params or {}
        self._order_id += 1
        order_id = str(self._order_id)
        # Determine status: market orders fill immediately (closed), others remain open
        status = 'closed' if type == 'market' else 'open'
        # Update position for market orders (immediate execution) or ignore for limit orders
        if type == 'market':
            # Ensure symbol in positions tracking
            if symbol not in self.positions:
                self.positions[symbol] = (0.0, None)
            pos_size, entry_price = self.positions[symbol]
            if params.get('reduceOnly'):
                # Reduce existing position without opening opposite
                if side == 'buy':
                    # Closing a short position by buying
                    if pos_size < 0:
                        new_size = pos_size + amount
                        if new_size > 0:
                            new_size = 0.0  # do not flip to long in reduceOnly
                        pos_size = new_size
                elif side == 'sell':
                    # Closing a long position by selling
                    if pos_size > 0:
                        new_size = pos_size - amount
                        if new_size < 0:
                            new_size = 0.0
                        pos_size = new_size
            else:
                # Opening or increasing a position
                if side == 'buy':
                    pos_size += amount
                else:
                    pos_size -= amount
                # Set entry price if position was previously zero (new position)
                if entry_price is None or abs(entry_price) < 1e-9 or abs(pos_size) == amount:
                    # use provided price if available (market orders may not have price)
                    entry_price = float(price) if price else (entry_price or 100.0)
            # Update stored position
            self.positions[symbol] = (pos_size, entry_price)
        # Create order record
        order = {
            'id': order_id,
            'symbol': symbol,
            'type': type,
            'side': side,
            'amount': amount,
            'price': price,
            'params': params,
            'status': status
        }
        self.orders[order_id] = order
        return order

    def cancel_order(self, order_id, symbol=None):
        # Simulate cancellation of an existing order
        if order_id not in self.orders:
            # Simulate ccxt OrderNotFound exception
            raise ccxt.OrderNotFound("Order not found")
        # Mark as canceled
        self.orders[order_id]['status'] = 'canceled'
        self.cancelled.add(order_id)
        return { 'id': order_id, 'status': 'canceled' }

    def fetch_open_orders(self, symbol=None):
        # Return orders still open (not filled or canceled)
        orders = [o for o in self.orders.values() if o['status'] == 'open']
        if symbol:
            orders = [o for o in orders if o['symbol'] == symbol]
        return orders

    def fetch_positions(self, symbols=None):
        # Return non-zero positions for requested symbols (or all if None)
        positions_list = []
        target_symbols = symbols or list(self.positions.keys())
        for sym in target_symbols:
            if sym in self.positions:
                contracts, entry_price = self.positions[sym]
                if abs(contracts) > 1e-9:
                    positions_list.append({ 'symbol': sym, 'contracts': str(contracts), 'entryPrice': entry_price or 0.0 })
        return positions_list

@pytest.fixture
def dummy_exchange():
    return DummyExchange()

@pytest.fixture
def order_manager(dummy_exchange):
    from execution.order_manager import OrderManager
    return OrderManager(dummy_exchange, "BTC/USDT")
