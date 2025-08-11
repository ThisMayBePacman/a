# path: execution/position_manager.py
import logging
import threading
from typing import Any, Dict
from config import TICK_SIZE
from execution.order_manager import OrderManager
from risk.sl_tp import calculate_initial_sl_tp
from risk.rules import RULES
from utils.price_utils import align_price
import ccxt

logger = logging.getLogger(__name__)


class PositionManager:
    def __init__(self, exchange: Any, symbol: str, order_manager: OrderManager):
        """
        Initialise le gestionnaire de position pour un symbole donné.

        Args:
            exchange (Any): Instance de l'API exchange (ex: ccxt) pour récupérer ordres/positions.
            symbol (str): Symbole de trading géré (ex: 'BTC/USDT').
            order_manager (OrderManager): Gestionnaire d'ordres associé pour passer/canceller des ordres.
        """
        self.exchange = exchange
        self.symbol = symbol
        self.om = order_manager
        self.active: Dict[str, Any] | None = None
        self._lock = threading.RLock()
        logger.info(f"PositionManager initialized for {symbol}")

    @staticmethod
    def opposite(side: str) -> str:
        s = (side or "").lower()
        if s not in ("buy", "sell"):
            raise ValueError(f"side invalide: {side!r}")
        return "sell" if s == "buy" else "buy"

    def load_active(self) -> None:
        """
        Charge la position active depuis l'exchange et met à jour self.active.
        """
        with self._lock:
            logger.debug("Loading active position")
            try:
                opens = self.exchange.fetch_open_orders(symbol=self.symbol)
            except Exception as e:
                logger.error(f"Failed to fetch open orders in load_active: {e}")
                self.active = None
                return

            def _stop_price(o: Dict[str, Any]) -> float | None:
                return o.get("stopPrice") or (o.get("info") or {}).get("stopPrice")

            sl_orders = [o for o in opens if _stop_price(o)]
            tp_orders = [o for o in opens if not _stop_price(o)]
            if not sl_orders or not tp_orders:
                logger.info("No active SL/TP orders; no position.")
                self.active = None
                return
            try:
                positions = [
                    p
                    for p in self.exchange.fetch_positions([self.symbol])
                    if p["symbol"] == self.symbol and float(p["contracts"]) != 0
                ]
            except Exception as e:
                logger.error(f"Failed to fetch positions in load_active: {e}")
                self.active = None
                return
            if not positions:
                logger.warning("SL/TP orders found but no open contracts.")
                self.active = None
                return
            pos = positions[0]
            side = "buy" if float(pos["contracts"]) > 0 else "sell"
            size = abs(float(pos["contracts"]))
            entry = float(pos["entryPrice"])
            sl_price = float(_stop_price(sl_orders[0]) or sl_orders[0]["price"])
            tp_price = float(tp_orders[0]["price"])
            trail_dist = abs(entry - sl_price)
            self.active = {
                "side": side,
                "size": size,
                "entry_price": entry,
                "tp_price": tp_price,
                "current_sl_price": sl_price,
                "trail_dist": trail_dist,
                "ids": {"sl": sl_orders[0]["id"], "tp": tp_orders[0]["id"]},
            }
            logger.info(
                f"Loaded position: {side} {size:.6f}@{entry}, SL={sl_price}, TP={tp_price}"
            )

    def open_position(self, side: str, entry_price: float, size: float) -> None:
        """
        Ouvre une nouvelle position au marché, puis place les ordres SL/TP associés.

        Args:
            side (str): 'buy' pour position longue, 'sell' pour position courte.
            entry_price (float): Prix prévu d'entrée (utilisé si prix de remplissage inconnu).
            size (float): Taille de position (nombre de contrats ou volume).

        Raises:
            RuntimeError: Si les ordres de protection (SL/TP) n'ont pu être placés (position alors fermée en urgence).
        """
        with self._lock:
            # 1) Place market order
            mkt_order = self.om.place_market_order(side, size)
            try:
                # 2) Calcul des niveaux de SL/TP
                sltp = calculate_initial_sl_tp(self.exchange, self.symbol, entry_price, side)
                # 3) Place les ordres de TP et SL
                tp_order = self.om.place_limit_order(
                    side=self.opposite(side),
                    size=size,
                    price=sltp["tp_price"],
                    params={"reduceOnly": True},
                )
                sl_order = self.om.place_stop_limit_order(
                    side=self.opposite(side),
                    size=size,
                    price=sltp["sl_price"],
                    params={"stopPrice": sltp["sl_price"], "reduceOnly": True},
                )
            except Exception as e:
                logger.error(f"Failed to place SL/TP orders: {e}")
                try:
                    self._emergency_exit("SL/TP placement failure")
                except Exception as ee:
                    logger.critical(f"Emergency exit failed after SL/TP error: {ee}")
                raise RuntimeError("Failed to open position safely, position closed") from e
            # 4) Enregistrement de la position active
            fill_price = float(mkt_order.get("average") or mkt_order.get("price") or entry_price)
            self.active = {
                "side": side,
                "size": float(size),
                "entry_price": fill_price,
                "tp_price": float(sltp["tp_price"]),
                "current_sl_price": float(sltp["sl_price"]),
                "trail_dist": float(sltp["trail_dist"]),
                "ids": {"mkt": mkt_order["id"], "tp": tp_order["id"], "sl": sl_order["id"]},
            }
            logger.info(
                f"Opened position: {side} {size:.6f}@{fill_price}, SL={sltp['sl_price']}, TP={sltp['tp_price']}"
            )

    def update_trail(self, df5: Any) -> None:
        """
        Ajuste le stop loss suiveur (trail) en fonction du dernier prix de clôture.
        """
        with self._lock:
            if not self.active:
                logger.debug("No active position; skip trail update.")
                return
            # Dernier prix de clôture connu
            price = float(df5.close.iloc[-1])
            side = self.active["side"]
            trail = self.active["trail_dist"]
            old_sl = self.active["current_sl_price"]
            if side == "buy":
                new_sl = align_price(price - trail, TICK_SIZE, mode="down")
                cond = new_sl > old_sl
            else:
                new_sl = align_price(price + trail, TICK_SIZE, mode="up")
                cond = new_sl < old_sl
            if not cond:
                logger.debug(f"Trail condition unmet: old_sl={old_sl}, computed new_sl={new_sl}")
                return
            exit_side = "sell" if side == "buy" else "buy"
            logger.info(f"Updating SL from {old_sl} to {new_sl}")
            try:
                self.exchange.cancel_order(self.active["ids"]["sl"], symbol=self.symbol)
                logger.debug(f"Cancelled old SL order id={self.active['ids']['sl']}")
                sl_order = self.exchange.create_order(
                    self.symbol,
                    "limit",
                    exit_side,
                    self.active["size"],
                    new_sl,
                    {"stopPrice": new_sl, "reduceOnly": True},
                )
                self.active["ids"]["sl"] = sl_order["id"]
                self.active["current_sl_price"] = new_sl
                logger.info(f"Created new SL order id={sl_order['id']} at {new_sl}")
            except (ccxt.OrderNotFound, ccxt.InvalidOrder):
                logger.warning("SL order missing or invalid, triggering emergency exit")
                self._emergency_exit("SL order missing")
                return
            except ccxt.BaseError:
                logger.exception("Failed CCXT update_trail; leaving state unchanged")
                self._emergency_exit("SL update failure")
                return

    def check_exit(self) -> None:
        """
        Vérifie si la position a été fermée ou si SL/TP ont été exécutés.
        """
        with self._lock:
            if not self.active:
                logger.debug("No active position; skip exit check.")
                return
            logger.debug("Checking exit conditions")
            try:
                positions = [
                    p
                    for p in self.exchange.fetch_positions([self.symbol])
                    if p["symbol"] == self.symbol and float(p["contracts"]) != 0
                ]
            except Exception as e:
                logger.error(f"Failed to fetch positions in check_exit: {e}")
                return
            if not positions:
                logger.info("Position closed (contracts=0)")
                self._cancel_all_open()
                self.active = None
                return
            try:
                opens = self.exchange.fetch_open_orders(symbol=self.symbol)
            except Exception as e:
                logger.error(f"Failed to fetch open orders in check_exit: {e}")
                return
            open_ids = {o["id"] for o in opens}
            ids = self.active.get("ids", {})
            if ids.get("sl") not in open_ids and ids.get("tp") not in open_ids:
                # Plus aucun ordre de protection ouvert
                logger.warning("Position still open but SL/TP orders missing - emergency exit")
                self._emergency_exit("missing protective orders")
                return

    @property
    def entry_price(self):
        return self.active.get("entry_price") if self.active else None

    @property
    def tp_price(self):
        return self.active.get("tp_price") if self.active else None

    def watchdog(self, current_price: float) -> None:
        """
        Parcourt les règles de risque et exécute l'action associée si une condition est remplie.
        """
        with self._lock:
            for name, rule in RULES.items():
                try:
                    if rule["condition"](self, current_price):
                        logger.warning(f"Watchdog triggered rule `{name}` at price {current_price}")
                        rule["action"](self)
                except Exception as e:
                    logger.error(f"Error in watchdog rule `{name}`: {e}")

    def _purge_stale_reduce_only(self, side: str) -> None:
        """
        Annule les ordres `reduceOnly` encore ouverts du côté donné.
        Détecte reduceOnly dans o['reduceOnly'], o['info']['reduceOnly'] ou o['params']['reduceOnly'].
        """
        try:
            opens = self.exchange.fetch_open_orders(symbol=self.symbol)
        except Exception as e:
            logger.error(f"Failed to fetch open orders in purge_stale: {e}")
            return

        def _is_reduce(o: Dict[str, Any]) -> bool:
            info = o.get("info") or {}
            params = o.get("params") or {}
            return bool(
                o.get("reduceOnly") or info.get("reduceOnly") or params.get("reduceOnly")
            )

        for o in opens:
            if o.get("side") == side and _is_reduce(o):
                try:
                    self.exchange.cancel_order(o["id"], symbol=self.symbol)
                    logger.info(f"Cancelled stale reduceOnly {side} id={o['id']}")
                except Exception as e:
                    logger.warning(f"Cancel stale failed: {e}")

    def _cancel_all_open(self) -> None:
        try:
            opens = self.exchange.fetch_open_orders(symbol=self.symbol)
        except Exception as e:
            logger.error(f"Failed to fetch open orders in cancel_all_open: {e}")
            return
        for o in opens:
            try:
                self.exchange.cancel_order(o["id"], symbol=self.symbol)
            except Exception as e:
                logger.warning(f"Failed to cancel order {o.get('id')}: {e}")

    def _position_contracts(self) -> float:
        try:
            positions = [
                p
                for p in self.exchange.fetch_positions([self.symbol])
                if p["symbol"] == self.symbol and float(p.get("contracts") or 0) != 0
            ]
        except Exception:
            return 0.0
        return float(positions[0]["contracts"]) if positions else 0.0

    def _emergency_exit(self, reason: str) -> None:
        with self._lock:
            if getattr(self, "closing", False):
                logger.debug("Already closing — skip")
                return
            self.closing = True
            try:
                logger.error(f"Emergency exit triggered due to {reason}")
                # Si déjà flat, ne rien faire
                if self._position_contracts() == 0.0:
                    logger.info("Already flat — skip emergency market")
                    self._cancel_all_open()
                    self.active = None
                    return
                exit_side = "sell" if self._position_contracts() > 0 else "buy"
                qty = abs(self._position_contracts() or (self.active and self.active["size"]) or 0.0)
                # Annule les ordres reduceOnly existants du côté choisi
                self._purge_stale_reduce_only(exit_side)
                # Envoi d'un ordre marché en reduceOnly pour fermer la position
                self.om.place_market_order(exit_side, qty, params={"reduceOnly": True})
                # Annule tous les ordres restants
                self._cancel_all_open()
                self.active = None
            finally:
                self.closing = False

    def _handle_drawdown(self) -> None:
        # Implémentation spécifique pour le drawdown (ex: alertes, réduction de position)
        logger.warning("Drawdown severe détecté - _handle_drawdown non implémenté")
