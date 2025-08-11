# utils/price_utils.py
import math
from decimal import Decimal, getcontext, ROUND_FLOOR, ROUND_CEILING, ROUND_HALF_UP

from typing import Literal
getcontext().prec = 34
def compute_size(investment_usd, leverage, price):
    """Calcule la taille de position."""
    return investment_usd * leverage / price

def align_price(p: float, tick: float, mode: Literal["down", "up"]) -> float:
    if tick <= 0:
        raise ValueError("tick must be > 0")
    if mode not in ("down", "up"):
        raise ValueError("mode must be 'down' or 'up'")

    step = Decimal(str(tick))
    d = Decimal(str(p))

    q = d / step
    q_floor = q.to_integral_value(rounding=ROUND_FLOOR)
    q_ceil = q_floor if q == q_floor else q_floor + 1
    rem = q - q_floor  # in [0,1)

    # Epsilon absolue max(1e-12, tick*5e-7) convertie en unités de tick
    eps_abs = max(1e-12, float(step) * 5e-7)
    eps_units = Decimal(str(eps_abs)) / step  # très petit, ~1e-6 de tick

    if mode == "down":
        # si on est quasi au multiple supérieur, on accepte de « snap up » seulement
        # si l'écart est < eps (sinon on reste floor)
        n = q_ceil if (Decimal(1) - rem) <= eps_units else q_floor
    else:  # mode == "up"
        # si on est quasi au multiple inférieur, on « snap down » seulement si < eps
        # (sinon on respecte la direction et on prend ceil)
        n = q_floor if rem <= eps_units else q_ceil

    res = (n * step).quantize(step, rounding=ROUND_HALF_UP)
    return float(res)