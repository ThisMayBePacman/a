from indicators.compute import compute_indicators
from data.fetcher import fetch_ohlcv
from utils.price_utils import align_price
from data.fetcher import create_exchange, fetch_ohlcv, resolve_symbol
# Constants (import or define as needed)
TF_M5 = "5m"
LOOKBACK = 100

def _get_tick_size(exchange, symbol) -> float:
    """
    Essaie de déterminer le tick size depuis les métadonnées CCXT.
    Fallback: utilise la précision décimale si pas de tick explicite.
    """
    exchange.load_markets()
    m = exchange.market(symbol)
    # 1) Tick size explicite (souvent présent sur les dérivés)
    tick = (
        (m.get("info") or {}).get("tickSize")
        or m.get("tickSize")
    )
    if tick is not None:
        return float(tick)
    # 2) Précision décimale -> tick = 10^-precision
    prec = (m.get("precision") or {}).get("price")
    if isinstance(prec, int):
        return 10 ** (-prec)
    # 3) Dernier recours : limite price.step si dispo
    step = (((m.get("limits") or {}).get("price") or {}).get("step"))
    if step is not None:
        return float(step)
    raise ValueError(f"Impossible de déterminer le tick size pour {symbol}")
 
def calculate_initial_sl_tp(exchange, symbol, entry_price: float, side: str, atr_multiplier: float = 1.5) -> dict:
    """
    Calcule les prix de Stop Loss (SL) et Take Profit (TP) initiaux
    en fonction de l'ATR14 du timeframe 5m.

    :param entry_price: prix d'entrée
    :param side: 'buy' ou 'sell'
    :param atr_multiplier: multiple de l'ATR pour la distance du SL
    :return: dict { 'sl_price': float, 'tp_price': float, 'trail_dist': float }
    """
    # 1. Récupérer OHLCV M5 et calculer ATR14
    df5 = fetch_ohlcv(exchange, symbol, TF_M5, LOOKBACK)
    df5 = compute_indicators(df5, TF_M5)
    atr = float(df5.iloc[-1].ATR14)

    # 2. Distance de trailing = atr * multiplier
    trail_dist = atr * atr_multiplier

    # 3. Calcul des prix
    if side == 'buy':
        sl_raw = entry_price - trail_dist
        tp_raw = entry_price + 2 * trail_dist
    else:
        sl_raw = entry_price + trail_dist
        tp_raw = entry_price - 2 * trail_dist

    # 4. Alignement sur le tick
    tick = _get_tick_size(exchange, symbol)
    # Pour un achat : SL arrondi vers le BAS, TP vers le HAUT (inverse pour une vente)
    if side == "buy":
        sl_price = align_price(sl_raw, tick, mode="down")
        tp_price = align_price(tp_raw, tick, mode="up")
    else:
        sl_price = align_price(sl_raw, tick, mode="up")
        tp_price = align_price(tp_raw, tick, mode="down")
    return { 'sl_price': sl_price, 'tp_price': tp_price, 'trail_dist': trail_dist }


def place_sl_tp_orders(exchange, symbol, side: str, size: float, sl_price: float, tp_price: float) -> dict:
    """
    Passe deux ordres : Stop Limit pour SL et Limit pour TP, en mode reduceOnly.

    :return: ids dict { 'tp': ..., 'sl': ... }
    """
    reduce_side = 'sell' if side == 'buy' else 'buy'

    # Création de l'ordre TP
    tp_order = exchange.create_order(
        symbol, 
        'limit', 
        reduce_side, 
        size, 
        tp_price, 
        { 'reduceOnly': True }
    )

    # Création de l'ordre SL (stop limit)
    sl_order = exchange.create_order(
        symbol,
        'limit',
        reduce_side,
        size,
        sl_price,
        { 'stopPrice': sl_price, 'reduceOnly': True }
    )

    return { 'tp': tp_order['id'], 'sl': sl_order['id'] }
