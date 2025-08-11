# path: tests/test_decorators.py
import pytest
from utils.decorators import verify_order


class Svc:
    @verify_order
    def ok(self):
        return {"id": "1", "status": "open", "symbol": "X/Y", "type": "limit", "side": "buy"}

    @verify_order
    def missing_id(self):
        return {"status": "open", "symbol": "X/Y"}

    @verify_order
    def rejected(self):
        return {"id": "2", "status": "rejected", "symbol": "X/Y"}

    @verify_order
    def none(self):
        return None  # type: ignore[return-value]


def test_verify_order_pass_through():
    s = Svc()
    order = s.ok()
    assert order["id"] == "1"
    assert order["status"] == "open"


def test_verify_order_missing_id_raises():
    s = Svc()
    with pytest.raises(RuntimeError):
        s.missing_id()


def test_verify_order_rejected_raises():
    s = Svc()
    with pytest.raises(RuntimeError):
        s.rejected()


def test_verify_order_none_raises():
    s = Svc()
    with pytest.raises(RuntimeError):
        s.none()
