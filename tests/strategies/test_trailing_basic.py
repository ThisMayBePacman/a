import math
import pandas as pd  # juste pour rester homogène avec le projet (pas utilisé ici)
from risk.strategies.base import StrategyContext, PositionSnapshot
from risk.strategies.config import TrailingSLOnlyConfig, TrailingSLAndTPConfig
from risk.strategies.registry import make_strategy

def snapshot_long(entry=100.0, price=110.0, sl=None, tp=None, tp0=120.0, qty=1.0, dist=5.0):
    return PositionSnapshot(
        entry_price=entry,
        current_price=price,
        qty_open=qty,
        qty_remaining=qty,
        sl_current=sl,
        tp_current=tp,
        tp_initial=tp0,
        trail_dist=dist,
    )

def snapshot_short(entry=100.0, price=90.0, sl=None, tp=None, tp0=80.0, qty=1.0, dist=5.0):
    return PositionSnapshot(
        entry_price=entry,
        current_price=price,
        qty_open=qty,
        qty_remaining=qty,
        sl_current=sl,
        tp_current=tp,
        tp_initial=tp0,
        trail_dist=dist,
    )

def ctx(side="buy", tick=0.05):
    from typing import Literal
    return StrategyContext(symbol="BTC/USDT", side=side, tick_size=tick)

def test_trailing_sl_only_monotonic_long():
    strat = make_strategy(TrailingSLOnlyConfig())
    s1 = snapshot_long(price=110.0, sl=None, dist=5.0)     # SL cible ≈ 105
    d1 = strat.compute_targets(s1, ctx("buy"))
    s2 = snapshot_long(price=115.0, sl=d1.sl_price, dist=5.0)  # SL cible ≈ 110
    d2 = strat.compute_targets(s2, ctx("buy"))
    assert d2.sl_price >= d1.sl_price  # monotonicité

def test_trailing_sl_only_keeps_tp():
    strat = make_strategy(TrailingSLOnlyConfig())
    s = snapshot_long(price=112.0, sl=None, tp=120.0, tp0=120.0, dist=5.0)
    d = strat.compute_targets(s, ctx("buy"))
    assert math.isclose(d.tp_price, 120.0, rel_tol=0, abs_tol=1e-9)

def test_trailing_and_tp_no_bump_before_threshold_long():
    strat = make_strategy(TrailingSLAndTPConfig(theta=0.5, rho=1.0))
    # entry=100, tp0=120 -> seuil θ=0.5 => SL_threshold=110
    # prix=114, dist=5 => SL_new≈109.95 arrondi up->110.0 => pile au seuil => pas de bump (bump déclenché si >= seuil, mais  tp_current + ρ*(110-110)=tp_current)
    s = snapshot_long(price=114.0, sl=None, tp=120.0, tp0=120.0, dist=5.0)
    d = strat.compute_targets(s, ctx("buy"))
    assert d.tp_price >= 120.0  # au moins le TP courant
    assert d.tp_price == 120.0  # pas d’augmentation effective

def test_trailing_and_tp_bump_long_after_threshold():
    strat = make_strategy(TrailingSLAndTPConfig(theta=0.5, rho=1.0))
    # entry=100, tp0=120 -> seuil=110
    # prix=116, dist=5 => SL_new≈111 -> bump = 1.0 -> TP passe de 120 à 121
    s = snapshot_long(price=116.0, sl=None, tp=120.0, tp0=120.0, dist=5.0)
    d = strat.compute_targets(s, ctx("buy"))
    assert d.sl_price >= 111.0 - 1e-9
    assert d.tp_price >= 121.0 - 1e-9

def test_trailing_and_tp_bump_allows_partial_fills_remaining_tp_up():
    strat = make_strategy(TrailingSLAndTPConfig(theta=0.5, rho=1.0))
    # Suppose qu'on a déjà partiellement exécuté le TP restant, mais on autorise la hausse du TP restant
    s = snapshot_long(price=118.0, sl=112.0, tp=122.0, tp0=120.0, dist=5.0)
    d = strat.compute_targets(s, ctx("buy"))
    assert d.tp_price >= 122.0  # jamais en dessous
    # Selon la distance, on attend un bump supplémentaire
    assert d.tp_price > 122.0

def test_trailing_and_tp_short_mirror():
    strat = make_strategy(TrailingSLAndTPConfig(theta=0.5, rho=1.0))
    # short: entry=100, tp0=80 -> threshold = entry - 0.5*(entry - tp0) = 90
    # prix=84, dist=5 => SL_new ~ 79 -> <= threshold -> bump TP (vers le bas) d'au moins (90-79)=11
    s = snapshot_short(price=84.0, sl=None, tp=80.0, tp0=80.0, dist=5.0)
    d = strat.compute_targets(s, ctx("sell"))
    assert d.sl_price <= 79.05  # arrondi down au tick 0.05
    assert d.tp_price <= 69.0   # 80 - 11 = 69 (ou mieux), avec alignement tick

def test_idempotent_same_inputs():
    strat = make_strategy(TrailingSLAndTPConfig(theta=0.5, rho=1.0))
    s = snapshot_long(price=116.0, sl=None, tp=120.0, tp0=120.0, dist=5.0)
    d1 = strat.compute_targets(s, ctx("buy"))
    d2 = strat.compute_targets(s, ctx("buy"))
    assert d1 == d2
