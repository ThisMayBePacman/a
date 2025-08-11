# path: execution/order_manager.py
import logging
from utils.decorators import verify_order
from typing import Any, Dict, Optional
logger = logging.getLogger(__name__)

class OrderManager:
    """
    Wrapper pour la création et l'annulation d'ordres CCXT.
    """
    def __init__(self, exchange: Any, symbol: str):
        """
        Initialise le gestionnaire d'ordres pour un symbole et un exchange donnés.

        Args:
            exchange (Any): Instance d'API de l'exchange (CCXT ou simili).
            symbol (str): Symbole de trading (ex: 'BTC/USDT').
        """
        self.exchange = exchange
        self.symbol = symbol
    
    @verify_order
    def place_market_order(self, side: str, size: float, leverage: Optional[float] = None) -> Dict[str, Any]:
        """
        Passe un ordre au marché (market order).

        Args:
            side (str): 'buy' pour achat ou 'sell' pour vente.
            size (float): Quantité de l'actif à trader (doit être > 0).
            leverage (float, optionnel): Effet de levier à appliquer (selon support exchange).
        
        Returns:
            dict: Détails de l'ordre retourné par l'exchange.

        Raises:
            ValueError: Si `side` n'est pas 'buy' ou 'sell', ou si `size` <= 0.
        """
        if side not in ("buy", "sell"):
            raise ValueError("side must be 'buy' or 'sell'")
        if size <= 0:
            raise ValueError("size must be positive")

        params: Dict[str, Any] = {}
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
    def place_limit_order(self, side: str, size: float, price: float, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Passe un ordre limit (généralement en `reduceOnly`).

        Args:
            side (str): 'buy' ou 'sell'.
            size (float): Taille de l'ordre (> 0).
            price (float): Prix limite (> 0).
            params (dict, optionnel): Paramètres additionnels pour l'ordre (ex: {'reduceOnly': True}).
        
        Returns:
            dict: Détails de l'ordre créé.

        Raises:
            ValueError: Si `side` invalide, ou `size` <= 0, ou `price` <= 0.
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
    def place_stop_limit_order(self, side: str, size: float, price: float, stop_price: Optional[float] = None, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Passe un ordre stop limit.

        Pour l'API CCXT (ex: Kraken) on utilise type 'limit' et on précise `stopPrice` dans params.

        Args:
            side (str): 'buy' ou 'sell'.
            size (float): Taille de l'ordre (> 0).
            price (float): Prix limite (> 0).
            stop_price (float, optionnel): Prix de déclenchement du stop (stopPrice).
            params (dict, optionnel): Autres paramètres additionnels (stopPrice peut y être passé).
        
        Returns:
            dict: Détails de l'ordre créé.

        Raises:
            ValueError: Si `side` invalide, ou `size` <= 0, ou `price` <= 0, ou `stop_price` non fourni ou <= 0.
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
        params['stopPrice'] = _stop_price
        logger.info(f"Placing stop limit order: {side} {size:.6f} {self.symbol} at {price} stop={_stop_price} params={params}")
        order = self.exchange.create_order(
            self.symbol, 'limit', side, size, price, params
        )
        logger.info(f"Stop limit order response: id={order['id']}, status={order.get('status')}")
        return order

    @verify_order
    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """
        Annule un ordre existant via son ID.

        Args:
            order_id (str): Identifiant de l'ordre à annuler.
        
        Returns:
            dict: Résultat de l'annulation retourné par l'exchange.

        Raises:
            ValueError: Si `order_id` n'est pas une chaîne non vide.
        """
        if not order_id or not isinstance(order_id, str):
            raise ValueError("order_id must be a non-empty string")
        logger.info(f"Cancelling order: id={order_id}")
        result = self.exchange.cancel_order(order_id, self.symbol)
        logger.info(f"Cancel result: {result}")
        return result
