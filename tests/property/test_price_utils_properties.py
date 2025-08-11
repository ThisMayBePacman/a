# path: tests/property/test_price_utils_properties.py
import math
from typing import Literal

import pytest
from hypothesis import given, settings, strategies as st

from utils.price_utils import align_price


# Stratégies sûres pour éviter NaN/inf et ticks pathologiques
prices = st.floats(min_value=-1e9, max_value=1e9, allow_nan=False, allow_infinity=False, width=32)
ticks = st.floats(min_value=1e-9, max_value=1e6, allow_nan=False, allow_infinity=False)  # tick > 0
modes = st.sampled_from(["down", "up"])  # on reste sur les 2 modes présents dans la base de tests


def _is_multiple(x: float, tick: float, tol: float = 1e-9) -> bool:
    """Vérifie que x est un multiple de tick (avec tolérance)."""
    if tick == 0:
        return False
    q = x / tick
    nearest = round(q)
    return math.isclose(q, nearest, rel_tol=0.0, abs_tol=tol)


@given(p=prices, t=ticks, mode=modes)
@settings(max_examples=200)
def test_align_price_bounds_and_multiple(p: float, t: float, mode: Literal["down", "up"]) -> None:
    """Bornes respectées et alignement sur un multiple du tick."""
    aligned = align_price(p, t, mode=mode)

    # Aligned est un multiple du tick
    assert _is_multiple(aligned, t)

    # Bornes selon le mode
    if mode == "down":
        assert aligned <= p + 1e-12  # tolérance flottante
        assert (p - aligned) < t + 1e-12
    else:  # mode == "up"
        assert aligned >= p - 1e-12
        assert (aligned - p) < t + 1e-12


@given(p=prices, t=ticks, mode=modes)
@settings(max_examples=200)
def test_align_price_idempotent(p: float, t: float, mode: Literal["down", "up"]) -> None:
    """Idempotence: appliquer deux fois ne change rien."""
    once = align_price(p, t, mode=mode)
    twice = align_price(once, t, mode=mode)
    assert math.isclose(once, twice, rel_tol=0.0, abs_tol=1e-12)


def test_align_price_raises_on_zero_or_negative_tick() -> None:
    with pytest.raises(ValueError):
        align_price(100.0, 0.0, mode="down")
    with pytest.raises(ValueError):
        align_price(100.0, -0.1, mode="up")
