from __future__ import annotations
from .config import StrategyConfig, TrailingSLOnlyConfig, TrailingSLAndTPConfig
from .trailing import TrailingSLOnly, TrailingSLAndTP, TrailingSLOnlyConfig, TrailingSLAndTPConfig
from .base import TrailingStrategy

def make_strategy(cfg_or_name="trailing_sl_only", **kwargs):
    # Cas 1: objets config
    if isinstance(cfg_or_name, TrailingSLOnlyConfig):
        return TrailingSLOnly()
    if isinstance(cfg_or_name, TrailingSLAndTPConfig):
        return TrailingSLAndTP(theta=cfg_or_name.theta, rho=cfg_or_name.rho)

    # Cas 2: nom + kwargs
    if isinstance(cfg_or_name, str):
        name = cfg_or_name
        if name == "trailing_sl_only":
            return TrailingSLOnly()
        if name == "trailing_sl_and_tp":
            theta = float(kwargs.get("theta", 0.5))
            rho = float(kwargs.get("rho", 1.0))
            return TrailingSLAndTP(theta=theta, rho=rho)

    raise ValueError(f"Unknown strategy config/name: {cfg_or_name!r}")
def make_from_name(name: str | None, params: dict | None = None):
    if not name:
        return None
    params = params or {}
    if name == "trailing_sl_only":
        return TrailingSLOnly()
    if name == "trailing_sl_and_tp":
        return TrailingSLAndTP(
            theta=float(params.get("theta", 0.5)),
            rho=float(params.get("rho", 1.0)),
        )
    raise ValueError(f"Unknown strategy name: {name}")