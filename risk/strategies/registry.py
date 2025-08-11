from __future__ import annotations
from .config import StrategyConfig, TrailingSLOnlyConfig, TrailingSLAndTPConfig
from .trailing import TrailingSLOnly, TrailingSLAndTP, TrailingSLOnlyConfig, TrailingSLAndTPConfig
from .base import TrailingStrategy

def make_strategy(cfg):
    if isinstance(cfg, TrailingSLOnlyConfig) or cfg == "trailing_sl_only":
        return TrailingSLOnly()
    if isinstance(cfg, TrailingSLAndTPConfig) or cfg == "trailing_sl_and_tp":
        if isinstance(cfg, TrailingSLAndTPConfig):
            return TrailingSLAndTP(theta=cfg.theta, rho=cfg.rho)
        return TrailingSLAndTP()
    raise ValueError(f"Unknown strategy config: {cfg!r}")

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