# utils/price_utils.py
import math
from decimal import Decimal, ROUND_FLOOR, ROUND_CEILING, getcontext
from typing import Literal
getcontext().prec = 28
def compute_size(investment_usd, leverage, price):
    """Calcule la taille de position."""
    return investment_usd * leverage / price

def align_price(p: float, tick: float, mode: Literal["down", "up"]) -> float:
    """
    Aligne p sur le tick en évitant les effets d'escalier liés au float.
    - 'down' : plus petit multiple <= p (à epsilon près)
    - 'up'   : plus grand multiple >= p (à epsilon près)
    Idempotent: align_price(align_price(p)) ne bouge pas de + d'1 tick.
    """
    if tick <= 0:
        raise ValueError("tick must be > 0")
    if mode not in ("down", "up"):
        raise ValueError("mode must be 'down' or 'up'")

    step = Decimal(str(tick))
    d = Decimal(str(p))
    q = d / step  # p en unités de tick

    # même logique d'epsilon que les tests (abs), convertie en unités de tick
    tol_abs = Decimal(str(max(1e-12, tick * 5e-7)))
    tol_units = tol_abs / step

    q_floor = q.to_integral_value(rounding=ROUND_FLOOR)
    rem = q - q_floor  # reste dans [0, 1)

    # Cas "déjà quasi aligné" -> snap sur l'entier le plus proche
    if rem <= tol_units:
        n = q_floor
    elif (Decimal(1) - rem) <= tol_units:
        n = q_floor + 1
    else:
        if mode == "down":
            n = q_floor
        else:  # up
            n = q.to_integral_value(rounding=ROUND_CEILING)

    res = n * step
    return float(res)