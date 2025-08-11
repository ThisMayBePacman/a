# path: tests/test_price_utils_extra.py
import pytest

from utils.price_utils import align_price


def test_align_price_down_and_up():
    # Tick 0.05
    assert align_price(100.03, 0.05, mode="down") == 100.0
    assert align_price(100.03, 0.05, mode="up") == 100.05


def test_align_price_precision_small_ticks():
    assert align_price(1.23456, 0.001, mode="down") == 1.234
    assert align_price(1.23456, 0.001, mode="up") == 1.235


def test_align_price_invalid_mode_raises():
    with pytest.raises(ValueError):
        align_price(100.0, 0.5, mode="invalid")  # type: ignore[arg-type]


def test_align_price_zero_tick_raises():
    with pytest.raises(ValueError):
        align_price(100.0, 0.0, mode="down")
