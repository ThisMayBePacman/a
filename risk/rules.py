# path: risk/rules.py
from typing import Callable
import logging

logger = logging.getLogger(__name__)

# Chaque règle est un dict contenant :
# - 'condition': Callable[[state, price], bool] déclenchant l'action quand True
# - 'action': Callable[[state], None] à exécuter en cas de déclenchement

RULES = {
    'sl_breach': {
        'condition': lambda state, price: (
            state.active is not None
            and state.active['side'] == 'buy'
            and price <= state.active['current_sl_price']
        ) or (
            state.active is not None
            and state.active['side'] == 'sell'
            and price >= state.active['current_sl_price']
        ),
        'action': lambda state: state._emergency_exit(reason="SL breach")
    },
    'tp_breach': {
        'condition': lambda state, price: (
            state.active is not None
            and state.tp_price is not None
            and state.active['side'] == 'buy'
            and price >= state.tp_price
        ) or (
            state.active is not None
            and state.tp_price is not None
            and state.active['side'] == 'sell'
            and price <= state.tp_price
        ),
        'action': lambda state: logger.info("TP breach: on laisse le TP limite se remplir")
    },
    'max_drawdown': {
        'condition': lambda state, price: (
            state.active is not None
            and state.entry_price is not None
            and (state.entry_price - price) / state.entry_price > 0.02
        ),
        'action': lambda state: state._handle_drawdown()
    }
}
