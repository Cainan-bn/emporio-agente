from __future__ import annotations

from decimal import Decimal

import pytest

from emporio.data.loader import load_database
from emporio.data.repositories import OrderRepository


@pytest.fixture
def repo() -> OrderRepository:
    conn = load_database()
    return OrderRepository(conn)


def test_order_1_ok(repo: OrderRepository) -> None:
    order = repo.get_for_customer(1, "pedro.oliveira@jmail.com")
    assert order is not None
    assert order.order_id == 1
    assert len(order.items) == 1
    assert order.items[0].product_name == "Martin D-28 Dreadnought Natural"


def test_order_wrong_email(repo: OrderRepository) -> None:
    assert repo.get_for_customer(1, "other@jmail.com") is None


def test_order_nonexistent(repo: OrderRepository) -> None:
    assert repo.get_for_customer(999, "any@jmail.com") is None


def test_order_email_case_insensitive(repo: OrderRepository) -> None:
    order = repo.get_for_customer(1, "  PEDRO.OLIVEIRA@JMAIL.COM  ")
    assert order is not None


def test_order_sql_injection(repo: OrderRepository) -> None:
    assert repo.get_for_customer(1, "1; DROP TABLE orders") is None


def test_order_empty_email(repo: OrderRepository) -> None:
    assert repo.get_for_customer(1, "") is None
    assert repo.get_for_customer(1, "  ") is None


def test_order_3_total_paid(repo: OrderRepository) -> None:
    order = repo.get_for_customer(3, "isabela.moreira@jmail.com")
    assert order is not None
    assert order.total_brl == Decimal("3450.00")


def test_order_17_notes(repo: OrderRepository) -> None:
    order = repo.get_for_customer(17, "matheus.correia@hayoo.com.br")
    assert order is not None
    assert order.notes is not None
    assert "cancelado" in order.notes.lower()


def test_order_contains_no_personal_data(repo: OrderRepository) -> None:
    order = repo.get_for_customer(1, "pedro.oliveira@jmail.com")
    assert order is not None
    assert not hasattr(order, "email")
    assert not hasattr(order, "phone")
    assert not hasattr(order, "name")
    assert not hasattr(order, "customer_id")
