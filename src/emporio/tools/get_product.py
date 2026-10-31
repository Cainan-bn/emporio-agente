from __future__ import annotations

from emporio.tools.base import Tool, ToolContext, product_summary

_AVISO_PROMO = (
    "Promoções não são cumulativas e o desconto de 5% do PIX "
    "não vale sobre preço promocional (Manual §6.2)."
)


def _handler(ctx: ToolContext, args: dict) -> dict:
    raw = args["produto"]
    product = None
    items: list = []
    is_ambiguous = False

    if raw.isdigit():
        product = ctx.products.get(int(raw))
        if product:
            items = [product]
    else:
        results = ctx.products.search(raw, limit=5)
        if results:
            # Check exact normalized name match
            from emporio.text import compact, normalize

            norm_term = compact(normalize(raw))
            exact = [p for p in results if compact(normalize(p.name)) == norm_term]
            if exact:
                items = exact[:1]
            elif len(results) == 1:
                items = results
            else:
                is_ambiguous = True
                items = results

    if not items:
        return {"encontrado": False}

    if is_ambiguous:
        candidates = []
        for p in items:
            promo = ctx.promotions.get_active_for_product(p.product_id)
            candidates.append(product_summary(p, promo, ctx.today))
        return {"ambiguo": True, "candidatos": candidates}

    p = items[0]
    promo = ctx.promotions.get_active_for_product(p.product_id)
    summary = product_summary(p, promo, ctx.today)
    summary["descricao"] = p.description
    summary["especificacoes"] = p.specs

    if promo and promo.is_active:
        summary["aviso"] = _AVISO_PROMO

    return summary


TOOL = Tool(
    name="consultar_produto",
    description=(
        "Consultar detalhes completos de um produto por ID numérico ou nome/modelo. "
        "Quando o nome retorna vários candidatos, devolve lista para o LLM escolher. "
        "NÃO usar para buscas genéricas (use buscar_produtos). "
        "Inclui descrição, especificações técnicas e preço com promoção se houver."
    ),
    parameters={
        "type": "object",
        "properties": {
            "produto": {
                "type": "string",
                "description": "ID numérico ou nome/modelo do produto",
            }
        },
        "required": ["produto"],
    },
    handler=_handler,
)
