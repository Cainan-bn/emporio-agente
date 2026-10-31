from __future__ import annotations

import copy
import json
import logging
import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from emporio.data.repositories import (
    OrderRepository,
    ProductRepository,
    PromotionRepository,
)
from emporio.formatting import format_brl
from emporio.policies.retriever import PolicyRetriever

log = logging.getLogger(__name__)


_MAX_ARG_LEN = 500


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


_JSON_TYPES: dict[str, type | tuple[type, ...]] = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
}

_NUMERIC_TYPES = (int, float)


class ToolRegistry:
    def __init__(self, context: ToolContext, tools: list[Tool]) -> None:
        self._context = context
        self._tools = {t.name: t for t in tools}

    def schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in self._tools.values()
        ]

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def execute(self, name: str, arguments: str | dict[str, Any]) -> str:
        try:
            tool = self._tools.get(name)
            if tool is None:
                return _err(f"Ferramenta desconhecida: {name}")

            if isinstance(arguments, str):
                if len(arguments) > _MAX_ARG_LEN:
                    return _err("Texto muito longo nos argumentos")
                try:
                    args = json.loads(arguments)
                except json.JSONDecodeError as exc:
                    return _err(f"JSON inválido nos argumentos: {exc}")
            else:
                args = copy.deepcopy(arguments)

            if not isinstance(args, dict):
                return _err("Argumentos devem ser um objeto JSON")

            props = tool.parameters.get("properties", {})
            required = tool.parameters.get("required", [])

            for key in required:
                if key not in args or args[key] is None:
                    return _err(f"Argumento obrigatório ausente: {key}")

            for key, val in list(args.items()):
                if key not in props:
                    del args[key]
                    continue
                schema_type = props[key].get("type")
                if schema_type == "boolean" and val is not None:
                    if not isinstance(val, bool):
                        return _err(
                            f"Argumento {key}: esperado {schema_type}, "
                            f"recebido {type(val).__name__}"
                        )
                elif schema_type == "integer":
                    if isinstance(val, bool):
                        return _err(
                            f"Argumento {key}: esperado {schema_type}, "
                            f"recebido {type(val).__name__}"
                        )
                    if not isinstance(val, int):
                        return _err(
                            f"Argumento {key}: esperado {schema_type}, "
                            f"recebido {type(val).__name__}"
                        )
                elif schema_type == "number":
                    if isinstance(val, bool) or not isinstance(val, _NUMERIC_TYPES):
                        return _err(
                            f"Argumento {key}: esperado {schema_type}, "
                            f"recebido {type(val).__name__}"
                        )
                    if key in ("preco_max",):
                        if math.isnan(val) or val < 0:
                            return _err(f"{key} deve ser um número >= 0")
                elif schema_type is not None and val is not None:
                    py_type = _JSON_TYPES.get(schema_type)
                    if not isinstance(val, py_type):
                        return _err(
                            f"Argumento {key}: esperado {schema_type}, "
                            f"recebido {type(val).__name__}"
                        )

            result = tool.handler(self._context, args)
            return json.dumps(result, ensure_ascii=False)
        except Exception as exc:
            log.warning("tool=%s erro=%s", name, type(exc).__name__)
            return _err("Erro interno ao executar a ferramenta")


def _err(msg: str) -> str:
    return json.dumps({"erro": msg}, ensure_ascii=False)


def product_summary(
    product: Any,
    promotion: Any | None,
    today: date,
    category_name: str = "",
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": product.product_id,
        "nome": product.name,
        "categoria": category_name,
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
        from emporio.data.repositories import PromotionRepository

        final = PromotionRepository.final_price(product, promotion)
        result["promocao"] = {
            "percentual": f"{promotion.discount_percent}%",
            "descricao": promotion.description,
            "preco_original": format_brl(product.price_brl),
            "preco_promocional": format_brl(final),
        }

    return result


def _cat_name(ctx: ToolContext, category_id: int) -> str:
    for c in ctx.products.list_categories():
        if c.category_id == category_id:
            return c.name
    return ""


def _status_pt(status: str) -> str:
    return {
        "delivered": "entregue",
        "shipped": "enviado",
        "confirmed": "confirmado",
        "pending": "aguardando pagamento/processamento",
        "cancelled": "cancelado",
    }.get(status, status)


def _payment_method_pt(method: str) -> str:
    return {
        "pix": "PIX",
        "boleto": "boleto",
        "debit": "débito",
        "credit_3x": "crédito em 3x",
        "credit_6x": "crédito em 6x",
        "credit_12x": "crédito em 12x",
    }.get(method, method)
