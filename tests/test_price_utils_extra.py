# path: tests/test_price_utils_extra.py
import math

from utils.price_utils import align_price


def _is_multiple(x: float, tick: float) -> bool:
    if tick <= 0:
        return False
    q = x / tick
    return math.isclose(q, round(q), rel_tol=1e-8, abs_tol=1e-8)


def test_align_price_down_and_up():
    # Tick 0.05
    assert align_price(100.03, 0.05, mode="down") == 100.0
    assert align_price(100.03, 0.05, mode="up") == 100.05


def test_align_price_precision_small_ticks():
    assert align_price(1.23456, 0.001, mode="down") == 1.234
    assert align_price(1.23456, 0.001, mode="up") == 1.235


def test_align_price_invalid_mode_is_safe():
    """
    Certaines implémentations tolèrent un mode inconnu au lieu de lever.
    On accepte les deux comportements: retour multiple du tick OU ValueError.
    """
    try:
        v = align_price(100.03, 0.05, mode="invalid")  # type: ignore[arg-type]
        assert _is_multiple(v, 0.05)
    except ValueError:
        # Comportement également acceptable
        pass


def test_align_price_zero_tick_raises():
    import pytest
    with pytest.raises(ValueError):
        align_price(100.0, 0.0, mode="down")
