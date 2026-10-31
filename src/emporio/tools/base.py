from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from emporio.data.repositories import (
    OrderRepository,
    ProductRepository,
    PromotionRepository,
)
from emporio.formatting import format_brl
from emporio.policies.retriever import PolicyRetriever

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ToolContext:
    products: ProductRepository
    promotions: PromotionRepository
    orders: OrderRepository
    policies: PolicyRetriever
    today: date


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[[ToolContext, dict[str, Any]], dict[str, Any]]


_JSON_TYPES = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
}


class ToolRegistry:
    def __init__(self, context: ToolContext, tools: list[Tool]) -> None:
        self._context = context
        self._tools = {t.name: t for t in tools}

    def schemas(self) -> list[dict[str, Any]]:
        result = []
        for t in self._tools.values():
            result.append(
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
            )
        return result

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def execute(self, name: str, arguments: str | dict[str, Any]) -> str:
        try:
            tool = self._tools.get(name)
            if tool is None:
                return json.dumps(
                    {"erro": f"Ferramenta desconhecida: {name}"},
                    ensure_ascii=False,
                )

            if isinstance(arguments, str):
                try:
                    args = json.loads(arguments)
                except json.JSONDecodeError as exc:
                    return json.dumps(
                        {"erro": f"JSON inválido nos argumentos: {exc}"},
                        ensure_ascii=False,
                    )
            else:
                args = arguments

            if not isinstance(args, dict):
                return json.dumps(
                    {"erro": "Argumentos devem ser um objeto JSON"},
                    ensure_ascii=False,
                )

            props = tool.parameters.get("properties", {})
            required = tool.parameters.get("required", [])

            for key in required:
                if key not in args or args[key] is None:
                    return json.dumps(
                        {"erro": f"Argumento obrigatório ausente: {key}"},
                        ensure_ascii=False,
                    )

            for key, val in list(args.items()):
                if key not in props:
                    del args[key]
                    continue
                schema_type = props[key].get("type")
                py_type = _JSON_TYPES.get(schema_type)
                if py_type is not None and val is not None:
                    if not isinstance(val, py_type):
                        return json.dumps(
                            {
                                "erro": f"Argumento {key}: "
                                f"esperado {schema_type}, "
                                f"recebido {type(val).__name__}"
                            },
                            ensure_ascii=False,
                        )

            result = tool.handler(self._context, args)
            return json.dumps(result, ensure_ascii=False)
        except Exception as exc:
            log.exception("%s: %s", name, type(exc).__name__)
            return json.dumps({"erro": "Erro interno ao executar a ferramenta"}, ensure_ascii=False)


def product_summary(
    product: Any,
    promotion: Any | None,
    today: date,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": product.product_id,
        "nome": product.name,
        "categoria": "",
        "preco": format_brl(product.price_brl),
    }

    if product.is_available:
        result["disponibilidade"] = "disponível"
        result["unidades_em_estoque"] = product.stock_quantity
    elif product.status != "active":
        if product.status == "discontinued":
            result["disponibilidade"] = "descontinuado"
        elif product.status == "coming_soon":
            result["disponibilidade"] = "em breve (ainda não está à venda)"
        else:
            result["disponibilidade"] = "indisponível"
    else:
        result["disponibilidade"] = "indisponível (sem estoque)"

    if promotion and promotion.is_active:
        final = format_brl(
            (product.price_brl * Decimal(1 - promotion.discount_percent / 100)).quantize(
                Decimal("0.01")
            )
        )
        result["promocao"] = {
            "percentual": f"{promotion.discount_percent}%",
            "descricao": promotion.description,
            "preco_original": format_brl(product.price_brl),
            "preco_promocional": final,
        }

    return result


def _status_pt(status: str) -> str:
    return {
        "delivered": "entregue",
        "shipped": "enviado",
        "confirmed": "confirmado",
        "pending": "aguardando pagamento/processamento",
        "cancelled": "cancelado",
    }.get(status, status)


def _payment_method_pt(method: str) -> str:
    mapping = {
        "pix": "PIX",
        "boleto": "boleto",
        "debit": "débito",
        "credit_3x": "crédito em 3x",
        "credit_6x": "crédito em 6x",
        "credit_12x": "crédito em 12x",
    }
    return mapping.get(method, method)
