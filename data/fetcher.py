# data/fetcher.py
import ccxt
import pandas as pd
from config import API_KEY, API_SECRET, SYMBOL

def create_exchange():
    ex = ccxt.krakenfutures({
        'apiKey': API_KEY,
        'secret': API_SECRET,
        'enableRateLimit': True,
    })
    ex.load_markets()
    return ex


def resolve_symbol(exchange, symbol_id):
    """
    Trouve le ticker CCXT correspondant à un ID interne (p.ex. "PF_ETHUSD").
    Raise ValueError si introuvable.
    """
    symbol = next(
        (s for s, m in exchange.markets.items()
         if m.get('id') == symbol_id),
        None
    )
    if symbol is None:
        raise ValueError(f"Symbole CCXT introuvable pour ID '{symbol_id}'")
    return symbol


def fetch_ohlcv(exchange, symbol, timeframe, lookback):
    since = exchange.milliseconds() - lookback * exchange.parse_timeframe(timeframe) * 1000
    raw = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=lookback)
    df = pd.DataFrame(raw, columns=["time","open","high","low","close","volume"])
    df['time'] = pd.to_datetime(df['time'], unit='ms')
    return df