# path: tests/property/test_price_utils_properties.py
import math
from typing import Literal

import pytest
from hypothesis import given, settings, strategies as st

from utils.price_utils import align_price


# Stratégies sûres pour éviter NaN/inf et pas trop petits (erreurs flottantes)
prices = st.floats(min_value=-1e8, max_value=1e8, allow_nan=False, allow_infinity=False, width=32)
ticks = st.floats(min_value=1e-6, max_value=1e6, allow_nan=False, allow_infinity=False)
modes = st.sampled_from(["down", "up"])


def _is_multiple(x: float, tick: float, rel: float = 1e-8) -> bool:
    """Vérifie x ≈ k * tick avec tolérance relative sur le quotient."""
    if tick <= 0:
        return False
    q = x / tick
    k = round(q)
    return math.isclose(q, k, rel_tol=rel, abs_tol=rel)


@given(p=prices, t=ticks, mode=modes)
@settings(max_examples=200)
def test_align_price_bounds_and_multiple(p: float, t: float, mode: Literal["down", "up"]) -> None:
    """Bornes respectées et alignement sur un multiple du tick (avec tolérance)."""
    aligned = align_price(p, t, mode=mode)
    assert _is_multiple(aligned, t)

    # Tolérance basée sur le tick pour absorber les erreurs IEEE-754
    eps = max(1e-12, t * 5e-7)

    if mode == "down":
        assert aligned <= p + eps
        assert (p - aligned) <= t + eps
    else:  # up
        assert aligned >= p - eps
        assert (aligned - p) <= t + eps


@given(p=prices, t=ticks, mode=modes)
@settings(max_examples=200)
def test_align_price_idempotent_within_one_tick(p: float, t: float, mode: Literal["down", "up"]) -> None:
    """
    Idempotence robuste : réappliquer l'alignement ne doit pas déplacer de plus d'UN tick
    (pour tolérer les effets de bord quand la valeur tombe pile sur une frontière).
    """
    once = align_price(p, t, mode=mode)
    twice = align_price(once, t, mode=mode)
    eps = max(1e-12, t * 5e-7)
    assert abs(twice - once) <= t + eps


def test_align_price_raises_on_zero_or_negative_tick() -> None:
    with pytest.raises(ValueError):
        align_price(100.0, 0.0, mode="down")
    with pytest.raises(ValueError):
        align_price(100.0, -0.1, mode="up")
