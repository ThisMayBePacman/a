# utils/price_utils.py
import math
def compute_size(investment_usd, leverage, price):
    """Calcule la taille de position."""
    return investment_usd * leverage / price

def align_price(price: float, tick_size: float, mode: str = "nearest") -> float:
    """
    Aligne le prix sur le tick_size demandé.
    mode: "up" | "down" | "nearest"
    """
    if tick_size <= 0:
        raise ValueError("tick_size doit être > 0")
    mult = price / tick_size
    if mode == "up":
        return round(math.ceil(mult) * tick_size, 12)
    if mode == "down":
        return round(math.floor(mult) * tick_size, 12)
    return round(round(mult) * tick_size, 12)