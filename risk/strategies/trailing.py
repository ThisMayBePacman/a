from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from .base import TrailingStrategy, StrategyContext, PositionSnapshot, DesiredState
from utils.price_utils import align_price

@dataclass
class TrailingSLOnly(TrailingStrategy):
    """
    Trailing stop simple: on remonte (long) / on abaisse (short) le SL avec une distance fixe.
    Le TP n'est jamais modifié ici.
    """

    def compute_targets(self, snap: PositionSnapshot, ctx: StrategyContext) -> DesiredState:
        side = ctx.side
        price = snap.current_price
        dist = snap.trail_dist

        if side == "buy":
            sl_target = max(snap.sl_current or (snap.entry_price - dist), price - dist)
            sl_target = align_price(sl_target, ctx.tick_size, mode="up")
            tp_target = snap.tp_current or snap.tp_initial
        else:
            sl_target = min(snap.sl_current or (snap.entry_price + dist), price + dist)
            sl_target = align_price(sl_target, ctx.tick_size, mode="down")
            tp_target = snap.tp_current or snap.tp_initial

        return DesiredState(
            sl_price=sl_target,
            tp_price=tp_target,
            debug={"kind": "TrailingSLOnly"}
        )

    def on_fill(self, snap, fill) -> None:
        # Pas d’état interne à maintenir dans ce squelette
        return

@dataclass
class TrailingSLAndTP(TrailingStrategy):
    """
    Trailing SL + bump éventuel du TP:
      - on trail le SL comme ci-dessus;
      - si SL_new dépasse le seuil θ entre entry et TP0, on augmente le TP restant.

    Formule de bump (long) :
      SL_threshold = entry + θ*(TP0 - entry)
      si SL_new >= SL_threshold:
          TP_new_candidate = TP_current_or_initial + ρ * (SL_new - SL_threshold)
          TP_new = max(TP_current_or_initial, TP_new_candidate)
    Miroir pour 'sell'.
    """
    theta: float = 0.5
    rho: float = 1.0

    def compute_targets(self, snap: PositionSnapshot, ctx: StrategyContext) -> DesiredState:
        if snap.tp_initial is None:
            # Sans TP initial de référence, on se comporte comme un trailing simple
            return TrailingSLOnly().compute_targets(snap, ctx)

        side = ctx.side
        price = snap.current_price
        dist = snap.trail_dist
        entry = snap.entry_price
        tp0 = snap.tp_initial
        tp_current = snap.tp_current or tp0
        if side == "buy":
            sl_cand = align_price(price - dist, tick, mode="down")
            if current_sl is not None:
                sl_cand = max(sl_cand, current_sl)  # monotone ↑ for long

            threshold = entry + self.theta * (tp0 - entry)
            tp_next = current_tp
            if sl_cand >= threshold:
                bump = self.rho * (sl_cand - threshold)
                tp_next = align_price(current_tp + bump, tick, mode="up")

            return DesiredState(sl_price=sl_cand, tp_price=tp_next, debug=dbg)

        else:  # side == "sell"
            # FIX: trail SL below price for short (+ mirror threshold/bump direction)
            sl_cand = align_price(price - dist, tick, mode="down")
            if current_sl is not None:
                sl_cand = min(sl_cand, current_sl)  # monotone ↓ for short

            threshold = entry - self.theta * (entry - tp0)  # e.g., 90 when entry=100, tp0=80, θ=0.5
            tp_next = current_tp
            if sl_cand <= threshold:
                bump = self.rho * (threshold - sl_cand)
                tp_next = align_price(current_tp - bump, tick, mode="down")

            return DesiredState(sl_price=sl_cand, tp_price=tp_next, debug=dbg)

    def on_fill(self, snap, fill) -> None:
        # Rien à persister ici : la quantité restante/ordres seront lus depuis l’exchange par le PM.
        return
