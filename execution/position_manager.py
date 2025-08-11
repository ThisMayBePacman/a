 # execution/position_manager.py
import logging
from config import TICK_SIZE
from execution.order_manager import OrderManager
from risk.sl_tp import calculate_initial_sl_tp
from risk.rules import RULES
import ccxt
logger = logging.getLogger(__name__)

def align_price(price):
    return round(price / TICK_SIZE) * TICK_SIZE

class PositionManager:
    def __init__(self, exchange, symbol, order_manager: OrderManager):
        self.exchange = exchange
        self.symbol = symbol
        self.om = order_manager
        self.active = None  # dict normalisé quand position ouverte
        logger.info(f"PositionManager initialized for {symbol}")

    @staticmethod
    def opposite(side: str) -> str:
        s = (side or "").lower()
        if s not in ("buy", "sell"):
            raise ValueError(f"side invalide: {side!r}")
        return "sell" if s == "buy" else "buy"

    def load_active(self):
        """
        Charge la position active depuis l'exchange et initialise self.active.
        """
        logger.debug("Loading active position")
        opens = self.exchange.fetch_open_orders(symbol=self.symbol)
        def _stop_price(o):
            return o.get('stopPrice') or (o.get('info') or {}).get('stopPrice')
        sl_orders = [o for o in opens if _stop_price(o)]
        tp_orders = [o for o in opens if not _stop_price(o)]
        if not sl_orders or not tp_orders:
            logger.info("No active SL/TP orders; no position.")
            self.active = None
            return

        positions = [p for p in self.exchange.fetch_positions([self.symbol])
                     if p['symbol']==self.symbol and float(p['contracts'])!=0]
        if not positions:
            logger.warning("SL/TP orders found but no open contracts.")
            self.active = None
            return

        pos = positions[0]
        side = 'buy' if float(pos['contracts'])>0 else 'sell'
        size = abs(float(pos['contracts']))
        entry = float(pos['entryPrice'])
        # SL : utiliser le stopPrice (trigger). fallback sur price si absent
        sl_price = float(_stop_price(sl_orders[0]) or sl_orders[0]['price'])
        tp_price = float(tp_orders[0]['price'])
        trail_dist = abs(entry - sl_price)

        self.active = {
            'side': side,
            'size': size,
            'entry_price': entry,
            'tp_price': tp_price,
            'current_sl_price': sl_price,
            'trail_dist': trail_dist,
            'ids': {'sl': sl_orders[0]['id'], 'tp': tp_orders[0]['id']},
        }
        logger.info(f"Loaded position: {side} {size:.6f}@{entry}, SL={sl_price}, TP={tp_price}")

    def open_position(self, side, entry_price, size):
        # 1) Place market
        mkt = self.om.place_market_order(side, size)

        # 2) Calcule SL/TP
        sltp = calculate_initial_sl_tp(self.exchange, self.symbol, entry_price, side)
        
        # 3) Place SL & TP via order_manager
        ids = self.om.place_limit_order(
                  side=self.opposite(side),
                  size=size,
                  price=sltp['tp_price'],
                  params={'reduceOnly': True}
              ), self.om.place_stop_limit_order(
                  side=self.opposite(side),
                  size=size,
                  price=sltp['sl_price'],
                  params={'stopPrice': sltp['sl_price'], 'reduceOnly': True}
              )

        # 4) Enregistrement
        fill_price = float(mkt.get('average') or mkt.get('price') or entry_price)
        self.active = {
            'side': side,
            'size': float(size),
            'entry_price': fill_price,
            'tp_price': float(sltp['tp_price']),
            'current_sl_price': float(sltp['sl_price']),
            'trail_dist': float(sltp['trail_dist']),
            'ids': {'mkt': mkt['id'], 'tp': ids[0]['id'], 'sl': ids[1]['id']},
        }
  
    def update_trail(self, df5):
        """
        Ajuste le stop suiveur basé sur le dernier close de df5.
        """
        if not self.active:
            logger.debug("No active position; skip trail update.")
            return
        price = df5.close.iloc[-1]
        side = self.active['side']
        trail = self.active['trail_dist']
        old_sl = self.active['current_sl_price']

        if side=='buy':
            new_sl = align_price(price - trail)
            cond = new_sl > old_sl
            exit_side = 'sell'
        else:
            new_sl = align_price(price + trail)
            cond = new_sl < old_sl
            exit_side = 'buy'

        if not cond:
            logger.debug(f"Trail condition unmet: old_sl={old_sl}, computed new_sl={new_sl}")
            return

        logger.info(f"Updating SL from {old_sl} to {new_sl}")
        try:
            self.exchange.cancel_order(self.active['ids']['sl'], symbol=self.symbol)
            logger.debug(f"Cancelled old SL order id={self.active['ids']['sl']}")
            sl_order = self.exchange.create_order(
                self.symbol, 'limit', exit_side,
                self.active['size'], new_sl,
                {'stopPrice': new_sl, 'reduceOnly': True}
            )
            self.active['ids']['sl'] = sl_order['id']
            self.active['current_sl_price'] = new_sl
            logger.info(f"Created new SL order id={sl_order['id']} at {new_sl}")
        except (ccxt.OrderNotFound, ccxt.InvalidOrder) as e:
            logger.warning("SL non trouvé/invalidé, tentative de recréation propre...")
            # logique de reprise ici
        except ccxt.BaseError as e:
            logger.exception("Echec CCXT lors de la mise à jour du SL; état laissé inchangé")
            self._emergency_exit("SL update failure")
            return

    def check_exit(self):
        """
        Vérifie si la position a été fermée ou si SL/TP ont été exécutés.
        """
        if not self.active:
            logger.debug("No active position; skip exit check.")
            return
        logger.debug("Checking exit conditions")
        positions = [p for p in self.exchange.fetch_positions([self.symbol])
                     if p['symbol']==self.symbol and float(p['contracts'])!=0]
        if not positions:
            logger.info("Position closed (contracts=0)")
            self._cancel_all_open()
            self.active = None
            return

        opens = self.exchange.fetch_open_orders(symbol=self.symbol)
        open_ids = {o['id'] for o in opens}
        ids = self.active['ids']
        if ids['sl'] not in open_ids and ids['tp'] not in open_ids:
            logger.info("SL/TP orders no longer present; position exited.")
            self.active = None
    
     # --- Properties pour les règles ---
    @property
    def entry_price(self):
        return self.active.get('entry_price') if self.active else None

    @property
    def tp_price(self):
        return self.active.get('tp_price') if self.active else None

    def watchdog(self, current_price: float):
        """
        Parcourt la table RULES et exécute l'action dès que la condition est vraie.
        """
        for name, rule in RULES.items():
            try:
                if rule['condition'](self, current_price):
                    logger.warning(f"Watchdog triggered rule `{name}` at price {current_price}")
                    rule['action'](self)
            except Exception as e:
                logger.error(f"Error in watchdog rule `{name}`: {e}")
    def _purge_stale_reduce_only(self, side: str):
        opens = self.exchange.fetch_open_orders(symbol=self.symbol)
        def _is_reduce(o):
            info = o.get('info') or {}
            return bool(o.get('reduceOnly') or info.get('reduceOnly'))
        for o in opens:
            if o['side'] == side and _is_reduce(o):
                try:
                    self.exchange.cancel_order(o['id'], symbol=self.symbol)
                    logger.info(f"Cancelled stale reduceOnly {side} id={o['id']}")
                except Exception as e:
                    logger.warning(f"Cancel stale failed: {e}")

    def _cancel_all_open(self):
        try:
            opens = self.exchange.fetch_open_orders(symbol=self.symbol)
            for o in opens:
                try:
                    self.exchange.cancel_order(o['id'], symbol=self.symbol)
                except Exception:
                    pass
        except Exception:
            pass

    def _position_contracts(self) -> float:
        ps = [p for p in self.exchange.fetch_positions([self.symbol])
            if p['symbol']==self.symbol and float(p.get('contracts') or 0)!=0]
        return float(ps[0]['contracts']) if ps else 0.0

    def _emergency_exit(self, reason: str):
        if getattr(self, "closing", False):
            logger.debug("Already closing — skip")
            return
        self.closing = True
        try:
            logger.error(f"Emergency exit triggered due to {reason}")
            # si déjà flat, ne rien envoyer
            if self._position_contracts() == 0.0:
                logger.info("Already flat — skip emergency market")
                self._cancel_all_open()
                self.active = None
                return
            side = 'sell' if self.active and self.active['side']=='buy' else 'buy'
            qty  = abs(self._position_contracts() or (self.active and self.active['size']) or 0.0)
            # Nettoyer d’abord le book reduceOnly de ce côté
            self._purge_stale_reduce_only(side)
            # Market en reduceOnly => n’ouvre jamais de position inverse
            self.om.place_market_order(side, qty, params={'reduceOnly': True})
            # On nettoie les ordres restants
            self._cancel_all_open()
            self.active = None
        finally:
            self.closing = False

    def _handle_drawdown(self):
        # Implémentation spécifique pour le drawdown
        pass
    