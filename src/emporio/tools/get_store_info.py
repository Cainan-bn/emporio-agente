from __future__ import annotations

from emporio.tools.base import Tool, ToolContext


def _handler(ctx: ToolContext, args: dict) -> dict:
    s12 = ctx.policies.get_section("1.2")
    s2 = ctx.policies.get_section("2")
    s7 = ctx.policies.get_section("7")

    citacoes = []
    if s12:
        citacoes.append(s12.citation)
    if s2:
        citacoes.append(s2.citation)
    if s7:
        citacoes.append(s7.citation)

    return {
        "endereco_e_dados": s12.text if s12 else "",
        "horario_de_funcionamento": s2.text if s2 else "",
        "whatsapp_atendimento": s7.text if s7 else "",
        "aviso": (
            "O manual traz dois números de telefone diferentes (loja e WhatsApp); "
            "informe os dois, rotulados como aparecem."
        ),
        "citacoes": citacoes,
    }


TOOL = Tool(
    name="consultar_loja",
    description=(
        "Consultar informações fixas da loja: endereço (Rua 14 de Maio), "
        "horário de funcionamento (seg-sex 09-18h, sáb 09-13h), "
        "telefone (3341-4444) e WhatsApp (3321-4500). "
        "NÃO usar para regras de troca/devolução/pagamento (use consultar_politicas)."
    ),
    parameters={
        "type": "object",
        "properties": {},
    },
    handler=_handler,
)
