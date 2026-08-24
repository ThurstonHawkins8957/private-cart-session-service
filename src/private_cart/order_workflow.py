from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import uuid4


class OrderState(StrEnum):
    CHECKOUT = "checkout"
    PAID = "paid"
    FULFILLING = "fulfilling"
    RECEIPT_READY = "receipt_ready"
    CUSTOMER_NOTIFIED = "customer_notified"


@dataclass
class Order:
    order_id: str
    customer_id: str
    sku: str
    quantity: int
    state: OrderState = OrderState.CHECKOUT


class OrderLedger:
    def __init__(self) -> None:
        self._orders: dict[str, Order] = {}

    def checkout(self, customer_id: str, sku: str, quantity: int) -> Order:
        order = Order(str(uuid4()), customer_id, sku, quantity)
        self._orders[order.order_id] = order
        return order

    def mark_paid(self, order_id: str, authenticated_customer_id: str) -> Order:
        order = self._orders[order_id]
        if order.customer_id != authenticated_customer_id:
            raise PermissionError("The session does not own this order")
        if order.state != OrderState.CHECKOUT:
            raise ValueError("Only a checkout can be marked paid")
        order.state = OrderState.PAID
        return order

    def fulfill_and_notify(self, order_id: str) -> Order:
        order = self._orders[order_id]
        if order.state != OrderState.PAID:
            raise ValueError("Payment must be recorded before fulfillment")
        order.state = OrderState.FULFILLING
        order.state = OrderState.RECEIPT_READY
        order.state = OrderState.CUSTOMER_NOTIFIED
        return order
