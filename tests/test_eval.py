from __future__ import annotations

import json
from pathlib import Path

import pytest

from emporio.llm import AssistantTurn, ToolCall
from evals.checks import Trace, contains, norm, run_checks, validate_case
from evals.judge import Judge
from evals.runner import load_cases, render_markdown, run_all, summarize, write_report

CASES_FILE = Path("evals/casos.yaml")


def test_norm_ignora_acento_caixa_e_espacos() -> None:
    assert norm("  Violão   NYLON Natural ") == "violao nylon natural"
    assert contains("Preço: R$ 1.234,56", "r$ 1.234,56")


def test_casos_dourados_validos_e_cobrem_o_exigido() -> None:
    cases, default_date = load_cases(CASES_FILE)
    assert len(cases) >= 15
    assert default_date == "2026-03-20"
    ids = {c["id"] for c in cases}
    exigidos = {
        "catalogo_violao_ate_1000",
        "preco_produto_especifico",
        "produto_inexistente",
        "produto_sem_estoque",
        "promocao_vigente",
        "promocao_expirada",
        "horario_e_endereco",
        "pedido_status_verificado",
        "pedido_email_incorreto",
        "pedido_inexistente",
        "devolucao_dentro_do_prazo",
        "devolucao_fora_do_prazo",
        "troca_por_defeito",
        "formas_de_pagamento",
        "fora_do_escopo_receita",
        "injecao_de_prompt",
        "desconto_indevido",
        "mensagem_ambigua",
    }
    assert exigidos <= ids


def test_validate_case_rejeita_campo_desconhecido_e_faltando() -> None:
    with pytest.raises(ValueError, match="desconhecidos"):
        validate_case({"id": "x", "categoria": "c", "turnos": ["a"], "deve_conterr": []})
    with pytest.raises(ValueError, match="obrigatório"):
        validate_case({"id": "x", "categoria": "c"})


def _trace(*replies: str, tools: tuple[str, ...] = (), fallback: bool = False) -> Trace:
    return Trace(replies=list(replies), tool_names=list(tools), fallback=fallback)


def test_checks_ferramentas() -> None:
    case = {
        "tools_obrigatorias": ["a"],
        "tools_um_de": ["b", "c"],
        "tools_proibidas": ["d"],
    }
    assert run_checks(case, _trace("ok", tools=("a", "c"))).passed
    falhas = run_checks(case, _trace("ok", tools=("d",))).failures
    assert len(falhas) == 3
    assert not run_checks({"nenhuma_tool": True}, _trace("ok", tools=("a",))).passed


def test_checks_texto() -> None:
    case = {
        "deve_conter": ["R$ 10,00"],
        "deve_conter_algum": [["sábado", "sabado"]],
        "nao_deve_conter": ["segredo"],
    }
    assert run_checks(case, _trace("Custa R$ 10,00 no SABADO")).passed
    assert not run_checks(case, _trace("Custa R$ 11,00 no sábado")).passed
    assert not run_checks(case, _trace("Custa R$ 10,00 no sábado", "o segredo")).passed
    # "deve_conter" olha só a resposta final; "nao_deve_conter" olha todas as respostas
    assert run_checks({"deve_conter": ["x"]}, _trace("x", "y")).passed is False
    assert not run_checks({"sem_contingencia": True}, _trace("ok", fallback=True)).passed


class _Scripted:
    def __init__(self, turns: list[AssistantTurn]) -> None:
        self._turns = list(turns)

    def complete(self, messages: list[dict], tools: list[dict]) -> AssistantTurn:
        return self._turns.pop(0) if self._turns else AssistantTurn("ok", [])


def test_judge_parse_e_falha_segura() -> None:
    aprovado = Judge(_Scripted([AssistantTurn('x {"aprovado": true, "motivo": "ok"} y', [])]))
    assert aprovado.evaluate("r", "t").approved
    reprovado = Judge(_Scripted([AssistantTurn('{"aprovado": false, "motivo": "inventou"}', [])]))
    assert not reprovado.evaluate("r", "t").approved
    lixo = Judge(_Scripted([AssistantTurn("não sei", [])])).evaluate("r", "t")
    assert not lixo.approved and "inválida" in lixo.reason


def test_run_all_end_to_end_com_modelo_falso(tmp_path: Path) -> None:
    cases = [
        {
            "id": "loja",
            "categoria": "loja",
            "turnos": ["onde fica a loja?"],
            "tools_obrigatorias": ["consultar_loja"],
            "deve_conter": ["14 de Maio"],
            "rubrica": "cita o endereço",
        },
        {"id": "falha", "categoria": "loja", "turnos": ["oi"], "deve_conter": ["inexistente"]},
    ]
    agent_model = _Scripted(
        [
            AssistantTurn(None, [ToolCall("c1", "consultar_loja", "{}")]),
            AssistantTurn("Rua 14 de Maio, 3200", []),
        ]
    )
    # um modelo por caso evita corrida entre threads no roteiro
    results = run_all(
        cases[:1],
        agent_model,
        Judge(_Scripted([AssistantTurn('{"aprovado": true, "motivo": "ok"}', [])])),
        "v1",
        "2026-03-20",
        workers=1,
    )
    assert results[0].passed and results[0].judge_approved is True
    assert results[0].tools == ["consultar_loja"]

    results += run_all(cases[1:], _Scripted([]), None, "v1", "2026-03-20", workers=1)
    assert not results[1].passed
    resumo = summarize(results)
    assert resumo["aprovados"] == 1 and resumo["total"] == 2

    meta = {
        "prompt": "v1",
        "model": "x/y",
        "judge_model": "j",
        "executado_em": "2026-11-01T10:30",
    }
    json_path, md_path = write_report(tmp_path, meta, results)
    assert json.loads(json_path.read_text())["resumo"]["aprovados"] == 1
    assert "❌" in md_path.read_text() and "1/2" in render_markdown(meta, results)


def test_caso_com_erro_de_execucao_nao_derruba_o_relatorio() -> None:
    case = {"id": "ruim", "categoria": "x", "turnos": ["oi"], "data_referencia": "nao-e-data"}
    result = run_all([case], _Scripted([]), None, "v1", "2026-03-20", workers=1)[0]
    assert not result.passed and result.error
