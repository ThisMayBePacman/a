# path: tests/integration/test_alignment_end_to_end.py
import math

from execution.position_manager import PositionManager


def _is_multiple(x: float, tick: float, rel: float = 1e-9) -> bool:
    q = x / tick
    return math.isclose(q, round(q), rel_tol=rel, abs_tol=rel)


def test_prices_aligned_to_tick_end_to_end(dummy_exchange, order_manager, monkeypatch):
    # Fixe un tick "difficile" et aligne partout (sl_tp + position_manager)
    monkeypatch.setattr("risk.sl_tp.TICK_SIZE", 0.05, raising=False)
    monkeypatch.setattr("execution.position_manager.TICK_SIZE", 0.05, raising=False)

    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    pm.open_position("buy", entry_price=100.03, size=1.0)
    assert pm.active is not None
    assert _is_multiple(pm.active["current_sl_price"], 0.05)
    assert _is_multiple(pm.active["tp_price"], 0.05)
