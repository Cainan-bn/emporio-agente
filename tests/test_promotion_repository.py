from __future__ import annotations

from decimal import Decimal

import pytest

from emporio.data.loader import load_database
from emporio.data.repositories import ProductRepository, PromotionRepository


@pytest.fixture
def promo_repo() -> PromotionRepository:
    conn = load_database()
    return PromotionRepository(conn)


@pytest.fixture
def product_repo() -> ProductRepository:
    conn = load_database()
    return ProductRepository(conn)


def test_active_product_ids(promo_repo: PromotionRepository) -> None:
    active = promo_repo.list_active()
    pids = {p.product_id for p in active}
    assert pids == {127, 121, 90, 94}


def test_product_96_promo_expired(promo_repo: PromotionRepository) -> None:
    promos = promo_repo.get_active_for_product(96)
    assert promos is None


def test_get_active_for_product(promo_repo: PromotionRepository) -> None:
    promos = promo_repo.get_active_for_product(127)
    assert promos is not None


def test_final_price(promo_repo: PromotionRepository, product_repo: ProductRepository) -> None:
    product = product_repo.get(121)
    assert product is not None
    active = promo_repo.list_active()
    promo = next((p for p in active if p.product_id == 121), None)
    assert promo is not None
    result = promo_repo.final_price(product, promo)
    assert result == Decimal("439.20")


def test_final_price_invalid_discount(
    promo_repo: PromotionRepository, product_repo: ProductRepository
) -> None:
    product = product_repo.get(81)
    assert product is not None
    from emporio.data.models import Promotion

    bad_promo = Promotion(
        promotion_id=999,
        product_id=81,
        discount_percent=-5,
        description="inválida",
        is_active=True,
    )
    with pytest.raises(ValueError, match="discount_percent.*entre 0 e 100"):
        promo_repo.final_price(product, bad_promo)
    bad_promo2 = Promotion(
        promotion_id=999,
        product_id=81,
        discount_percent=150,
        description="inválida",
        is_active=True,
    )
    with pytest.raises(ValueError):
        promo_repo.final_price(product, bad_promo2)
