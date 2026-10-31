from __future__ import annotations

from emporio.formatting import format_brl, format_date
from emporio.tools.base import (
    Tool,
    ToolContext,
    _payment_method_pt,
    _status_pt,
)


def _handler(ctx: ToolContext, args: dict) -> dict:
    order_id = args["numero_pedido"]
    email = args.get("email", "")

    order = ctx.orders.get_for_customer(order_id, email)
    if order is None:
        return {
            "verificado": False,
            "mensagem": "Não foi possível verificar este pedido com os dados informados.",
        }

    days_since_order = (ctx.today - order.order_date).days if order.order_date else None
    days_since_est = (
        (ctx.today - order.estimated_delivery).days if order.estimated_delivery else None
    )

    result: dict = {
        "verificado": True,
        "pedido": {
            "numero": order.order_id,
            "status": _status_pt(order.status),
            "data_do_pedido": format_date(order.order_date) if order.order_date else None,
            "itens": [{"produto": i.product_name, "quantidade": i.quantity} for i in order.items],
            "total": format_brl(order.total_brl),
            "forma_de_pagamento": _payment_method_pt(order.payment_method),
            "codigo_de_rastreio": order.tracking_code,
            "entrega_estimada": (
                format_date(order.estimated_delivery) if order.estimated_delivery else None
            ),
            "observacao": order.notes,
        },
        "hoje": format_date(ctx.today),
        "dias_desde_o_pedido": days_since_order,
        "dias_desde_a_entrega_estimada": days_since_est,
    }

    if order.status == "delivered":
        result["aviso_prazos"] = (
            "A base não registra a data de recebimento; "
            "a entrega estimada é apenas uma referência aproximada."
        )

    return result


TOOL = Tool(
    name="consultar_pedido",
    description=(
        "Consultar pedido pelo número informado pelo cliente e e-mail cadastrado. "
        "Exige AMBOS número do pedido e e-mail — NUNCA chutar o e-mail. "
        "Retorna status, itens, total (valor pago), rastreio e prazos. "
        "Se a verificação falhar, a mensagem é genérica (mesma para pedido inexistente ou "
        "e-mail errado). NÃO informar ao cliente qual dos dois está incorreto."
    ),
    parameters={
        "type": "object",
        "properties": {
            "numero_pedido": {
                "type": "integer",
                "description": "Número do pedido informado pelo cliente",
            },
            "email": {
                "type": "string",
                "description": "E-mail cadastrado do cliente",
            },
        },
        "required": ["numero_pedido", "email"],
    },
    handler=_handler,
)
