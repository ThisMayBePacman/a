# execution/order_manager.py
import logging
from utils.decorators import verify_order
logger = logging.getLogger(__name__)

class OrderManager:
    """
    Wrapper pour la création et l'annulation d'ordres CCXT.
    """
    def __init__(self, exchange, symbol):
        self.exchange = exchange
        self.symbol = symbol
    
    @verify_order
    def place_market_order(self, side: str, size: float, leverage: float = None):
        # Ajout de la validation du paramètre side
        if side not in ("buy", "sell"):
            raise ValueError("side must be 'buy' or 'sell'")
        if size <= 0:
            raise ValueError("size must be positive")

        params = {}
        if leverage is not None:
            params['leverage'] = leverage
        logger.info(f"Placing market order: {side} {size:.6f} {self.symbol} with params={params}")
        order = self.exchange.create_order(
            symbol=self.symbol,
            type='market',
            side=side,
            amount=size,
            price=None,
            params=params
        )
        logger.info(f"Market order response: id={order['id']}, status={order.get('status')}")
        return order
    
    @verify_order
    def place_limit_order(self, side: str, size: float, price: float, params=None):
        """
        Place un ordre limit en reduceOnly et log l'opération.
        """
        if side not in ("buy", "sell"):
            raise ValueError("side must be 'buy' or 'sell'")
        if size <= 0:
            raise ValueError("size must be positive")
        if price <= 0:
            raise ValueError("price must be positive")
        params = params or {}
        logger.info(f"Placing limit order: {side} {size:.6f} {self.symbol} at {price} params={params}")
        order = self.exchange.create_order(
            self.symbol, 'limit', side, size, price, params
        )
        logger.info(f"Limit order response: id={order['id']}, status={order.get('status')}")
        return order

    @verify_order
    def place_stop_limit_order(self, side: str, size: float, price: float, stop_price: float = None, params=None):
        """
        Place un ordre stop limit et log l'opération.
        Pour Kraken/CCXT : type 'limit' + params['stopPrice']
        """
        if side not in ("buy", "sell"):
            raise ValueError("side must be 'buy' or 'sell'")
        if size <= 0:
            raise ValueError("size must be positive")
        if price <= 0:
            raise ValueError("price must be positive")
        params = params or {}
        _stop_price = stop_price if stop_price is not None else params.get('stopPrice')
        if _stop_price is None or _stop_price <= 0:
            raise ValueError("stop_price must be provided and positive")
        params['stopPrice'] = _stop_price  # s'assure qu'il est bien dans params
        logger.info(f"Placing stop limit order: {side} {size:.6f} {self.symbol} at {price} stop={_stop_price} params={params}")
        order = self.exchange.create_order(
            self.symbol, 'limit', side, size, price, params
        )
        logger.info(f"Stop limit order response: id={order['id']}, status={order.get('status')}")
        return order

    @verify_order
    def cancel_order(self, order_id: str):
        """
        Annule un ordre existant par son ID et log l'opération.
        """
        if not order_id or not isinstance(order_id, str):
            raise ValueError("order_id must be a non-empty string")
        logger.info(f"Cancelling order: id={order_id}")
        result = self.exchange.cancel_order(order_id, self.symbol)
        logger.info(f"Cancel result: {result}")
        return result