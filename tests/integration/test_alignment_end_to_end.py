# path: tests/integration/test_alignment_end_to_end.py
import math
from typing import Any, Dict

from execution.position_manager import PositionManager
from utils.price_utils import align_price


def _is_multiple(x: float, tick: float, rel: float = 1e-9) -> bool:
    q = x / tick
    return math.isclose(q, round(q), rel_tol=rel, abs_tol=rel)


def test_prices_aligned_to_tick_end_to_end(dummy_exchange, order_manager, monkeypatch):
    # Fixe un tick tricky et aligne partout
    monkeypatch.setattr("risk.sl_tp.TICK_SIZE", 0.05, raising=False)
    monkeypatch.setattr("execution.position_manager.TICK_SIZE", 0.05, raising=False)

    def dummy_calc(exchange, symbol, entry_price, side):
        from utils.price_utils import align_price
        trail = max(0.5, entry_price * 0.01)
        if side == "buy":
            sl = align_price(entry_price - trail, 0.05, mode="down")
            tp = align_price(entry_price + 2 * trail, 0.05, mode="up")
        else:
            sl = align_price(entry_price + trail, 0.05, mode="up")
            tp = align_price(entry_price - 2 * trail, 0.05, mode="down")
        return {"sl_price": sl, "tp_price": tp, "trail_dist": abs(entry_price - sl)}

    # ⚠️ Patch BOTH places
    monkeypatch.setattr("risk.sl_tp.calculate_initial_sl_tp", dummy_calc, raising=False)
    monkeypatch.setattr("execution.position_manager.calculate_initial_sl_tp", dummy_calc, raising=False)
    pm = PositionManager(dummy_exchange, "BTC/USDT", order_manager)
    pm.open_position("buy", entry_price=100.03, size=1.0)
    assert pm.active is not None
    assert _is_multiple(pm.active["current_sl_price"], 0.05)
    assert _is_multiple(pm.active["tp_price"], 0.05)
