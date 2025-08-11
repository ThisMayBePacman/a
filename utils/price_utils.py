# utils/price_utils.py
import math
from decimal import Decimal, ROUND_FLOOR, ROUND_CEILING, getcontext
from typing import Literal
getcontext().prec = 28
def compute_size(investment_usd, leverage, price):
    """Calcule la taille de position."""
    return investment_usd * leverage / price

def align_price(price: float, tick: float, mode: Literal["down", "up"]) -> float:
    if tick <= 0:
        raise ValueError("tick must be > 0")
    p = Decimal(str(price))
    t = Decimal(str(tick))
    steps = p / t
    if mode == "down":
        k = steps.to_integral_value(rounding=ROUND_FLOOR)
    elif mode == "up":
        k = steps.to_integral_value(rounding=ROUND_CEILING)
    else:
        raise ValueError("mode must be 'down' or 'up'")
    return float(k * t)