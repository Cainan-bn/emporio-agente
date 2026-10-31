from __future__ import annotations

from decimal import Decimal

import pytest

from emporio.data.loader import load_database
from emporio.data.repositories import ProductRepository


@pytest.fixture
def repo() -> ProductRepository:
    conn = load_database()
    return ProductRepository(conn)


def test_search_violao(repo: ProductRepository) -> None:
    results = repo.search("violao")
    assert len(results) > 0
    has_violao = any(p.category_id == 5 for p in results)
    assert has_violao, "Nenhum produto da categoria Violões nos resultados"


def test_search_violao_accents(repo: ProductRepository) -> None:
    r1 = repo.search("violao")
    r2 = repo.search("Violão")
    r3 = repo.search("VIOLÃO")
    assert len(r1) > 0
    assert len(r1) == len(r2) == len(r3)
    assert {p.product_id for p in r1} == {p.product_id for p in r2}


def test_search_gd20(repo: ProductRepository) -> None:
    results = repo.search("gd 20")
    names = [p.name for p in results]
    assert any("GD20" in n.replace(" ", "") for n in names)
    # Não deve trazer Ohana CK-20 (compact do nome contém "ck20", não "gd20")
    assert not any("CK-20" in n for n in names)


def test_search_typo_yamha_not_rozini(repo: ProductRepository) -> None:
    results = repo.search("yamha")
    names = [p.name for p in results]
    assert not any("Rozini" in n for n in names)


def test_search_typo_yamha(repo: ProductRepository) -> None:
    results = repo.search("yamha")
    names = [p.name for p in results]
    assert any("Yamaha" in n for n in names)


def test_search_filter_max_price(repo: ProductRepository) -> None:
    results = repo.search("violao", max_price=Decimal("1000"))
    for p in results:
        assert p.price_brl <= Decimal("1000"), f"{p.name} custa {p.price_brl}"


def test_search_only_available(repo: ProductRepository) -> None:
    all_results = repo.search("violao")
    available = repo.search("violao", only_available=True)
    assert len(available) <= len(all_results)

    product_96 = repo.get(96)
    if product_96:
        assert product_96 not in available

    for pid in [113, 136]:
        p = repo.get(pid)
        if p:
            assert p not in available, f"{p.name} (id {pid}) não deveria estar disponível"

    p130 = repo.get(130)
    if p130:
        assert p130 not in available, f"{p130.name} (coming_soon) não deveria estar disponível"


def test_search_empty_term(repo: ProductRepository) -> None:
    assert repo.search("") == []
    assert repo.search("   ") == []


def test_search_garbage_terms(repo: ProductRepository) -> None:
    assert repo.search("😀") == []
    assert repo.search("%") == []
    assert repo.search("_") == []
    assert repo.search("!!!") == []


def test_search_no_match(repo: ProductRepository) -> None:
    assert repo.search("trombone") == []


def test_search_category_by_name(repo: ProductRepository) -> None:
    by_name = repo.search("violao", category="violões")
    by_id = repo.search("violao", category=5)
    assert len(by_name) > 0
    assert {p.product_id for p in by_name} == {p.product_id for p in by_id}


def test_find_by_name_basic(repo: ProductRepository) -> None:
    results = repo.find_by_name("Nylon")
    assert len(results) > 0
    assert any("Nylon" in p.name for p in results)


def test_find_by_name_normalized(repo: ProductRepository) -> None:
    r1 = repo.find_by_name("nYlOn")
    r2 = repo.find_by_name("Nylon")
    assert len(r1) == len(r2) > 0
    assert {p.product_id for p in r1} == {p.product_id for p in r2}


def test_find_by_name_wildcards_not_expanded(repo: ProductRepository) -> None:
    r1 = repo.find_by_name("%")
    r2 = repo.find_by_name("_")
    assert len(r1) == 0
    assert len(r2) == 0


def test_get_product(repo: ProductRepository) -> None:
    p = repo.get(81)
    assert p is not None
    assert p.product_id == 81
    assert p.name == "Yamaha C40 Nylon Natural"


def test_get_nonexistent(repo: ProductRepository) -> None:
    assert repo.get(999) is None


def test_list_categories(repo: ProductRepository) -> None:
    cats = repo.list_categories()
    names = [c.name for c in cats]
    assert "Violões" in names
    assert "Ukuleles" in names
