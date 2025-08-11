# path: tests/property/test_rules_properties.py
from __future__ import annotations

from typing import Dict, Any

from hypothesis import given, settings, strategies as st

from risk.rules import RULES


class FakePM:
    def __init__(self, side: str, sl: float, tp: float):
        self.active: Dict[str, Any] = {"side": side, "current_sl_price": sl, "tp_price": tp}


sides = st.sampled_from(["buy", "sell"])
entries = st.floats(min_value=0.01, max_value=1e6)
prices = st.floats(min_value=0.0, max_value=1e6)


@given(side=sides, entry=entries)
@settings(max_examples=100)
def test_sl_tp_do_not_trigger_simultaneously_when_levels_consistent(side: str, entry: float) -> None:
    """
    Propriété: si SL < TP pour long (et TP < SL pour short),
    il n'existe pas de prix p qui déclenche simultanément SL et TP.
    """
    if side == "buy":
        sl = entry * 0.95
        tp = entry * 1.05
        pm = FakePM("buy", sl, tp)
        for p in (sl * 0.999, entry, tp * 1.001):
            sl_hit = RULES["sl_breach"]["condition"](pm, p)
            tp_hit = RULES["tp_breach"]["condition"](pm, p)
            assert not (sl_hit and tp_hit)
    else:
        sl = entry * 1.05  # SL au-dessus
        tp = entry * 0.95  # TP au-dessous
        pm = FakePM("sell", sl, tp)
        for p in (tp * 0.999, entry, sl * 1.001):
            sl_hit = RULES["sl_breach"]["condition"](pm, p)
            tp_hit = RULES["tp_breach"]["condition"](pm, p)
            assert not (sl_hit and tp_hit)


@given(entry=entries, price=prices)
@settings(max_examples=100)
def test_sl_monotonic_with_price_for_long(entry: float, price: float) -> None:
    """Pour un long: si SL est atteint à un prix p, il reste atteint pour tout prix <= p."""
    sl = entry * 0.9
    pm = FakePM("buy", sl, entry * 1.1)
    p1 = price
    p2 = p1 - abs(entry) * 0.01  # p2 <= p1
    hit1 = RULES["sl_breach"]["condition"](pm, p1)
    hit2 = RULES["sl_breach"]["condition"](pm, p2)
    assert (not hit1) or hit2
