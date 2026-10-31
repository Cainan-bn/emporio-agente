from __future__ import annotations

from emporio.tools.base import Tool, ToolContext, product_summary

_AVISO_PROMO = (
    "Promoções não são cumulativas e o desconto de 5% do PIX "
    "não vale sobre preço promocional (Manual §6.2)."
)


def _handler(ctx: ToolContext, args: dict) -> dict:
    filtro = args.get("produto_ou_categoria")

    if filtro:
        from emporio.text import normalize

        norm = normalize(filtro)
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
            cat_name = ""
            for c in ctx.products.list_categories():
                if c.category_id == prod.category_id:
                    cat_name = c.name
                    break
            if norm in normalize(cat_name):
                matched.append((prod, promo))
        active = [m for m in matched]
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
        s = product_summary(prod, promo, ctx.today)
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
