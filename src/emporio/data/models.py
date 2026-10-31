from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class Category:
    category_id: int
    name: str
    description: str


@dataclass(frozen=True)
class Product:
    product_id: int
    price_brl: Decimal
    name: str
    category_id: int
    description: str
    stock_quantity: int
    status: str
    specs: dict[str, Any]
    created_at: date

    @property
    def is_available(self) -> bool:
        return self.status == "active" and self.stock_quantity > 0


@dataclass(frozen=True)
class Promotion:
    promotion_id: int
    product_id: int
    discount_percent: int
    description: str
    is_active: bool


@dataclass(frozen=True)
class OrderItem:
    order_id: int
    quantity: int
    product_id: int
    product_name: str


@dataclass(frozen=True)
class Order:
    order_id: int
    customer_id: int
    order_date: date | None
    status: str
    total_brl: Decimal
    payment_method: str
    tracking_code: str | None
    estimated_delivery: date | None
    notes: str | None
    items: list[OrderItem] = field(default_factory=list)


@dataclass(frozen=True)
class Customer:
    customer_id: int
    name: str
    phone: str
    email: str
    city: str
