from __future__ import annotations

import csv
import json
import sqlite3
from decimal import Decimal
from pathlib import Path


class DataLoadError(Exception):
    """Erro durante carga dos dados."""


DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"


def find_data_file(suffix: str) -> Path:
    """Retorna o único arquivo em DATA_DIR cujo nome termina com *suffix*."""
    suffix = suffix.lower()
    matches: list[Path] = []
    for f in sorted(DATA_DIR.iterdir()):
        if f.name.lower().endswith(suffix):
            matches.append(f)
    if len(matches) > 1:
        names = [m.name for m in matches]
        msg = f"Múltiplos arquivos com sufixo {suffix!r}: {names}"
        raise DataLoadError(msg)
    if not matches:
        msg = f"Arquivo *{suffix} não encontrado em {DATA_DIR}"
        raise DataLoadError(msg)
    return matches[0]


def load_csv(name: str) -> list[dict[str, str]]:
    path = find_data_file(name)
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _load_csv(name: str) -> list[dict[str, str]]:
    return load_csv(name)


def _to_cents(value: str) -> int:
    """Converte string decimal (ex.: '599.9', '11499') para centavos inteiros."""
    return int(Decimal(value.strip()) * 100)


def _to_nullable(value: str) -> str | None:
    v = value.strip()
    return v if v else None


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS categories (
    category_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    product_id INTEGER PRIMARY KEY,
    price_cents INTEGER NOT NULL,
    name TEXT NOT NULL,
    category_id INTEGER NOT NULL REFERENCES categories(category_id),
    description TEXT NOT NULL,
    stock_quantity INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active', 'discontinued', 'coming_soon')),
    specs TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS customers (
    customer_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    email TEXT NOT NULL,
    city TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    order_date TEXT,
    status TEXT NOT NULL,
    total_cents INTEGER NOT NULL,
    payment_method TEXT NOT NULL,
    tracking_code TEXT,
    estimated_delivery TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS order_items (
    order_id INTEGER NOT NULL REFERENCES orders(order_id),
    quantity INTEGER NOT NULL,
    product_id INTEGER NOT NULL REFERENCES products(product_id)
);

CREATE TABLE IF NOT EXISTS promotions (
    promotion_id INTEGER PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(product_id),
    discount_percent INTEGER NOT NULL,
    description TEXT NOT NULL,
    is_active INTEGER NOT NULL
);
"""


def load_database(data_dir: Path | None = None) -> sqlite3.Connection:
    """Carrega os CSVs em um banco SQLite em memória e devolve a conexão."""
    global DATA_DIR  # noqa: PLW0603
    if data_dir is not None:
        DATA_DIR = data_dir

    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_SCHEMA_SQL)

    # categories
    rows = _load_csv("categories.csv")
    conn.executemany(
        "INSERT INTO categories (category_id, name, description) VALUES (?, ?, ?)",
        [(int(r["category_id"]), r["name"], r["description"]) for r in rows],
    )

    # customers
    rows = _load_csv("customers.csv")
    conn.executemany(
        "INSERT INTO customers (customer_id, name, phone, email, city) VALUES (?, ?, ?, ?, ?)",
        [(int(r["customer_id"]), r["name"], r["phone"], r["email"], r["city"]) for r in rows],
    )

    # products
    rows = _load_csv("products.csv")
    conn.executemany(
        "INSERT INTO products (product_id, price_cents, name, category_id, "
        "description, stock_quantity, status, specs, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                int(r["product_id"]),
                _to_cents(r["price_brl"]),
                r["name"],
                int(r["category_id"]),
                r["description"],
                int(r["stock_quantity"]),
                r["status"],
                json.dumps(json.loads(r["specs"])),
                r["created_at"],
            )
            for r in rows
        ],
    )

    # orders
    rows = _load_csv("orders.csv")
    conn.executemany(
        "INSERT INTO orders (order_id, customer_id, order_date, status, total_cents, "
        "payment_method, tracking_code, estimated_delivery, notes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                int(r["order_id"]),
                int(r["customer_id"]),
                _to_nullable(r["order_date"]),
                r["status"],
                _to_cents(r["total_brl"]),
                r["payment_method"],
                _to_nullable(r["tracking_code"]),
                _to_nullable(r["estimated_delivery"]),
                _to_nullable(r["notes"]),
            )
            for r in rows
        ],
    )

    # order_items
    rows = _load_csv("order_items.csv")
    conn.executemany(
        "INSERT INTO order_items (order_id, quantity, product_id) VALUES (?, ?, ?)",
        [(int(r["order_id"]), int(r["quantity"]), int(r["product_id"])) for r in rows],
    )

    # promotions
    rows = _load_csv("promotions.csv")
    conn.executemany(
        "INSERT INTO promotions (promotion_id, product_id, discount_percent, "
        "description, is_active) VALUES (?, ?, ?, ?, ?)",
        [
            (
                int(r["promotion_id"]),
                int(r["product_id"]),
                int(r["discount_percent"]),
                r["description"],
                int(r["is_active"]),
            )
            for r in rows
        ],
    )

    conn.commit()
    return conn
