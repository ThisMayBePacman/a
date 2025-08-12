# main.py
import logging
import time
from data.fetcher import create_exchange, fetch_ohlcv, resolve_symbol
from indicators.compute import compute_indicators
from strategy.signal import generate_signal
# plus besoin de place_market_order direct
from execution.order_manager import OrderManager
from execution.position_manager import PositionManager
from config import SYMBOL, TIMEFRAMES, LOOKBACK, POLL_INTERVAL, INVESTMENT_USD, LEVERAGE, STRATEGY, STRATEGY_PARAMS
import argparse
from risk.strategies.registry import make_from_name


# ========== LOGGER ==========
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler("logs/bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
def _parse_args():
    parser = argparse.ArgumentParser(description="Bot trading")
    parser.add_argument(
        "--strategy",
        choices=["trailing_sl_only", "trailing_sl_and_tp", "none", "legacy"],
        default=None,
        help="Nom de la stratégie. 'none'/'legacy' = trailing historique par défaut."
    )
    parser.add_argument(
        "--theta",
        type=float,
        default=None,
        help="Seuil (0–1) pour trailing_sl_and_tp (ex: 0.5)."
    )
    parser.add_argument(
        "--rho",
        type=float,
        default=None,
        help="Multiplicateur >= 0 pour bump TP (ex: 1.0)."
    )
    return parser.parse_args()
def main():
    # Création du client et résolution du symbole
    exchange = create_exchange()
    ccxt_symbol = resolve_symbol(exchange, SYMBOL)
    logger.info(f"> Utilisation du ticker CCXT : {ccxt_symbol}")
      # 🔸 CLI overrides
    args = _parse_args()
    # stratégie finale = CLI > config.py
    if args.strategy in (None, "none", "legacy"):
        strategy_name = STRATEGY  # peut être None
    else:
        strategy_name = args.strategy

    # paramètres finaux = config.py puis overrides CLI s'ils sont fournis
    params = dict(STRATEGY_PARAMS or {})
    if args.theta is not None:
        params["theta"] = args.theta
    if args.rho is not None:
        params["rho"] = args.rho

    strategy = make_from_name(strategy_name, **(params or {}))
    if strategy is None:
        logger.info("> Stratégie: legacy (SL-only)")
    else:
        logger.info(f"> Stratégie: {strategy_name} params={params}")

    # Instanciation du PositionManager
    om = OrderManager(exchange, ccxt_symbol)
    pm = PositionManager(exchange, ccxt_symbol, om, strategy=strategy)
    pm.load_active()
    
    # Chargement historique
    _df_m15 = compute_indicators(
        fetch_ohlcv(exchange, ccxt_symbol, TIMEFRAMES['M15'], LOOKBACK),
        TIMEFRAMES['M15']
    )
    _df_m5 = compute_indicators(
        fetch_ohlcv(exchange, ccxt_symbol, TIMEFRAMES['M5'], LOOKBACK),
        TIMEFRAMES['M5']
    )
    logger.info("Initialisation des données terminée.")

    # Boucle principale
    while True:
        time.sleep(POLL_INTERVAL)
        size = INVESTMENT_USD * LEVERAGE / _df_m5.close.iloc[-1]
     
        # Mise à jour M5
        new5 = fetch_ohlcv(exchange, ccxt_symbol, TIMEFRAMES['M5'], LOOKBACK)
        if new5.time.iloc[-1] != _df_m5.time.iloc[-1]:
            _df_m5 = compute_indicators(new5, TIMEFRAMES['M5'])
            current_price = _df_m5.close.iloc[-1]
            pm.watchdog(current_price)
            pm.update_trail(_df_m5)
            pm.check_exit()
            sig = generate_signal(_df_m15, _df_m5)
            logger.info(f"Signal reçu : {sig}")

            if not pm.active:
                if sig['long']:
                    size = INVESTMENT_USD * LEVERAGE / _df_m5.close.iloc[-1]
                    pm.open_position('buy', _df_m5.close.iloc[-1], size)
                elif sig['short']:
                    size = INVESTMENT_USD * LEVERAGE / _df_m5.close.iloc[-1]
                    pm.open_position('sell', _df_m5.close.iloc[-1], size)
            else:
                pm.update_trail(_df_m5)

            pm.check_exit()

        # Mise à jour M15
        new15 = fetch_ohlcv(exchange, ccxt_symbol, TIMEFRAMES['M15'], LOOKBACK)
        if new15.time.iloc[-1] != _df_m15.time.iloc[-1]:
            _df_m15 = compute_indicators(new15, TIMEFRAMES['M15'])


if __name__ == "__main__":
    main()
