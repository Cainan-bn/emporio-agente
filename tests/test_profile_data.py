from __future__ import annotations

from pathlib import Path

import pytest

from scripts.profile_data import (
    check_order_totals,
    extract_section_titles,
    find_data_file,
    find_duplicate_values,
    load_csv,
)


def test_find_data_file() -> None:
    path = find_data_file("orders.csv")
    assert path.exists()
    assert "orders" in path.name


def test_find_data_file_not_found() -> None:
    with pytest.raises(FileNotFoundError):
        find_data_file("nonexistent.csv")


def test_find_data_file_multiple_matches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "a_orders.csv").write_text("x\n1\n")
    (data_dir / "b_orders.csv").write_text("x\n2\n")

    import scripts.profile_data as pm

    monkeypatch.setattr(pm, "DATA_DIR", data_dir)
    with pytest.raises(FileNotFoundError, match="Múltiplos"):
        find_data_file("orders.csv")


def test_pk_duplicates_real_data() -> None:
    pk_tables = [
        ("products", "product_id"),
        ("orders", "order_id"),
        ("customers", "customer_id"),
        ("categories", "category_id"),
        ("promotions", "promotion_id"),
    ]
    for table, pk in pk_tables:
        rows = load_csv(find_data_file(f"{table}.csv"))
        dups = find_duplicate_values(rows, pk)
        assert dups == [], f"{table}.{pk} tem duplicatas inesperadas: {dups}"


def test_pk_duplicates_tmp_path(tmp_path: Path) -> None:
    csv_path = tmp_path / "test.csv"
    csv_path.write_text("id,name\n1,Alice\n2,Bob\n1,Charlie\n")
    rows = load_csv(csv_path)
    dups = find_duplicate_values(rows, "id")
    assert len(dups) == 1
    assert dups[0][0] == "1"


def test_profiles_quantities() -> None:
    products = load_csv(find_data_file("products.csv"))
    assert len(products) == 65

    orders = load_csv(find_data_file("orders.csv"))
    assert len(orders) == 20

    customers = load_csv(find_data_file("customers.csv"))
    assert len(customers) == 50

    promotions = load_csv(find_data_file("promotions.csv"))
    assert len(promotions) == 25


def test_active_promotions() -> None:
    promotions = load_csv(find_data_file("promotions.csv"))
    ativas = [p for p in promotions if p["is_active"].strip() == "1"]
    assert len(ativas) == 4


def test_divergent_order_totals() -> None:
    orders = load_csv(find_data_file("orders.csv"))
    items = load_csv(find_data_file("order_items.csv"))
    products = load_csv(find_data_file("products.csv"))
    divergences = check_order_totals(orders, items, products)
    assert {d["order_id"] for d in divergences} == {3, 20}


def test_duplicate_emails() -> None:
    customers = load_csv(find_data_file("customers.csv"))
    dups = find_duplicate_values(customers, "email")
    assert len(dups) == 1
    email, lines = dups[0]
    assert email == "bruno.martins@jmail.com"
    assert len(lines) == 2


def test_pdf_section_titles() -> None:
    pdf_path = find_data_file(".pdf")
    titles = extract_section_titles(pdf_path)
    all_titles = "\n".join(titles)
    assert "4.1" in all_titles
    assert "7.1" in all_titles
    assert "8.1" in all_titles
    assert "10" in all_titles
    assert any("Disposições Finais" in t for t in titles)


def test_csv_minimal(tmp_path: Path) -> None:
    csv_path = tmp_path / "test.csv"
    csv_path.write_text("id,name,email\n1,Alice,\n2,Bob,bob@jmail.com\n3,Charlie,bob@jmail.com\n")
    rows = load_csv(csv_path)
    assert len(rows) == 3

    from scripts.profile_data import column_null_counts

    nulls = column_null_counts(rows)
    assert nulls["email"] == 1

    dups = find_duplicate_values(rows, "email")
    assert len(dups) == 1
    assert dups[0][0] == "bob@jmail.com"
