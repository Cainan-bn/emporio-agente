from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from emporio.data.loader import DataLoadError, load_database


def test_loader_quantities() -> None:
    conn = load_database()
    cursor = conn.execute("SELECT COUNT(*) FROM categories")
    assert cursor.fetchone()[0] == 9
    cursor = conn.execute("SELECT COUNT(*) FROM products")
    assert cursor.fetchone()[0] == 65
    cursor = conn.execute("SELECT COUNT(*) FROM customers")
    assert cursor.fetchone()[0] == 50
    cursor = conn.execute("SELECT COUNT(*) FROM orders")
    assert cursor.fetchone()[0] == 20
    cursor = conn.execute("SELECT COUNT(*) FROM order_items")
    assert cursor.fetchone()[0] == 22
    cursor = conn.execute("SELECT COUNT(*) FROM promotions")
    assert cursor.fetchone()[0] == 25
    conn.close()


def test_loader_product_price() -> None:
    conn = load_database()
    cursor = conn.execute("SELECT price_cents FROM products WHERE product_id = ?", (93,))
    row = cursor.fetchone()
    assert row is not None
    price_decimal = Decimal(str(row[0])) / Decimal("100")
    assert price_decimal == Decimal("11499.00")
    conn.close()


def test_loader_missing_file(tmp_path: Path) -> None:
    with pytest.raises(DataLoadError, match="não encontrado"):
        load_database(tmp_path)


def test_loader_check_integrity(monkeypatch: pytest.MonkeyPatch) -> None:
    import hashlib

    checksums_before = {}
    for f in sorted(Path("data").iterdir()):
        checksums_before[f.name] = hashlib.sha256(f.read_bytes()).hexdigest()

    conn = load_database()
    conn.close()

    for f in sorted(Path("data").iterdir()):
        after = hashlib.sha256(f.read_bytes()).hexdigest()
        assert after == checksums_before[f.name], f"{f.name} foi modificado"
