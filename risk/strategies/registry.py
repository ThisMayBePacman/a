from __future__ import annotations
from .config import StrategyConfig, TrailingSLOnlyConfig, TrailingSLAndTPConfig
from .trailing import TrailingSLOnly, TrailingSLAndTP
from .base import TrailingStrategy

def make_strategy(cfg: StrategyConfig) -> TrailingStrategy:
    if isinstance(cfg, TrailingSLOnlyConfig):
        return TrailingSLOnly()
    if isinstance(cfg, TrailingSLAndTPConfig):
        return TrailingSLAndTP(theta=cfg.theta, rho=cfg.rho)
    raise ValueError(f"Unsupported strategy config: {cfg}")
