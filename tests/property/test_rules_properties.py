# path: tests/property/test_rules_properties.py
from hypothesis import given, strategies as st
from risk.rules import RULES

class FakeState:
    def __init__(self, side=None, sl=None, tp=None, entry=None):
        self.active = {} if side or sl or tp or entry else None
        if side is not None:
            self.active['side'] = side
        if sl is not None:
            self.active['current_sl_price'] = sl
        if tp is not None:
            self.active['tp_price'] = tp
        if entry is not None:
            self.active['entry_price'] = entry
    @property
    def tp_price(self):
        return self.active.get('tp_price') if self.active else None
    @property
    def entry_price(self):
        return self.active.get('entry_price') if self.active else None

@given(side=st.sampled_from(['buy','sell']),
       sl=st.floats(min_value=0.001, max_value=1e6),
       price=st.floats(min_value=0.0, max_value=1e6))
def test_sl_breach_condition(side, sl, price):
    state = FakeState(side=side, sl=sl)
    result = RULES['sl_breach']['condition'](state, price)
    expected = False
    if side == 'buy':
        expected = price <= sl
    elif side == 'sell':
        expected = price >= sl
    assert result == expected

@given(side=st.sampled_from(['buy','sell']),
       tp=st.floats(min_value=0.001, max_value=1e6),
       price=st.floats(min_value=0.0, max_value=1e6))
def test_tp_breach_condition(side, tp, price):
    state = FakeState(side=side, tp=tp)
    result = RULES['tp_breach']['condition'](state, price)
    expected = False
    if side == 'buy':
        expected = price >= tp
    elif side == 'sell':
        expected = price <= tp
    assert result == expected

@given(entry=st.floats(min_value=0.01, max_value=1e6),
       price=st.floats(min_value=0.0, max_value=1e6))
def test_max_drawdown_condition(entry, price):
    state = FakeState(entry=entry)
    result = RULES['max_drawdown']['condition'](state, price)
    # Condition est vraie si price < 0.98 * entry (baisse > 2%)
    expected = price < 0.98 * entry
    assert result == expected
