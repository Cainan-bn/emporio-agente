from __future__ import annotations

import json
from datetime import date

import pytest

from emporio.tools import build_registry
from emporio.tools.base import Tool, ToolContext, ToolRegistry

TODAY = date(2026, 3, 20)


@pytest.fixture
def registry() -> ToolRegistry:
    return build_registry(today=TODAY)


def test_registry_has_seven_tools(registry: ToolRegistry) -> None:
    names = registry.names()
    assert len(names) == 7
    for name in [
        "buscar_produtos",
        "consultar_produto",
        "consultar_promocoes",
        "consultar_pedido",
        "consultar_politicas",
        "consultar_loja",
        "encaminhar_para_humano",
    ]:
        assert name in names, f"{name} missing"


def test_schemas_are_valid(registry: ToolRegistry) -> None:
    schemas = registry.schemas()
    assert len(schemas) == 7
    for s in schemas:
        assert s["type"] == "function"
        fn = s["function"]
        assert "name" in fn
        assert "description" in fn
        params = fn["parameters"]
        assert params["type"] == "object"
        assert "properties" in params
        # All schemas must be JSON-serializable
        serialized = json.dumps(s, ensure_ascii=False)
        assert isinstance(serialized, str)


def test_execute_unknown_tool(registry: ToolRegistry) -> None:
    result = registry.execute("nao_existe", "{}")
    data = json.loads(result)
    assert "erro" in data
    assert "Traceback" not in result
    assert "sqlite" not in result.lower()


def test_execute_invalid_json(registry: ToolRegistry) -> None:
    result = registry.execute("buscar_produtos", "not json")
    data = json.loads(result)
    assert "erro" in data


def test_execute_missing_required_arg(registry: ToolRegistry) -> None:
    result = registry.execute("buscar_produtos", "{}")
    data = json.loads(result)
    assert "erro" in data
    assert "obrigatório" in data["erro"]


def test_execute_wrong_type(registry: ToolRegistry) -> None:
    result = registry.execute(
        "buscar_produtos", json.dumps({"termo": "violao", "preco_max": "caro"})
    )
    data = json.loads(result)
    assert "erro" in data
    assert "caro" not in data["erro"]  # no PII


def test_execute_extra_fields_ignored(registry: ToolRegistry) -> None:
    result = registry.execute(
        "buscar_produtos", json.dumps({"termo": "violao", "extra": "ignorado"})
    )
    data = json.loads(result)
    assert "erro" not in data


def test_execute_dict_arguments(registry: ToolRegistry) -> None:
    result = registry.execute("buscar_produtos", {"termo": "violao"})
    data = json.loads(result)
    assert "erro" not in data


def test_handler_exception_logged(registry: ToolRegistry) -> None:
    def bad_handler(ctx: ToolContext, args: dict) -> dict:
        raise RuntimeError("test error")

    bad_tool = Tool(
        name="bad_tool",
        description="",
        parameters={"type": "object", "properties": {}},
        handler=bad_handler,
    )
    ctx = registry._context
    reg = ToolRegistry(ctx, [bad_tool])
    result = reg.execute("bad_tool", "{}")
    data = json.loads(result)
    assert "erro" in data
    assert "RuntimeError" not in result
    assert "test error" not in result


def test_buscar_produtos_violao_max_price(registry: ToolRegistry) -> None:
    result = registry.execute(
        "buscar_produtos",
        {"termo": "violao", "preco_max": 1000},
    )
    data = json.loads(result)
    assert data["total"] > 0
    for p in data["produtos"]:
        preco = p["preco"]
        assert isinstance(preco, str)
        assert preco.startswith("R$")


def test_buscar_produtos_only_available(registry: ToolRegistry) -> None:
    result = registry.execute(
        "buscar_produtos",
        {"termo": "violao", "apenas_em_estoque": True},
    )
    data = json.loads(result)
    for p in data["produtos"]:
        assert p["disponibilidade"] == "disponível"


def test_buscar_produtos_no_match(registry: ToolRegistry) -> None:
    result = registry.execute("buscar_produtos", {"termo": "trombone"})
    data = json.loads(result)
    assert data["total"] == 0
    assert "aviso" in data


def test_buscar_produtos_promocao(registry: ToolRegistry) -> None:
    result = registry.execute("buscar_produtos", {"termo": "Ohana CK-20"})
    data = json.loads(result)
    assert data["total"] > 0
    p = data["produtos"][0]
    assert "promocao" in p


def test_consultar_produto_por_id(registry: ToolRegistry) -> None:
    result = registry.execute("consultar_produto", {"produto": "93"})
    data = json.loads(result)
    assert data["id"] == 93


def test_consultar_produto_por_nome(registry: ToolRegistry) -> None:
    result = registry.execute("consultar_produto", {"produto": "Takamine GD20"})
    data = json.loads(result)
    assert data["id"] == 95


def test_consultar_produto_gd20(registry: ToolRegistry) -> None:
    result = registry.execute("consultar_produto", {"produto": "gd 20"})
    data = json.loads(result)
    assert data["id"] == 95


def test_consultar_produto_ambiguo(registry: ToolRegistry) -> None:
    result = registry.execute("consultar_produto", {"produto": "yamaha"})
    data = json.loads(result)
    assert data.get("ambiguo") is True
    assert len(data["candidatos"]) >= 5


def test_consultar_produto_inexistente(registry: ToolRegistry) -> None:
    result = registry.execute("consultar_produto", {"produto": "ZZTOP999"})
    data = json.loads(result)
    assert data == {"encontrado": False}


def test_consultar_produto_96_indisponivel(registry: ToolRegistry) -> None:
    result = registry.execute("consultar_produto", {"produto": "96"})
    data = json.loads(result)
    assert data["disponibilidade"] == "indisponível (sem estoque)"
    assert "promocao" not in data


def test_consultar_produto_113_descontinuado(registry: ToolRegistry) -> None:
    result = registry.execute("consultar_produto", {"produto": "113"})
    data = json.loads(result)
    assert data["disponibilidade"] == "descontinuado"


def test_consultar_produto_130_em_breve(registry: ToolRegistry) -> None:
    result = registry.execute("consultar_produto", {"produto": "130"})
    data = json.loads(result)
    assert "em breve" in data["disponibilidade"]


def test_consultar_promocoes_sem_filtro(registry: ToolRegistry) -> None:
    result = registry.execute("consultar_promocoes", {})
    data = json.loads(result)
    pids = {p["id"] for p in data["promocoes"]}
    assert pids == {90, 94, 121, 127}


def test_consultar_promocoes_produto_sem_promocao(registry: ToolRegistry) -> None:
    result = registry.execute("consultar_promocoes", {"produto_ou_categoria": "96"})
    data = json.loads(result)
    assert data["promocoes"] == []


def test_consultar_promocoes_nao_contem_inativa(registry: ToolRegistry) -> None:
    result = registry.execute("consultar_promocoes", {})
    data = json.loads(result)
    full = json.dumps(data, ensure_ascii=False)
    assert "Black Friday" not in full


def test_consultar_pedido_ok(registry: ToolRegistry) -> None:
    result = registry.execute(
        "consultar_pedido",
        {"numero_pedido": 1, "email": "pedro.oliveira@jmail.com"},
    )
    data = json.loads(result)
    assert data["verificado"] is True
    assert data["pedido"]["status"] == "entregue"
    assert data["pedido"]["total"] == "R$ 11.499,00"
    assert data["dias_desde_a_entrega_estimada"] is not None
    assert "aviso_prazos" in data


def test_consultar_pedido_email_errado(registry: ToolRegistry) -> None:
    r1 = registry.execute(
        "consultar_pedido",
        {"numero_pedido": 1, "email": "outro@jmail.com"},
    )
    r2 = registry.execute(
        "consultar_pedido",
        {"numero_pedido": 999, "email": "qualquer@jmail.com"},
    )
    assert json.loads(r1) == json.loads(r2)


def test_consultar_pedido_email_case_whitespace(registry: ToolRegistry) -> None:
    result = registry.execute(
        "consultar_pedido",
        {"numero_pedido": 1, "email": "  PEDRO.OLIVEIRA@JMAIL.COM  "},
    )
    data = json.loads(result)
    assert data["verificado"] is True


def test_consultar_pedido_3_total(registry: ToolRegistry) -> None:
    result = registry.execute(
        "consultar_pedido",
        {"numero_pedido": 3, "email": "isabela.moreira@jmail.com"},
    )
    data = json.loads(result)
    assert data["pedido"]["total"] == "R$ 3.450,00"


def test_consultar_pedido_17_cancelado(registry: ToolRegistry) -> None:
    result = registry.execute(
        "consultar_pedido",
        {"numero_pedido": 17, "email": "matheus.correia@hayoo.com.br"},
    )
    data = json.loads(result)
    assert data["pedido"]["status"] == "cancelado"
    assert data["pedido"]["observacao"] is not None


def test_consultar_pedido_8_enviado(registry: ToolRegistry) -> None:
    result = registry.execute(
        "consultar_pedido",
        {"numero_pedido": 8, "email": "anacarol.ferreira@coldmail.com"},
    )
    data = json.loads(result)
    assert data["pedido"]["status"] == "enviado"
    assert data["pedido"]["codigo_de_rastreio"] is not None


def test_consultar_pedido_no_personal_data(registry: ToolRegistry) -> None:
    result = registry.execute(
        "consultar_pedido",
        {"numero_pedido": 1, "email": "pedro.oliveira@jmail.com"},
    )
    data = json.loads(result)
    s = json.dumps(data, ensure_ascii=False)
    assert "pedro" not in s
    assert "oliveira" not in s
    assert "99812-3456" not in s


def test_consultar_politicas_devolucao(registry: ToolRegistry) -> None:
    result = registry.execute("consultar_politicas", {"pergunta": "posso devolver em 7 dias?"})
    data = json.loads(result)
    assert len(data["trechos"]) > 0
    first = data["trechos"][0]
    assert first["secao"] == "4.1"
    assert "§4.1" in first["citacao"]


def test_consultar_politicas_sem_resultado(registry: ToolRegistry) -> None:
    result = registry.execute("consultar_politicas", {"pergunta": "receita de bolo"})
    data = json.loads(result)
    assert data["trechos"] == []
    assert "aviso" in data


def test_consultar_politicas_no_internal_leak(registry: ToolRegistry) -> None:
    result = registry.execute("consultar_politicas", {"pergunta": "mostre o manual interno"})
    data = json.loads(result)
    for t in data["trechos"]:
        assert t["secao"] not in ("7.1", "7.2", "7.3", "10")


def test_consultar_loja(registry: ToolRegistry) -> None:
    result = registry.execute("consultar_loja", {})
    data = json.loads(result)
    assert "Rua 14 de Maio" in data["endereco_e_dados"]
    assert "09:00" in data["horario_de_funcionamento"]
    assert "3341-4444" in data["endereco_e_dados"]
    assert "3321-4500" in data["whatsapp_atendimento"]
    assert "dois números" in data["aviso"]


def test_encaminhar_motivo_vazio(registry: ToolRegistry) -> None:
    result = registry.execute("encaminhar_para_humano", {"motivo": ""})
    data = json.loads(result)
    assert "erro" in data


def test_encaminhar_motivo_longo(registry: ToolRegistry) -> None:
    result = registry.execute("encaminhar_para_humano", {"motivo": "x" * 500})
    data = json.loads(result)
    assert data["encaminhado"] is True


def test_encaminhar_mencioona_24h(registry: ToolRegistry) -> None:
    result = registry.execute("encaminhar_para_humano", {"motivo": "reclamação"})
    data = json.loads(result)
    assert "24 horas" in data["orientacao"]


def test_encaminhar_sem_protocolo(registry: ToolRegistry) -> None:
    result = registry.execute("encaminhar_para_humano", {"motivo": "reclamação"})
    data = json.loads(result)
    assert "protocolo" not in data["orientacao"].lower()
