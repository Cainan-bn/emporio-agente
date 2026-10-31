from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path
from typing import Any

import pypdf

from emporio.data.loader import find_data_file


def load_csv(path: Path) -> list[dict[str, str]]:
    """Lê um CSV (com ou sem BOM) e devolve lista de dicionários."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def column_null_counts(rows: list[dict[str, str]]) -> dict[str, int]:
    """Conta células vazias por coluna."""
    if not rows:
        return {}
    counts: dict[str, int] = {col: 0 for col in rows[0]}
    for row in rows:
        for col in rows[0]:
            if not row.get(col, "").strip():
                counts[col] += 1
    return counts


def find_duplicate_values(rows: list[dict[str, str]], column: str) -> list[tuple[str, list[int]]]:
    """Retorna (valor, lista_de_linhas) para valores duplicados em *column*."""
    seen: dict[str, list[int]] = {}
    for i, row in enumerate(rows, start=2):
        val = row.get(column, "").strip().lower()
        seen.setdefault(val, []).append(i)
    return [(v, lines) for v, lines in seen.items() if len(lines) > 1]


def check_orphans(
    child_rows: list[dict[str, str]],
    child_key: str,
    parent_rows: list[dict[str, str]],
    parent_key: str,
) -> list[str]:
    """Retorna FKs em child sem correspondente em parent."""
    parent_ids = {row[parent_key].strip() for row in parent_rows}
    orphans = []
    for row in child_rows:
        val = row[child_key].strip()
        if val and val not in parent_ids:
            orphans.append(val)
    return sorted(set(orphans))


def check_order_totals(
    orders: list[dict[str, str]],
    items: list[dict[str, str]],
    products: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """Retorna pedidos com total divergente ou itens com product_id órfão."""
    prices = {p["product_id"]: float(p["price_brl"]) for p in products}
    divergences: list[dict[str, Any]] = []
    item_by_order: dict[str, list[dict[str, str]]] = {}
    for it in items:
        item_by_order.setdefault(it["order_id"].strip(), []).append(it)
    for o in orders:
        oid = o["order_id"].strip()
        expected = 0.0
        orphan_pids: set[str] = set()
        for it in item_by_order.get(oid, []):
            qty = int(it["quantity"])
            pid = it["product_id"].strip()
            if pid not in prices:
                orphan_pids.add(pid)
                continue
            expected += qty * prices[pid]
        actual = float(o["total_brl"])
        entry: dict[str, Any] = {"order_id": int(oid), "actual": actual}
        if orphan_pids:
            entry["orphan_product_ids"] = sorted(orphan_pids)
        if abs(expected - actual) > 0.01 or orphan_pids:
            entry["expected"] = expected
            divergences.append(entry)
    return divergences


def extract_section_titles(path: Path) -> list[str]:
    """Extrai títulos de seção numerados do PDF com extraction_mode='layout'."""
    reader = pypdf.PdfReader(str(path))
    text = ""
    for page in reader.pages:
        text += page.extract_text(extraction_mode="layout")
    pattern = r"^\d+(?:\.\d+)?\.? [A-ZÁ-Ú][^\n]*"
    titles = re.findall(pattern, text, re.MULTILINE)
    return [t.strip() for t in titles if t.strip()]


def profile_csv(name: str, rows: list[dict[str, str]]) -> None:
    """Imprime perfil de um CSV."""
    n_rows = len(rows)
    n_cols = len(rows[0]) if rows else 0
    print(f"\n📄 {name}")
    print(f"  Linhas: {n_rows}  |  Colunas: {n_cols}")
    print(f"  Colunas: {', '.join(rows[0])}" if rows else "  (vazio)")

    if rows:
        nulls = column_null_counts(rows)
        nulos = {c: v for c, v in nulls.items() if v > 0}
        if nulos:
            print("  Nulos por coluna:")
            for c, v in nulos.items():
                print(f"    {c}: {v}")
        else:
            print("  Nulos: nenhum")


def main() -> None:
    print("=" * 55)
    print("  Perfil dos Dados — Empório da Música")
    print("=" * 55)

    # --- CSVs ------------------------------------------------------------------
    csv_files = {
        "categories": "categories.csv",
        "customers": "customers.csv",
        "order_items": "order_items.csv",
        "orders": "orders.csv",
        "products": "products.csv",
        "promotions": "promotions.csv",
    }

    data: dict[str, list[dict[str, str]]] = {}
    for key, suffix in csv_files.items():
        path = find_data_file(suffix)
        rows = load_csv(path)
        data[key] = rows
        label = key.replace("_", " ").title()
        profile_csv(label, rows)

    # --- Valores categóricos --------------------------------------------------
    print("\n📊 Valores Categóricos")

    status_vals = Counter(r["status"] for r in data["orders"])
    print(f"  orders.status: {dict(status_vals)}")

    payment_vals = Counter(r["payment_method"] for r in data["orders"])
    print(f"  orders.payment_method: {dict(payment_vals)}")

    active_vals = Counter(r["is_active"] for r in data["promotions"])
    print(f"  promotions.is_active: {dict(active_vals)}")

    cat_vals = Counter(r["category_id"] for r in data["products"])
    print(f"  products.category_id: {dict(sorted(cat_vals.items()))}")

    prod_status = Counter(r["status"] for r in data["products"])
    print(f"  products.status: {dict(prod_status)}")

    # --- Integridade referencial ----------------------------------------------
    print("\n🔗 Integridade Referencial")

    orphans_oc = check_orphans(data["orders"], "customer_id", data["customers"], "customer_id")
    print(f"  orders → customers (órfãos): {orphans_oc if orphans_oc else 'nenhum'}")

    orphans_op = check_orphans(data["order_items"], "product_id", data["products"], "product_id")
    print(f"  order_items → products (órfãos): {orphans_op if orphans_op else 'nenhum'}")

    orphans_oo = check_orphans(data["order_items"], "order_id", data["orders"], "order_id")
    print(f"  order_items → orders (órfãos): {orphans_oo if orphans_oo else 'nenhum'}")

    orphans_pp = check_orphans(data["promotions"], "product_id", data["products"], "product_id")
    print(f"  promotions → products (órfãos): {orphans_pp if orphans_pp else 'nenhum'}")

    orphans_pc = check_orphans(data["products"], "category_id", data["categories"], "category_id")
    print(f"  products → categories (órfãos): {orphans_pc if orphans_pc else 'nenhum'}")

    # --- Totais divergentes ---------------------------------------------------
    divergences = check_order_totals(data["orders"], data["order_items"], data["products"])
    print("\n💰 Totais Divergentes (total_brl ≠ soma qty × preço atual)")
    if divergences:
        for d in divergences:
            parts = [
                f"  Pedido {d['order_id']}: esperado {d['expected']:.2f}, "
                f"informado {d['actual']:.2f}"
            ]
            if "orphan_product_ids" in d:
                parts.append(f"  (product_id órfão: {d['orphan_product_ids']})")
            print("\n".join(parts))
    else:
        print("  Nenhum")

    # --- Chaves primárias duplicadas ------------------------------------------
    print("\n🔑 Chaves Primárias Duplicadas")
    pk_checks = [
        ("products", "product_id"),
        ("orders", "order_id"),
        ("customers", "customer_id"),
        ("categories", "category_id"),
        ("promotions", "promotion_id"),
    ]
    for table, pk in pk_checks:
        dups = find_duplicate_values(data[table], pk)
        if dups:
            for val, lines in dups:
                print(f"  {table}.{pk}: {val} repetido nas linhas {lines}")
        else:
            print(f"  {table}.{pk}: nenhuma duplicata")

    # --- E-mails duplicados ---------------------------------------------------
    dups = find_duplicate_values(data["customers"], "email")
    print("\n📧 E-mails Duplicados")
    if dups:
        for email, lines in dups:
            print(f"  {email}: linhas {lines}")
    else:
        print("  Nenhum")

    # --- Produtos -------------------------------------------------------------
    print("\n🏷️  Produtos")

    non_active = [p for p in data["products"] if p["status"].strip() != "active"]
    print(f"  Não ativos ({len(non_active)}):")
    for p in non_active:
        print(
            f"    #{p['product_id']} {p['name'][:50]:50s} status={p['status']} "
            f"estoque={p['stock_quantity']}"
        )

    zero_stock = [
        p
        for p in data["products"]
        if int(p["stock_quantity"]) == 0 and p["status"].strip() == "active"
    ]
    print(f"  Ativos com estoque 0 ({len(zero_stock)}):")
    for p in zero_stock:
        print(f"    #{p['product_id']} {p['name'][:50]}")

    inativos_com_estoque = [
        p
        for p in data["products"]
        if p["status"].strip() != "active" and int(p["stock_quantity"]) > 0
    ]
    print(f"  Indisponíveis com estoque ({len(inativos_com_estoque)}):")
    for p in inativos_com_estoque:
        print(
            f"    #{p['product_id']} {p['name'][:50]:50s} status={p['status']} "
            f"estoque={p['stock_quantity']}"
        )

    # --- Promoções ativas -----------------------------------------------------
    ativas = [p for p in data["promotions"] if p["is_active"].strip() == "1"]
    print(f"\n🎯 Promoções Ativas ({len(ativas)}):")
    for p in ativas:
        print(
            f"    #{p['promotion_id']} produto #{p['product_id']} "
            f"{p['discount_percent']}% — {p['description']}"
        )

    # --- PDF ------------------------------------------------------------------
    print("\n📄 PDF — Políticas da Loja")
    pdf_path = find_data_file(".pdf")
    reader = pypdf.PdfReader(str(pdf_path))
    n_pages = len(reader.pages)
    text = ""
    for page in reader.pages:
        text += page.extract_text(extraction_mode="layout")
    print(f"  Páginas: {n_pages}")
    print(f"  Caracteres: {len(text)}")
    titles = extract_section_titles(pdf_path)
    print(f"  Seções encontradas: {len(titles)}")
    for t in titles:
        print(f"    {t}")

    print("\n" + "=" * 55)
    print("  Perfil concluído.")
    print("=" * 55)


if __name__ == "__main__":
    main()
