# utils/decorators.py
import functools, logging
logger = logging.getLogger(__name__)

def verify_order(fn):
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        order = fn(self, *args, **kwargs)
        # récupération et vérif…
        return order
    return wrapper
