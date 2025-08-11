# path: tests/test_sl_tp.py
import pandas as pd
import pytest
from risk import sl_tp


def test_calculate_initial_sl_tp_buy(monkeypatch):
    # Monkeypatch _get_tick_size to avoid real exchange calls
    monkeypatch.setattr(sl_tp, "_get_tick_size", lambda exchange, symbol: 0.5)
    # Monkeypatch fetch_ohlcv & compute_indicators to provide deterministic ATR
    data = pd.DataFrame({"time": range(100), "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1})
    monkeypatch.setattr(sl_tp, "fetch_ohlcv", lambda exchange, symbol, tf, lb: data)
    monkeypatch.setattr(sl_tp, "compute_indicators", lambda df, tf: df.assign(ATR14=10.0))
    # Calculate SL/TP for buy
    res = sl_tp.calculate_initial_sl_tp(None, "BTC/USDT", entry_price=100.3, side="buy")
    # ATR14=10 -> trail_dist=15; expected raw SL=85.3, TP=130.3, tick=0.5 -> SL down to 85.0, TP up to 130.5
    assert pytest.approx(res["sl_price"], rel=1e-6) == 85.0
    assert pytest.approx(res["tp_price"], rel=1e-6) == 130.5
    assert pytest.approx(res["trail_dist"], rel=1e-6) == 15.0


def test_calculate_initial_sl_tp_sell(monkeypatch):
    monkeypatch.setattr(sl_tp, "_get_tick_size", lambda exchange, symbol: 0.5)
    monkeypatch.setattr(sl_tp, "fetch_ohlcv", lambda exchange, symbol, tf, lb: pd.DataFrame({"ATR14": [10.0]}))
    monkeypatch.setattr(sl_tp, "compute_indicators", lambda df, tf: df.assign(ATR14=df["ATR14"]))
    res = sl_tp.calculate_initial_sl_tp(None, "BTC/USDT", entry_price=100.3, side="sell")
    # ATR14=10 -> trail_dist=15; expected raw SL=115.3, TP=70.3, tick=0.5 -> SL up to 115.5, TP down to 70.0
    assert pytest.approx(res["sl_price"], rel=1e-6) == 115.5
    assert pytest.approx(res["tp_price"], rel=1e-6) == 70.0
    assert pytest.approx(res["trail_dist"], rel=1e-6) == 15.0


def test_place_sl_tp_orders(monkeypatch, dummy_exchange):
    # Dummy exchange already provided by fixture
    res = sl_tp.place_sl_tp_orders(dummy_exchange, "BTC/USDT", side="buy", size=2.0, sl_price=90.0, tp_price=110.0)
    # It should return IDs of created orders
    assert set(res.keys()) == {"tp", "sl"}
    tp_id, sl_id = res["tp"], res["sl"]
    # Both orders should be in dummy_exchange and marked reduceOnly
    tp_order = dummy_exchange.orders[tp_id]
    sl_order = dummy_exchange.orders[sl_id]
    assert tp_order["params"].get("reduceOnly") is True
    assert sl_order["params"].get("stopPrice") == 90.0 and sl_order["params"].get("reduceOnly") is True


def test_get_tick_size_from_info():
    class FX:
        def load_markets(self): ...
        def market(self, symbol):
            return {"info": {"tickSize": "0.01"}}

    assert sl_tp._get_tick_size(FX(), "BTC/USDT") == 0.01


def test_get_tick_size_from_top_level_tickSize():
    class FX:
        def load_markets(self): ...
        def market(self, symbol):
            return {"tickSize": 0.5}

    assert sl_tp._get_tick_size(FX(), "BTC/USDT") == 0.5


def test_get_tick_size_from_precision_price():
    class FX:
        def load_markets(self): ...
        def market(self, symbol):
            return {"precision": {"price": 3}}

    assert sl_tp._get_tick_size(FX(), "BTC/USDT") == 10 ** -3


def test_get_tick_size_from_limits_step():
    class FX:
        def load_markets(self): ...
        def market(self, symbol):
            return {"limits": {"price": {"step": "0.25"}}}

    assert sl_tp._get_tick_size(FX(), "BTC/USDT") == 0.25


def test_get_tick_size_raises_when_missing():
    class FX:
        def load_markets(self): ...
        def market(self, symbol):
            return {}

    with pytest.raises(ValueError):
        sl_tp._get_tick_size(FX(), "BTC/USDT")
