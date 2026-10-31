from __future__ import annotations

from emporio.tools.base import Tool, ToolContext


def _handler(ctx: ToolContext, args: dict) -> dict:
    pergunta = args["pergunta"]
    hits = ctx.policies.search(pergunta, k=3, include_internal=False)

    if not hits:
        return {
            "trechos": [],
            "aviso": "Não encontrei esse assunto no manual de políticas.",
        }

    trechos = []
    for h in hits:
        trechos.append(
            {
                "secao": h.chunk.section_id,
                "titulo": h.chunk.title,
                "citacao": h.chunk.citation,
                "texto": h.chunk.text,
            }
        )

    return {"trechos": trechos}


TOOL = Tool(
    name="consultar_politicas",
    description=(
        "Consultar regras e políticas da loja: trocas, devoluções, pagamento, "
        "frete, garantia, promoções, privacidade. "
        "NÃO usar para consultar endereço, horário ou telefone (use consultar_loja). "
        "NÃO inclui seções internas de atendimento (tom de voz, fluxo)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "pergunta": {
                "type": "string",
                "description": "Pergunta em linguagem natural sobre as políticas",
            }
        },
        "required": ["pergunta"],
    },
    handler=_handler,
)
