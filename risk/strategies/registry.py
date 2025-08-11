# risk/strategies/registry.py
from __future__ import annotations
from typing import Any

from .trailing import (
    TrailingSLOnly,
    TrailingSLAndTP,
    # Ces deux classes doivent exister dans trailing.py
    TrailingSLOnlyConfig,
    TrailingSLAndTPConfig,
)
def make_from_name(name: str, **kwargs):
    """
    Compat helper pour le CLI: construit une stratégie à partir d'un nom
    (ex: 'trailing_sl_only' ou 'trailing_sl_and_tp') + éventuels kwargs (theta, rho).
    """
    return make_strategy(name, **kwargs)
def make_strategy(cfg_or_name: Any = "trailing_sl_only", **kwargs) -> TrailingSLOnly | TrailingSLAndTP:
    """
    Fabrique une stratégie à partir :
      - d'un objet config (TrailingSLOnlyConfig / TrailingSLAndTPConfig),
      - ou d'un objet 'config-like' avec un attribut .name,
      - ou d'un nom de stratégie (str) + kwargs (theta/rho).
    """
    # Cas 1 — objets config des classes attendues
    try:
        if isinstance(cfg_or_name, TrailingSLOnlyConfig):
            return TrailingSLOnly()
        if isinstance(cfg_or_name, TrailingSLAndTPConfig):
            return TrailingSLAndTP(theta=float(cfg_or_name.theta), rho=float(cfg_or_name.rho))
    except Exception:
        # Si les classes ne sont pas importables pour une raison quelconque,
        # on tombera dans le duck-typing ci-dessous.
        pass

    # Cas 2 — duck-typing d'un objet "config-like"
    name = getattr(cfg_or_name, "name", None)
    if isinstance(name, str):
        name = name.lower()
        if name == "trailing_sl_only":
            return TrailingSLOnly()
        if name == "trailing_sl_and_tp":
            theta = float(getattr(cfg_or_name, "theta", kwargs.get("theta", 0.5)))
            rho = float(getattr(cfg_or_name, "rho", kwargs.get("rho", 1.0)))
            return TrailingSLAndTP(theta=theta, rho=rho)

    # Cas 3 — nom + kwargs
    if isinstance(cfg_or_name, str):
        key = cfg_or_name.lower()
        if key == "trailing_sl_only":
            return TrailingSLOnly()
        if key == "trailing_sl_and_tp":
            theta = float(kwargs.get("theta", 0.5))
            rho = float(kwargs.get("rho", 1.0))
            return TrailingSLAndTP(theta=theta, rho=rho)

    raise ValueError(f"Unknown strategy config/name: {cfg_or_name!r}")
