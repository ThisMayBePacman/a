# indicators/compute.py
import pandas_ta as ta
import pandas as pd

def compute_indicators(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """
    Calcule les indicateurs techniques sur un DataFrame OHLCV pour une timeframe donnée.
    """
    df = df.copy().set_index('time')
    if timeframe == '15m':
        df['EMA21'] = ta.ema(df['close'], length=21)
        df['EMA50'] = ta.ema(df['close'], length=50)
        df['RSI14'] = ta.rsi(df['close'], length=14)
    else:
        df['EMA9']     = ta.ema(df['close'], length=9)
        df['EMA21']    = ta.ema(df['close'], length=21)
        df['RSI7']     = ta.rsi(df['close'], length=7)
        df['Vol_SMA5'] = df['volume'].rolling(window=5, min_periods=1).mean()
        df['ATR14']    = ta.atr(df['high'], df['low'], df['close'], length=14)
    return df.reset_index()