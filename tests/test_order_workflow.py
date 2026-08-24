import pytest

from private_cart.order_workflow import OrderLedger, OrderState


def test_only_the_authenticated_customer_can_complete_checkout() -> None:
    ledger = OrderLedger()
    order = ledger.checkout(customer_id="patient-shopper-7", sku="refill-case", quantity=1)

    with pytest.raises(PermissionError):
        ledger.mark_paid(order.order_id, authenticated_customer_id="different-customer")

    paid = ledger.mark_paid(order.order_id, authenticated_customer_id="patient-shopper-7")
    completed = ledger.fulfill_and_notify(paid.order_id)

    assert completed.state == OrderState.CUSTOMER_NOTIFIED
