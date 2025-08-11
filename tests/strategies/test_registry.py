import pytest
from risk.strategies.registry import make_strategy
from risk.strategies.trailing import TrailingSLOnlyConfig, TrailingSLAndTPConfig

def test_make_strategy_by_key():
    from risk.strategies.trailing import TrailingSLOnly
    s = make_strategy("trailing_sl_only")
    assert isinstance(s, TrailingSLOnly)

def test_make_strategy_with_params():
    from risk.strategies.trailing import TrailingSLAndTP
    s = make_strategy("trailing_sl_and_tp", theta=0.5, rho=1.0)
    assert isinstance(s, TrailingSLAndTP)
    assert pytest.approx(s.theta) == 0.5
    assert pytest.approx(s.rho) == 1.0

def test_make_strategy_with_config_obj():
    from risk.strategies.trailing import TrailingSLAndTP
    cfg = TrailingSLAndTPConfig(theta=0.5, rho=1.0)
    s = make_strategy(cfg)
    assert isinstance(s, TrailingSLAndTP)
    assert pytest.approx(s.theta) == 0.5
    assert pytest.approx(s.rho) == 1.0

def test_make_strategy_unknown_key():
    with pytest.raises(ValueError):
        make_strategy("does_not_exist")
