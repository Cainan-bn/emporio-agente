from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

from emporio.data.loader import DATA_DIR, load_database
from emporio.data.repositories import OrderRepository, ProductRepository, PromotionRepository
from emporio.policies.retriever import PolicyRetriever
from emporio.tools.base import ToolContext, ToolRegistry
from emporio.tools.get_order import TOOL as get_order_tool
from emporio.tools.get_product import TOOL as get_product_tool
from emporio.tools.get_store_info import TOOL as get_store_info_tool
from emporio.tools.handoff import TOOL as handoff_tool
from emporio.tools.list_promotions import TOOL as list_promotions_tool
from emporio.tools.query_policies import TOOL as query_policies_tool
from emporio.tools.search_products import TOOL as search_products_tool


def build_registry(
    conn: sqlite3.Connection | None = None,
    policies: PolicyRetriever | None = None,
    today: date | None = None,
    data_dir: Path | None = None,
) -> ToolRegistry:
    if conn is None:
        base = data_dir if data_dir is not None else DATA_DIR
        pdf_path = _find_pdf(base)
        conn = load_database(base)
    else:
        pdf_path = _find_pdf(DATA_DIR)

    today = today or date.today()

    if policies is None:
        policies = PolicyRetriever.from_pdf(str(pdf_path))

    products = ProductRepository(conn)
    promotions = PromotionRepository(conn)
    orders = OrderRepository(conn)

    ctx = ToolContext(
        products=products,
        promotions=promotions,
        orders=orders,
        policies=policies,
        today=today,
    )

    tools = [
        search_products_tool,
        get_product_tool,
        list_promotions_tool,
        get_order_tool,
        query_policies_tool,
        get_store_info_tool,
        handoff_tool,
    ]

    return ToolRegistry(ctx, tools)


def _find_pdf(base: Path) -> Path:
    for f in sorted(base.iterdir()):
        if f.suffix.lower() == ".pdf":
            return f
    msg = f"PDF não encontrado em {base}"
    raise FileNotFoundError(msg)
