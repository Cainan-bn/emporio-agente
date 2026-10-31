from __future__ import annotations

import math
from decimal import Decimal

from emporio.tools.base import Tool, ToolContext, _cat_name, product_summary

_TOOL_PARAMS = {
    "type": "object",
    "properties": {
        "termo": {"type": "string"},
        "categoria": {"type": "string"},
        "preco_max": {"type": "number"},
        "apenas_em_estoque": {"type": "boolean"},
    },
    "required": ["termo"],
}


def _handler(ctx: ToolContext, args: dict) -> dict:
    termo = args["termo"]
    categoria = (args.get("categoria") or "").strip() or None  # "" do LLM = sem filtro
    preco_max = args.get("preco_max")
    if preco_max is not None:
        if isinstance(preco_max, float) and math.isinf(preco_max):
            preco_max = None
        else:
            preco_max = Decimal(str(preco_max))
    apenas_estoque = args.get("apenas_em_estoque", False)

    results = ctx.products.search(
        term=termo,
        category=categoria,
        max_price=preco_max,
        only_available=apenas_estoque,
        limit=8,
    )

    if not results:
        return {
            "total": 0,
            "produtos": [],
            "aviso": "Nenhum produto encontrado no catálogo.",
        }

    summaries = []
    for p in results:
        promo = ctx.promotions.get_active_for_product(p.product_id)
        cat = _cat_name(ctx, p.category_id)
        summaries.append(product_summary(p, promo, ctx.today, category_name=cat))

    return {"total": len(summaries), "produtos": summaries}


TOOL = Tool(
    name="buscar_produtos",
    description=(
        "Buscar produtos no catálogo por termo, categoria ou faixa de preço. "
        "Usar quando o cliente pergunta por um produto, modelo, marca ou tipo. "
        "NÃO usar para consultar detalhes de um produto já identificado (use consultar_produto). "
        "NÃO inferir que uma categoria 'não existe' se a busca voltar vazia."
    ),
    parameters=_TOOL_PARAMS,
    handler=_handler,
)
