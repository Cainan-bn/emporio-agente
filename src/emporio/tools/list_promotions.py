from __future__ import annotations

from emporio.text import normalize
from emporio.tools.base import Tool, ToolContext, _cat_name, product_summary

_AVISO_PROMO = (
    "Promoções não são cumulativas e o desconto de 5% do PIX "
    "não vale sobre preço promocional (Manual §6.2)."
)


def _handler(ctx: ToolContext, args: dict) -> dict:
    filtro = args.get("produto_ou_categoria")

    if filtro:
        norm = normalize(filtro)
        if not norm:
            return {
                "promocoes": [],
                "aviso": "Não há promoção vigente para o item informado.",
            }
        cat_ids = ctx.products._resolve_category(filtro)
        all_active = ctx.promotions.list_active()
        matched = []
        for promo in all_active:
            prod = ctx.products.get(promo.product_id)
            if prod is None:
                continue
            prod_norm = normalize(prod.name)
            if norm in prod_norm:
                matched.append((prod, promo))
                continue
            if cat_ids and prod.category_id in cat_ids:
                matched.append((prod, promo))
                continue
        active = matched
    else:
        active = [(ctx.products.get(p.product_id), p) for p in ctx.promotions.list_active()]
        active = [(p, r) for p, r in active if p is not None]

    if not active:
        return {
            "promocoes": [],
            "aviso": "Não há promoção vigente para o item informado.",
        }

    items = []
    for prod, promo in active:
        cat = _cat_name(ctx, prod.category_id)
        s = product_summary(prod, promo, ctx.today, category_name=cat)
        items.append(s)

    return {"promocoes": items, "aviso": _AVISO_PROMO}


TOOL = Tool(
    name="consultar_promocoes",
    description=(
        "Listar promoções vigentes (active=1). Opcionalmente filtrar por nome de produto "
        "ou categoria. Promoções inativas nunca são exibidas. "
        "NÃO usar para simular descontos que não existem no sistema. "
        "O aviso de não cumulatividade é incluso automaticamente."
    ),
    parameters={
        "type": "object",
        "properties": {"produto_ou_categoria": {"type": "string"}},
    },
    handler=_handler,
)
