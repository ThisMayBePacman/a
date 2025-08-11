# main.py
import logging
import time
from data.fetcher import create_exchange, fetch_ohlcv, resolve_symbol
from indicators.compute import compute_indicators
from strategy.signal import generate_signal
# plus besoin de place_market_order direct
from execution.order_manager import OrderManager
from execution.position_manager import PositionManager
from config import SYMBOL, TIMEFRAMES, LOOKBACK, POLL_INTERVAL, INVESTMENT_USD, LEVERAGE
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
def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--strategy", choices=["trailing_sl_only", "trailing_sl_and_tp"], default=STRATEGY)
    p.add_argument("--theta", type=float, default=None)
    p.add_argument("--rho", type=float, default=None)
    return p.parse_args()
def main():
    # Création du client et résolution du symbole
    exchange = create_exchange()
    ccxt_symbol = resolve_symbol(exchange, SYMBOL)
    logger.info(f"> Utilisation du ticker CCXT : {ccxt_symbol}")

    # 🔹 Instanciation (optionnelle) de la stratégie depuis la config
    strategy = make_from_name(STRATEGY, STRATEGY_PARAMS)
    if strategy is None:
        logger.info("> Stratégie: legacy (SL-only)")
    else:
        logger.info(f"> Stratégie: {STRATEGY} params={STRATEGY_PARAMS}")

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
