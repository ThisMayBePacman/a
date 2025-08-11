# utils/price_utils.py
import math
from decimal import Decimal, ROUND_FLOOR, ROUND_CEILING, getcontext
from typing import Literal
getcontext().prec = 34
def compute_size(investment_usd, leverage, price):
    """Calcule la taille de position."""
    return investment_usd * leverage / price

def align_price(p: float, tick: float, mode: Literal["down", "up"]) -> float:
    """
    Aligne p sur la grille 'tick' en évitant les effets float.
    - 'down' : plus petit multiple <= p (avec zone de snap autour des multiples)
    - 'up'   : plus grand multiple >= p (avec zone de snap)
    Idempotent: un 2e alignement ne bouge pas de > 1 tick.
    """
    if tick <= 0:
        raise ValueError("tick must be > 0")
    if mode not in ("down", "up"):
        raise ValueError("mode must be 'down' or 'up'")

    step = Decimal(str(tick))             # ex: '1e-06'
    d = Decimal(str(p))                   # entrée stabilisée

    q = d / step                          # p en unités de tick
    q_floor = q.to_integral_value(rounding=ROUND_FLOOR)
    rem = q - q_floor                     # reste dans [0, 1)

    # Tolérance en "unités de tick" plus large que la dérive float observée (~2e-4 tick)
    # pour "snapper" une valeur quasi-alignée.
    snap_units = Decimal("1e-3")          # 0.001 tick

    # Si déjà quasi sur un multiple → snap au multiple le plus proche
    if rem <= snap_units:
        n = q_floor
    elif (Decimal(1) - rem) <= snap_units:
        n = q_floor + 1
    else:
        # Sinon respect strict de la direction
        if mode == "down":
            n = q_floor
        else:  # 'up'
            n = q.to_integral_value(rounding=ROUND_CEILING)

    # Résultat exactement sur la grille, puis conversion float
    res = (n * step).quantize(step, rounding=ROUND_HALF_UP)
    return float(res)