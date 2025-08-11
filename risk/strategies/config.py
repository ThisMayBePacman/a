from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

StrategyName = Literal["trailing_sl_only", "trailing_sl_and_tp"]

@dataclass(frozen=True)
class TrailingSLOnlyConfig:
    name: Literal["trailing_sl_only"] = "trailing_sl_only"

@dataclass(frozen=True)
class TrailingSLAndTPConfig:
    name: Literal["trailing_sl_and_tp"] = "trailing_sl_and_tp"
    theta: float = 0.5   # seuil: fraction de (TP0 - entry) à partir de laquelle on peut bumper le TP
    rho: float = 1.0     # intensité du bump (gain ajouté = rho * (SL_new - SL_threshold))

StrategyConfig = TrailingSLOnlyConfig | TrailingSLAndTPConfig
