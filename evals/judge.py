"""LLM-juiz: aplica a rubrica curta de um caso a uma conversa."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from emporio.llm import ChatModel, LLMError

_SYSTEM = """Você é um avaliador rigoroso de um agente de atendimento de uma loja de instrumentos \
musicais. Receberá a conversa, as ferramentas que o agente chamou (com os resultados) e uma \
RUBRICA. Aprove SOMENTE se a última resposta do agente cumpre TODA a rubrica e não contradiz \
os resultados das ferramentas. Dados que não aparecem nos resultados das ferramentas são \
invenção. Responda apenas com JSON: {"aprovado": true|false, "motivo": "uma frase"}."""

_MAX_RESULT_CHARS = 1500


@dataclass(frozen=True)
class Verdict:
    approved: bool
    reason: str


def _extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError("sem JSON")
    return json.loads(match.group(0))


class Judge:
    def __init__(self, model: ChatModel) -> None:
        self._model = model

    def evaluate(self, rubric: str, transcript: str) -> Verdict:
        messages = [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": f"RUBRICA:\n{rubric.strip()}\n\nCONVERSA:\n{transcript}"},
        ]
        try:
            content = self._model.complete(messages, []).content or ""
            data = _extract_json(content)
            return Verdict(bool(data["aprovado"]), str(data.get("motivo", "")).strip())
        except (LLMError, ValueError, KeyError, TypeError) as exc:
            return Verdict(False, f"juiz indisponível ou resposta inválida ({type(exc).__name__})")


def format_transcript(turns: list[tuple[str, str, list[tuple[str, dict, dict]]]]) -> str:
    """turns: (fala do cliente, resposta do agente, [(tool, argumentos, resultado)])."""
    lines: list[str] = []
    for user, answer, tools in turns:
        lines.append(f"CLIENTE: {user}")
        for name, args, result in tools:
            shown = json.dumps(result, ensure_ascii=False)[:_MAX_RESULT_CHARS]
            lines.append(f"  [ferramenta {name} {json.dumps(args, ensure_ascii=False)}] -> {shown}")
        lines.append(f"AGENTE: {answer}")
    return "\n".join(lines)
