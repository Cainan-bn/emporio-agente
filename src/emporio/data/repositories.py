from __future__ import annotations

import json
import sqlite3
from decimal import ROUND_HALF_UP, Decimal
from difflib import SequenceMatcher

from emporio.data.models import Category, Order, OrderItem, Product, Promotion
from emporio.text import compact, normalize

SIMILARITY_THRESHOLD = 0.85
_MIN_FUZZY_TOKEN_LEN = 4
_STOPWORDS_PT = frozenset(
    {
        "ate",
        "de",
        "com",
        "para",
        "por",
        "ou",
        "e",
        "um",
        "uma",
        "ao",
        "a",
        "o",
        "do",
        "da",
        "em",
        "no",
        "na",
        "os",
        "as",
        "dos",
        "das",
        "nos",
        "nas",
        "pelo",
        "pela",
    }
)


def _singular(token: str) -> str:
    """Singular aproximado de um token já normalizado ('violoes' -> 'violao')."""
    if token.endswith("oes") and len(token) > 4:
        return token[:-3] + "ao"
    if token.endswith("s") and len(token) > 3:
        return token[:-1]
    return token


def _category_tokens(text: str) -> set[str]:
    """Tokens de categoria no singular; ignora palavras de até 2 letras ('e', 'de')."""
    return {_singular(t) for t in normalize(text).split() if len(t) > 2}


class ProductRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get(self, product_id: int) -> Product | None:
        row = self._conn.execute(
            "SELECT * FROM products WHERE product_id = ?", (product_id,)
        ).fetchone()
        return self._row_to_product(row) if row else None

    def find_by_name(self, term: str) -> list[Product]:
        if not term.strip():
            return []
        norm_term = normalize(term)
        if not norm_term:
            return []
        all_rows = self._conn.execute(
            "SELECT * FROM products ORDER BY price_cents, product_id"
        ).fetchall()
        results = []
        for r in all_rows:
            prod = self._row_to_product(r)
            if norm_term in normalize(prod.name):
                results.append(prod)
        return results

    def search(
        self,
        term: str,
        category: str | int | None = None,
        max_price: Decimal | None = None,
        only_available: bool = False,
        limit: int = 10,
    ) -> list[Product]:
        if not term.strip():
            return []
        norm_term = normalize(term)
        if not norm_term:
            return []
        tokens = norm_term.split()
        tokens = [t for t in tokens if t not in _STOPWORDS_PT and not t.isdigit()]

        tokens = [t[:50] for t in tokens[:8]]  # teto: evita custo O(n²) do fuzzy em entrada enorme

        if not tokens:
            return []

        compact_full = compact(norm_term)

        all_products = self._conn.execute(
            "SELECT p.*, c.name AS category_name "
            "FROM products p "
            "JOIN categories c ON p.category_id = c.category_id "
            "ORDER BY p.product_id"
        ).fetchall()

        cat_ids: set[int] | None = None
        if category is not None:
            cat_ids = self.resolve_categories(category)

        scored: list[tuple[int, Decimal, int, Product]] = []
        for row in all_products:
            prod = self._row_to_product(row)
            cat_name: str = row["category_name"]

            if cat_ids is not None and prod.category_id not in cat_ids:
                continue
            if max_price is not None and prod.price_brl > max_price:
                continue
            if only_available and not prod.is_available:
                continue

            score, _ = self._match_score(tokens, compact_full, prod, cat_name)
            if score > 0:
                scored.append((score, prod.price_brl, prod.product_id, prod))

        scored.sort(key=lambda x: (-x[0], x[1], x[2]))
        return [p[3] for p in scored[:limit]]

    def list_categories(self) -> list[Category]:
        rows = self._conn.execute("SELECT * FROM categories ORDER BY category_id").fetchall()
        return [
            Category(
                category_id=int(r["category_id"]),
                name=r["name"],
                description=r["description"],
            )
            for r in rows
        ]

    def resolve_categories(self, category: str | int) -> set[int]:
        """Resolve nome/termo de categoria em ids, tolerando acento, caixa e plural.

        Compara tokens normalizados e no singular ("violões" ~ "Violões", "ukulele" ~
        "Ukuleles"). Nenhuma correspondência -> `{0}` (id inexistente), para que a busca
        devolva vazio em vez de ignorar o filtro.
        """
        if isinstance(category, int):
            return {category}
        wanted = _category_tokens(category)
        cursor = self._conn.execute("SELECT category_id, name FROM categories")
        result = {int(cid) for cid, cname in cursor.fetchall() if wanted & _category_tokens(cname)}
        return result if result else {0}

    def _match_score(
        self,
        tokens: list[str],
        compact_term: str,
        product: Product,
        category_name: str,
    ) -> tuple[int, float]:
        norm_name = normalize(product.name)
        norm_cat = normalize(category_name)
        name_tokens = set(norm_name.split())
        cat_tokens = set(norm_cat.split())
        all_tokens = name_tokens | cat_tokens

        # Rank 1: every token matches exactly a word in name or category
        if all(t in all_tokens for t in tokens):
            return (3, 1.0)

        # Rank 2: compact of full term in compact of product name (only if >= 4 chars)
        compact_name = compact(norm_name)
        if len(compact_term) >= 4 and compact_term in compact_name:
            return (2, 0.0)

        # Rank 3 (fallback): fuzzy only for tokens >= 4 chars
        suitable = [t for t in tokens if len(t) >= _MIN_FUZZY_TOKEN_LEN]
        if not suitable:
            return (0, 0.0)
        tokens_text = f"{norm_name} {normalize(product.description)} {norm_cat}"
        for tok in suitable:
            ok = any(
                SequenceMatcher(None, tok, word).ratio() >= SIMILARITY_THRESHOLD
                for word in tokens_text.split()
            )
            if not ok:
                return (0, 0.0)
        return (1, 0.0)

    @staticmethod
    def _row_to_product(row: sqlite3.Row) -> Product:
        from datetime import date

        return Product(
            product_id=int(row["product_id"]),
            price_brl=Decimal(str(row["price_cents"])) / Decimal("100"),
            name=row["name"],
            category_id=int(row["category_id"]),
            description=row["description"],
            stock_quantity=int(row["stock_quantity"]),
            status=row["status"],
            specs=json.loads(row["specs"]),
            created_at=date.fromisoformat(row["created_at"]),
        )


class PromotionRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get_active_for_product(self, product_id: int) -> Promotion | None:
        row = self._conn.execute(
            "SELECT * FROM promotions WHERE product_id = ? AND is_active = 1",
            (product_id,),
        ).fetchone()
        if not row:
            return None
        return self._row_to_promotion(row)

    def list_active(self) -> list[Promotion]:
        rows = self._conn.execute(
            "SELECT * FROM promotions WHERE is_active = 1 ORDER BY promotion_id"
        ).fetchall()
        return [self._row_to_promotion(r) for r in rows]

    @staticmethod
    def final_price(product: Product, promotion: Promotion) -> Decimal:
        if not 0 <= promotion.discount_percent <= 100:
            msg = (
                f"discount_percent deve estar entre 0 e 100, recebido {promotion.discount_percent}"
            )
            raise ValueError(msg)
        discount = product.price_brl * Decimal(promotion.discount_percent) / Decimal("100")
        return (product.price_brl - discount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def _row_to_promotion(row: sqlite3.Row) -> Promotion:
        return Promotion(
            promotion_id=int(row["promotion_id"]),
            product_id=int(row["product_id"]),
            discount_percent=int(row["discount_percent"]),
            description=row["description"],
            is_active=bool(int(row["is_active"])),
        )


class OrderRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get_for_customer(self, order_id: int, email: str) -> Order | None:
        from datetime import date

        if not email or not email.strip():
            return None
        try:
            int(order_id)
        except (ValueError, TypeError):
            return None
        sanitized_email = email.strip().lower()

        row = self._conn.execute(
            "SELECT o.*, c.email AS customer_email "
            "FROM orders o "
            "JOIN customers c ON o.customer_id = c.customer_id "
            "WHERE o.order_id = ?",
            (order_id,),
        ).fetchone()
        if not row:
            return None

        owner_email = row["customer_email"].strip().lower()
        if owner_email != sanitized_email:
            return None

        items = self._conn.execute(
            "SELECT oi.*, p.name AS product_name "
            "FROM order_items oi "
            "JOIN products p ON oi.product_id = p.product_id "
            "WHERE oi.order_id = ?",
            (order_id,),
        ).fetchall()

        return Order(
            order_id=int(row["order_id"]),
            order_date=date.fromisoformat(row["order_date"]) if row["order_date"] else None,
            status=row["status"],
            total_brl=Decimal(str(row["total_cents"])) / Decimal("100"),
            payment_method=row["payment_method"],
            tracking_code=row["tracking_code"],
            estimated_delivery=date.fromisoformat(row["estimated_delivery"])
            if row["estimated_delivery"]
            else None,
            notes=row["notes"] if row["notes"] else None,
            items=[
                OrderItem(
                    order_id=int(i["order_id"]),
                    quantity=int(i["quantity"]),
                    product_id=int(i["product_id"]),
                    product_name=i["product_name"],
                )
                for i in items
            ],
        )
