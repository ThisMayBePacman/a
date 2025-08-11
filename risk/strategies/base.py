from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Literal, Protocol

Side = Literal["buy", "sell"]

@dataclass(frozen=True)
class StrategyContext:
    symbol: str
    side: Side
    tick_size: float = 0.01

@dataclass(frozen=True)
class PositionSnapshot:
    entry_price: float
    current_price: float
    qty_open: float                 # quantité totale ouverte au départ
    qty_remaining: float            # quantité restante (après fills partiels éventuels)
    sl_current: Optional[float]     # SL actuel si déjà posé
    tp_current: Optional[float]     # TP actuel (restant) si déjà posé
    tp_initial: Optional[float]     # TP initial à l’ouverture (référence pour le seuil θ)
    trail_dist: float               # distance de trailing (unité prix)

@dataclass(frozen=True)
class DesiredState:
    sl_price: Optional[float]
    tp_price: Optional[float]       # simple TP (pas de paliers dans ce squelette)
    debug: dict                     # infos pour logs/tests

@dataclass(frozen=True)
class FillEvent:
    price: float
    qty: float

class TrailingStrategy(Protocol):
    def compute_targets(self, snap: PositionSnapshot, ctx: StrategyContext) -> DesiredState: ...
    def on_fill(self, snap: PositionSnapshot, fill: FillEvent) -> None: ...
