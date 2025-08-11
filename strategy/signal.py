import pandas as pd

def generate_signal(df_m15: pd.DataFrame, df_m5: pd.DataFrame) -> dict:
    """
    Analyse les indicateurs M15 et M5 pour générer un signal de trading.

    Args:
        df_m15: DataFrame issu de compute_indicators pour la bougie 15m.
        df_m5:  DataFrame issu de compute_indicators pour la bougie 5m.

    Returns:
        dict contenant :
          - 'long': True si condition d'achat validée
          - 'short': True si condition de vente validée
          - 'mom': 'up'/'down'/'neutral' indiquant la tendance M15
          - 'cross': 1/-1/0 selon le croisement EMA9/EMA21 sur M5
          - 'vol_ok': bool, vrai si le volume > SMA5 du volume sur M5
          - 'rsi': valeur de RSI7 sur la dernière bougie M5
    """
    # ----- 1. Momentum M15 -----
    last15 = df_m15.iloc[-1]
    if last15.EMA21 > last15.EMA50:
        mom = 'up'
    elif last15.EMA21 < last15.EMA50:
        mom = 'down'
    else:
        mom = 'neutral'

    # ----- 2. Croisement EMA sur M5 -----
    prev2, prev1, last5 = df_m5.iloc[-3], df_m5.iloc[-2], df_m5.iloc[-1]
    cross = 0
    # croisement haussier
    if ((last5.EMA9 > last5.EMA21 and prev1.EMA9 <= prev1.EMA21) or
        (last5.EMA9 > last5.EMA21 and prev2.EMA9 <= prev2.EMA21)):
        cross = 1
    # croisement baissier
    elif ((last5.EMA9 < last5.EMA21 and prev1.EMA9 >= prev1.EMA21) or
          (last5.EMA9 < last5.EMA21 and prev2.EMA9 >= prev2.EMA21)):
        cross = -1

    # ----- 3. Volume & RSI sur M5 -----
    vol_ok = last5.volume > last5.Vol_SMA5
    rsi7   = last5.RSI7
    rsi_ok_long  = rsi7 > 30
    rsi_ok_short = rsi7 < 70

    # ----- 4. Conditions de signal -----
    long_signal  = (mom == 'up'   and cross == 1  and rsi_ok_long)
    short_signal = (mom == 'down' and cross == -1  and rsi_ok_short)

    return {
        'long': long_signal,
        'short': short_signal,
        'mom': mom,
        'cross': cross,
        'vol_ok': vol_ok,
        'rsi': rsi7,
    }
