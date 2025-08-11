import importlib
import sys
import pytest

def _import_cli():
    mod = importlib.import_module("main")
    parse_args = getattr(mod, "parse_args", None)
    build_strategy_from_flags = getattr(mod, "build_strategy_from_flags", None)
    if parse_args is None or build_strategy_from_flags is None:
        pytest.skip("main.parse_args/build_strategy_from_flags not exposed by main.py")
    return mod, parse_args, build_strategy_from_flags

def test_cli_builds_trailing_sl_and_tp(monkeypatch):
    _, parse_args, build = _import_cli()
    monkeypatch.setattr(sys, "argv", ["prog", "--strategy", "trailing_sl_and_tp", "--theta", "0.5", "--rho", "1.0"])
    args = parse_args()
    strat = build(args)
    from risk.strategies.trailing import TrailingSLAndTP
    assert isinstance(strat, TrailingSLAndTP)
    assert pytest.approx(strat.theta) == 0.5
    assert pytest.approx(strat.rho) == 1.0

def test_cli_defaults_to_sl_only(monkeypatch):
    _, parse_args, build = _import_cli()
    monkeypatch.setattr(sys, "argv", ["prog"])
    args = parse_args()
    strat = build(args)
    from risk.strategies.trailing import TrailingSLOnly
    assert isinstance(strat, TrailingSLOnly)
