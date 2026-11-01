"""Gera as transcrições de exemplo em examples/*.md rodando o agente real.

Uso: python scripts/gerar_exemplos.py   (precisa de OPENCODE_API_KEY no .env)

Faz chamadas reais ao modelo. A data de referência é fixa para o resultado ser reproduzível.
"""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from emporio.agent import AgentReply  # noqa: E402
from emporio.cli import _mask_email, build_agent  # noqa: E402
from emporio.config import load_settings  # noqa: E402

OUT_DIR = ROOT / "examples"
REFERENCE_DATE = date(2026, 2, 20)
MAX_RESULT_CHARS = 1500

SCENARIOS: list[dict] = [
    {
        "file": "01-catalogo-violoes.md",
        "title": "Consulta de catálogo",
        "goal": "Busca de produtos com filtro de preço.",
        "turns": ["Quais opções de violões disponíveis custando até R$1000?"],
    },
    {
        "file": "02-endereco-da-loja.md",
        "title": "Informação geral",
        "goal": "Dados fixos da loja, vindos do manual de políticas.",
        "turns": ["Qual o endereço da loja?"],
    },
    {
        "file": "03-preco-takamine-gd20.md",
        "title": "Consulta de preço",
        "goal": "Preço e disponibilidade de um produto específico.",
        "turns": ["Quanto custa o Takamine GD20?"],
    },
    {
        "file": "04-devolucao-pedido.md",
        "title": "Cenário não trivial: cruzamento de dados e política",
        "goal": (
            "Cruza o pedido (dados + verificação por e-mail) com a política de arrependimento. "
            "O agente pede os dados, consulta o pedido e a política e não aprova a devolução "
            "por conta própria."
        ),
        "turns": [
            "Me arrependi da minha compra, posso devolver meu pedido?",
            "É o pedido 7, meu e-mail é leticia.rocha@jmail.com",
        ],
    },
]


def _json(value: object) -> str:
    return _mask_email(json.dumps(value, ensure_ascii=False, indent=2))


def _tool_block(reply: AgentReply) -> list[str]:
    lines: list[str] = []
    for i, call in enumerate(reply.tool_calls, start=1):
        result = _json(call.result)
        if len(result) > MAX_RESULT_CHARS:
            result = result[:MAX_RESULT_CHARS] + "\n… [resultado truncado]"
        lines += [
            f"**🔧 Chamada {i}: `{call.name}`**",
            "",
            "```json",
            _json(call.arguments),
            "```",
            "",
            "<details><summary>Resultado da ferramenta</summary>",
            "",
            "```json",
            result,
            "```",
            "",
            "</details>",
            "",
        ]
    return lines


def render(scenario: dict, replies: list[AgentReply], meta: dict) -> str:
    lines = [
        f"# {scenario['title']}",
        "",
        scenario["goal"],
        "",
        f"- Modelo: `{meta['model']}` · Prompt: `{meta['prompt']}`",
        f'- Data de referência ("hoje"): {REFERENCE_DATE:%d/%m/%Y}',
        f"- Gerado em {meta['generated']} por `scripts/gerar_exemplos.py` (conversa real)",
        "- Os dados são fictícios; e-mails aparecem mascarados nas chamadas de ferramenta.",
        "",
        "---",
        "",
    ]
    for user, reply in zip(scenario["turns"], replies, strict=True):
        lines += [f"**Cliente:** {user}", ""]
        if reply.tool_calls:
            lines += _tool_block(reply)
        else:
            lines += ["_Nenhuma ferramenta chamada neste turno._", ""]
        lines += [f"**Téo:** {reply.text}", "", "---", ""]
    return "\n".join(lines).rstrip("\n") + "\n"


def main() -> int:
    settings = load_settings()
    if not settings.opencode_api_key:
        print("Erro: OPENCODE_API_KEY não configurada (.env na raiz).", file=sys.stderr)
        return 2
    settings = replace(settings, reference_date=REFERENCE_DATE)
    meta = {
        "model": settings.model_id,
        "prompt": settings.prompt_version,
        "generated": datetime.now().strftime("%d/%m/%Y %H:%M"),
    }
    OUT_DIR.mkdir(exist_ok=True)
    for scenario in SCENARIOS:
        agent = build_agent(settings)  # conversa nova por cenário
        replies = [agent.reply(turn) for turn in scenario["turns"]]
        path = OUT_DIR / scenario["file"]
        path.write_text(render(scenario, replies, meta), encoding="utf-8")
        tools = [c.name for r in replies for c in r.tool_calls]
        print(f"{path.relative_to(ROOT)}  ferramentas: {tools}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
