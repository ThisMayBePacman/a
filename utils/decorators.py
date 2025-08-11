# path: utils/decorators.py
import functools, logging
logger = logging.getLogger(__name__)

def verify_order(fn):
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        try:
            order = fn(self, *args, **kwargs)
        except Exception as e:
            # Log the exception at debug level and propagate
            logger.debug(f"Order function {fn.__name__} raised {e}")
            raise
        # Vérification du résultat de l'ordre
        if order is None or 'id' not in order:
            raise RuntimeError(f"Order {fn.__name__} failed: invalid response {order}")
        status = order.get('status')
        if isinstance(status, str):
            status_lower = status.lower()
            # Ne considère 'canceled' comme échec que pour les créations d'ordres, pas l'annulation
            if status_lower in ('rejected',) or (status_lower in ('canceled','cancelled') and fn.__name__ != 'cancel_order'):
                raise RuntimeError(f"Order {order.get('id')} returned status '{status_lower}'")
        return order
    return wrapper
