from __future__ import annotations

import logging

from emporio.tools.base import Tool, ToolContext

log = logging.getLogger(__name__)


def _handler(ctx: ToolContext, args: dict) -> dict:
    motivo = args.get("motivo", "")
    if not motivo or not motivo.strip():
        return {"erro": "O motivo do encaminhamento não pode estar vazio."}

    if len(motivo) > 300:
        motivo = motivo[:300]

    log.info("handoff motivo_len=%d", len(motivo))

    return {
        "encaminhado": True,
        "orientacao": (
            "Vou te encaminhar para a equipe humana. "
            "Entre em contato pelo WhatsApp (67) 3321-4500 "
            "ou e-mail contato@emporiodamusica.com.br. "
            "O retorno ocorre em até 24 horas úteis (Manual §7.3)."
        ),
    }


TOOL = Tool(
    name="encaminhar_para_humano",
    description=(
        "Encaminhar o cliente para um atendente humano quando: "
        "o assistente não tem o dado solicitado, "
        "não tem autoridade para decidir (ex.: devolução fora do prazo, "
        "reclamação), ou ocorreu um erro na execução. "
        "NÃO usar como primeira opção — sempre tentar resolver com as outras ferramentas antes. "
        "NÃO inventar número de protocolo ou chamado (não há sistema de tickets)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "motivo": {
                "type": "string",
                "description": "Motivo do encaminhamento (máx. 300 caracteres)",
            }
        },
        "required": ["motivo"],
    },
    handler=_handler,
)
