# execution/position_manager.py
import logging
import threading
from typing import Any, Dict, Optional

import ccxt
import pandas as pd

from risk.strategies.base import StrategyContext, PositionSnapshot
from config import TICK_SIZE
from execution.order_manager import OrderManager
from risk.sl_tp import calculate_initial_sl_tp
from risk.rules import RULES
from utils.price_utils import align_price

logger = logging.getLogger(__name__)


class PositionManager:
    def __init__(self, exchange, symbol, order_manager, strategy: Optional[object] = None):
        self.exchange = exchange
        self.symbol = symbol
        self.om = order_manager
        self.strategy = strategy
        self._lock = threading.RLock()
        self.active = None

    @staticmethod
    def opposite(side: str) -> str:
        s = (side or "").lower()
        if s not in ("buy", "sell"):
            raise ValueError(f"side invalide: {side!r}")
        return "sell" if s == "buy" else "buy"

    def load_active(self) -> None:
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
                "ids": {
                    "sl": sl_orders[0]["id"],
                    "tp": tp_orders[0]["id"],
                    # pas d’info mkt lors d’un reload
                },
                # utile aux stratégies si rechargé
                "tp_initial": tp_price,
            }
            logger.info("Loaded position: %s %.6f@%s, SL=%s, TP=%s", side, size, entry, sl_price, tp_price)  # pragma: no cover

    def open_position(self, side: str, entry_price: float, size: float) -> None:
        with self._lock:
            # 1) Ordre marché
            mkt_order = self.om.place_market_order(side, size)
            mkt_id = (mkt_order or {}).get("id")
            fill_price = (
                (mkt_order or {}).get("average")
                or (mkt_order or {}).get("price")
                or entry_price
            )

            try:
                # 2) Calcul SL/TP basé sur le vrai prix de remplissage
                sltp = calculate_initial_sl_tp(self.exchange, self.symbol, float(fill_price), side)

                # 3) Placement des ordres de protection
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

                sl_order_price = float(sltp["sl_price"])
                tp_order_price = float(sltp["tp_price"])

                # 4) État actif
                self.active = {
                    "side": side,
                    "size": size,
                    "entry_price": float(fill_price),
                    "current_sl_price": sl_order_price,
                    "tp_price": tp_order_price,
                    "trail_dist": sltp["trail_dist"],
                    "ids": {
                        "mkt": mkt_id,
                        "tp": (tp_order or {}).get("id"),
                        "sl": (sl_order or {}).get("id"),
                    },
                    # utile pour bump TP
                    "tp_initial": tp_order_price,
                }
            except Exception as e:
                logger.error(f"Failed to place SL/TP orders: {e}")
                try:
                    self._emergency_exit("SL/TP placement failure")
                except Exception as ee:
                    logger.critical(f"Emergency exit failed after SL/TP error: {ee}")
                raise RuntimeError("Failed to open position safely, position closed") from e

    def update_trail(self, df: pd.DataFrame) -> None:
        # -- early exit si flat --
        if not self.active:
            return

        # --- snapshot pour éviter de relire self.active si ça bouge entre-temps ---
        active = self.active
        side = active["side"]                # "long" | "short"
        price = float(df["close"].iloc[-1])
        trail = active["trail_dist"]
        old_sl = active.get("current_sl_price")
        old_tp = active.get("tp_price")

        # --------- MODE LEGACY (sans stratégie) ----------
        if not self.strategy:
            if side == "long":
                new_sl = align_price(price - trail, TICK_SIZE, mode="down")
                # monotonicité: on ne descend jamais un SL long
                if old_sl is not None and new_sl <= old_sl:
                    return
            else:  # short
                new_sl = align_price(price + trail, TICK_SIZE, mode="up")
                # monotonicité: on ne remonte jamais un SL short
                if old_sl is not None and new_sl >= old_sl:
                    return

            # re-check: encore en position ?
            if not self.active:
                return
            self._replace_sl(new_sl)
            return

        # --------- MODE STRATÉGIE ----------
        snap = PositionSnapshot(
            entry_price=active["entry_price"],
            current_price=price,
            qty_open=active.get("size", 0.0),
            qty_remaining=active.get("qty_remaining", active.get("size", 0.0)),
            sl_current=active.get("current_sl_price"),
            tp_current=active.get("tp_price"),
            tp_initial=active.get("tp_initial"),
            trail_dist=trail,
        )
        ctx = StrategyContext(symbol=self.symbol, side=side, tick_size=TICK_SIZE)
        desired = self.strategy.compute_targets(snap, ctx)

        # --- SL monotone ---
        if desired.sl_price is not None and old_sl is not None:
            if (side == "long" and desired.sl_price > old_sl) or \
            (side == "short" and desired.sl_price < old_sl):
                if not self.active:
                    return
                self._replace_sl(desired.sl_price)

        # --- TP si changement ---
        if desired.tp_price is not None and old_tp is not None and desired.tp_price != old_tp:
            if not self.active:
                return
            self._replace_tp(desired.tp_price)

    def check_exit(self) -> None:
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
        with self._lock:
            for name, rule in RULES.items():
                try:
                    if rule["condition"](self, current_price):
                        logger.warning(f"Watchdog triggered rule `{name}` at price {current_price}")
                        rule["action"](self)
                except Exception as e:
                    logger.error(f"Error in watchdog rule `{name}`: {e}")

    def _purge_stale_reduce_only(self, side: str) -> None:
        try:
            opens = self.exchange.fetch_open_orders(symbol=self.symbol)
        except Exception as e:
            logger.error(f"Failed to fetch open orders in purge_stale: {e}")
            return

        def _is_reduce(o: Dict[str, Any]) -> bool:
            info = o.get("info") or {}
            params = o.get("params") or {}
            return bool(o.get("reduceOnly") or info.get("reduceOnly") or params.get("reduceOnly"))

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
                if self._position_contracts() == 0.0:
                    logger.info("Already flat — skip emergency market")
                    self._cancel_all_open()
                    self.active = None
                    return
                exit_side = "sell" if self._position_contracts() > 0 else "buy"
                qty = abs(self._position_contracts() or (self.active and self.active["size"]) or 0.0)
                self._purge_stale_reduce_only(exit_side)
                self.om.place_market_order(exit_side, qty, params={"reduceOnly": True})
                self._cancel_all_open()
                self.active = None
            finally:
                self.closing = False

    # Helpers internes
    def _replace_sl(self, new_sl: float) -> None:
        # --- snapshot & garde ---
        active = self.active
        if not active or not active["ids"].get("sl"):
            return
        old_sl_id = active["ids"]["sl"]
        side = self.opposite(active["side"])
        size = active["size"]

        # --- cancel idempotent via OrderManager ---
        try:
            self.om.cancel_order(old_sl_id)
        except Exception as e:
            msg = str(e).lower()
            benign = any(s in msg for s in ("notfound", "unknown order", "already canceled", "not open"))
            if not benign:
                logger.error(f"cancel SL unexpected error {old_sl_id}: {e}")
                self._emergency_exit("cancel SL failed")
                return
            logger.info(f"Cancel SL benign (already gone): {old_sl_id} -> continue")

        # --- recheck état avant de replacer ---
        if self.active is None:
            return
        # si un autre cycle a déjà mis à jour l'id, ne rien faire
        if self.active["ids"].get("sl") not in (None, old_sl_id):
            return

        order = self.om.place_stop_limit_order(
            side=side,
            size=size,
            price=new_sl,
            params={"stopPrice": new_sl, "reduceOnly": True},
        )
        # sécuriser l'accès
        if self.active is not None:
            self.active["ids"]["sl"] = order.get("id")
            self.active["current_sl_price"] = new_sl


    def _replace_tp(self, new_tp: float) -> None:
        # --- snapshot & garde ---
        active = self.active
        if not active or not active["ids"].get("tp"):
            return
        old_tp_id = active["ids"]["tp"]
        side = self.opposite(active["side"])
        size = active["size"]

        # --- cancel idempotent via OrderManager ---
        try:
            self.om.cancel_order(old_tp_id)
        except Exception as e:
            msg = str(e).lower()
            benign = any(s in msg for s in ("notfound", "unknown order", "already canceled", "not open"))
            if not benign:
                logger.error(f"cancel TP unexpected error {old_tp_id}: {e}")
                self._emergency_exit("cancel TP failed")
                return
            logger.info(f"Cancel TP benign (already gone): {old_tp_id} -> continue")

        # --- recheck état avant de replacer ---
        if self.active is None:
            return
        if self.active["ids"].get("tp") not in (None, old_tp_id):
            return

        order = self.om.place_limit_order(
            side=side,
            size=size,
            price=new_tp,
            params={"reduceOnly": True},
        )
        if self.active is not None:
            self.active["ids"]["tp"] = order.get("id")
            self.active["tp_price"] = new_tp
            
    def _handle_drawdown(self) -> None:
        logger.warning("Drawdown severe détecté - _handle_drawdown non implémenté")  # pragma: no cover
