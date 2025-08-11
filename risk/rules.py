# path: risk/rules.py
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable, Dict, TypedDict

if TYPE_CHECKING:
    # Import uniquement pour le typage (évite les cycles runtime)
    from execution.position_manager import PositionManager

logger = logging.getLogger(__name__)


class Rule(TypedDict):
    """Règle de risque typée pour mypy."""
    condition: Callable[["PositionManager", float], bool]
    action: Callable[["PositionManager"], None]


def _cond_sl(pm: "PositionManager", price: float) -> bool:
    state = pm.active
    if not state:
        return False
    side = state.get("side")
    sl = float(state.get("current_sl_price", 0.0))
    if side == "buy":
        return price <= sl
    if side == "sell":
        return price >= sl
    return False


def _act_sl(pm: "PositionManager") -> None:
    pm._emergency_exit("sl_breach")


def _cond_tp(pm: "PositionManager", price: float) -> bool:
    state = pm.active
    if not state:
        return False
    side = state.get("side")
    tp = float(state.get("tp_price", 0.0))
    if side == "buy":
        return price >= tp
    if side == "sell":
        return price <= tp
    return False


def _act_tp(pm: "PositionManager") -> None:
    # Comportement volontairement non destructif (log only)
    logger.info("TP level breached.")


def _cond_drawdown(pm: "PositionManager", price: float) -> bool:
    # Placeholder: la condition réelle peut être injectée/monkeypatchée en tests
    return False


def _act_drawdown(pm: "PositionManager") -> None:
    pm._handle_drawdown()


# Dictionnaire de règles exporté et typé
RULES: Dict[str, Rule] = {
    "sl_breach": {"condition": _cond_sl, "action": _act_sl},
    "tp_breach": {"condition": _cond_tp, "action": _act_tp},
    "drawdown": {"condition": _cond_drawdown, "action": _act_drawdown},
}
