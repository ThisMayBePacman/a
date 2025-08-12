# path: execution/order_manager.py
import logging
from typing import Any, Dict, Optional

from utils.decorators import verify_order

logger = logging.getLogger(__name__)

# CCXT change parfois l’emplacement de l’exception selon les versions
try:
    from ccxt.base.errors import OrderNotFound, InvalidOrder
except Exception:  # fallback large si la structure change
    class OrderNotFound(Exception): ...
    class InvalidOrder(Exception): ...

class OrderManager:
    """
    Wrapper pour la création et l'annulation d'ordres CCXT.
    """

    def __init__(self, exchange: Any, symbol: str) -> None:
        """
        Initialise le gestionnaire d'ordres pour un symbole et un exchange donnés.

        Args:
            exchange: Instance d'API de l'exchange (CCXT ou simili).
            symbol: Symbole de trading (ex: 'BTC/USDT').
        """
        self.exchange = exchange
        self.symbol = symbol

    @verify_order
    def place_market_order(
        self,
        side: str,
        size: float,
        leverage: Optional[float] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Passe un ordre au marché (market order).

        Args:
            side: 'buy' pour achat ou 'sell' pour vente.
            size: Quantité de l'actif à trader (> 0).
            leverage: Effet de levier à appliquer (selon support exchange).
            params: Paramètres additionnels transmis à l'exchange
                (ex: {'reduceOnly': True} pour une fermeture d'urgence).

        Returns:
            Détails de l'ordre retourné par l'exchange.

        Raises:
            ValueError: Si `side` n'est pas 'buy' ou 'sell', ou si `size` <= 0.
        """
        if side not in ("buy", "sell"):
            raise ValueError("side must be 'buy' or 'sell'")
        if size <= 0:
            raise ValueError("size must be positive")

        final_params: Dict[str, Any] = dict(params or {})
        if leverage is not None and "leverage" not in final_params:
            final_params["leverage"] = leverage

        logger.info(
            f"Placing market order: {side} {size:.6f} {self.symbol} with params={final_params}"
        )
        order = self.exchange.create_order(
            symbol=self.symbol,
            type="market",
            side=side,
            amount=size,
            price=None,
            params=final_params,
        )
        logger.info(
            "Market order response: id=%s, status=%s",
            order.get("id"),
            order.get("status"),
        )
        return order

    @verify_order
    def place_limit_order(
        self,
        side: str,
        size: float,
        price: float,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Passe un ordre limit (généralement en `reduceOnly`).

        Args:
            side: 'buy' ou 'sell'.
            size: Taille de l'ordre (> 0).
            price: Prix limite (> 0).
            params: Paramètres additionnels (ex: {'reduceOnly': True}).

        Returns:
            Détails de l'ordre créé.

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
        logger.info(
            f"Placing limit order: {side} {size:.6f} {self.symbol} at {price} params={params}"
        )
        order = self.exchange.create_order(
            self.symbol, "limit", side, size, price, params
        )
        logger.info(
            "Limit order response: id=%s, status=%s",
            order.get("id"),
            order.get("status"),
        )
        return order

    @verify_order
    def place_stop_limit_order(
        self,
        side: str,
        size: float,
        price: float,
        stop_price: Optional[float] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Passe un ordre stop limit.

        Pour l'API CCXT (ex: Kraken) on utilise type 'limit' et on précise `stopPrice` dans params.

        Args:
            side: 'buy' ou 'sell'.
            size: Taille de l'ordre (> 0).
            price: Prix limite (> 0).
            stop_price: Prix de déclenchement du stop (stopPrice).
            params: Autres paramètres additionnels (stopPrice peut y être passé).

        Returns:
            Détails de l'ordre créé.

        Raises:
            ValueError: Si `side` invalide, ou `size` <= 0, ou `price` <= 0, ou `stop_price` manquant/<= 0.
        """
        if side not in ("buy", "sell"):
            raise ValueError("side must be 'buy' or 'sell'")
        if size <= 0:
            raise ValueError("size must be positive")
        if price <= 0:
            raise ValueError("price must be positive")
        params = params or {}
        _stop_price = stop_price if stop_price is not None else params.get("stopPrice")
        if _stop_price is None or _stop_price <= 0:
            raise ValueError("stop_price must be provided and positive")
        params["stopPrice"] = _stop_price
        logger.info(
            f"Placing stop limit order: {side} {size:.6f} {self.symbol} at {price} stop={_stop_price} params={params}"
        )
        order = self.exchange.create_order(
            self.symbol, "limit", side, size, price, params
        )
        logger.info(
            "Stop limit order response: id=%s, status=%s",
            order.get("id"),
            order.get("status"),
        )
        return order

    @verify_order
    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """
        Annule un ordre existant via son ID, de manière idempotente.
        Si l'ordre est déjà exécuté/annulé côté exchange, on traite cela comme un succès ("canceled").
        """
        if not order_id or not isinstance(order_id, str):
            raise ValueError("order_id must be a non-empty string")

        logger.info("Cancelling order: id=%s", order_id)

        try:
            result = self.exchange.cancel_order(order_id, self.symbol)
            # CCXT peut renvoyer {'id': ..., 'status': 'canceled'} ou similaire
            logger.info("Cancel result: id=%s, status=%s", result.get("id"), result.get("status"))
            return result

        except OrderNotFound as e:
            # Cas normal si le TP a été rempli et que l'exchange a auto‑annulé le SL reduceOnly
            logger.info("Cancel benign (already gone): id=%s, reason=%s", order_id, e)
            return {"id": order_id, "status": "canceled"}

        except InvalidOrder as e:
            # Certains exchanges renvoient InvalidOrder quand l'ordre n'est plus ouvert
            msg = str(e).lower()
            if "not found" in msg or "unknown order" in msg or "not open" in msg:
                logger.info("Cancel benign (invalid/not open): id=%s, reason=%s", order_id, e)
                return {"id": order_id, "status": "canceled"}
            logger.error("Cancel unexpected InvalidOrder: id=%s, error=%s", order_id, e)
            raise

        except Exception as e:
            # Dernier filet : tolère aussi quelques messages fréquents typiques
            msg = str(e).lower()
            benign = any(s in msg for s in ["notfound", "unknown order", "already canceled", "not open"])
            if benign:
                logger.info("Cancel benign (generic): id=%s, reason=%s", order_id, e)
                return {"id": order_id, "status": "canceled"}
            logger.error("Cancel unexpected error: id=%s, error=%s", order_id, e)
            raise