"""Checagens determinísticas de um caso do eval (sem LLM)."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

KNOWN_KEYS = frozenset(
    {
        "id",
        "categoria",
        "descricao",
        "turnos",
        "data_referencia",
        "tools_obrigatorias",
        "tools_um_de",
        "tools_proibidas",
        "nenhuma_tool",
        "deve_conter",
        "deve_conter_algum",
        "nao_deve_conter",
        "nao_deve_conter_palavra",
        "nao_comeca_com",
        "sem_contingencia",
        "rubrica",
    }
)


def norm(text: str) -> str:
    """Minúsculas, sem acentos e com espaços colapsados (pontuação preservada)."""
    decomposed = unicodedata.normalize("NFKD", text.replace(" ", " "))
    plain = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", plain).strip().lower()


def contains(haystack: str, needle: str) -> bool:
    return norm(needle) in norm(haystack)


def contains_word(haystack: str, needle: str) -> bool:
    """Como `contains`, mas só como palavra inteira ("Ana" não casa com "analisar")."""
    pattern = rf"(?<!\w){re.escape(norm(needle))}(?!\w)"
    return re.search(pattern, norm(haystack)) is not None


@dataclass(frozen=True)
class Trace:
    """O que o agente fez numa conversa: respostas, ferramentas e se houve contingência."""

    replies: list[str]
    tool_names: list[str]
    fallback: bool = False


@dataclass
class CheckResult:
    failures: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.failures


def validate_case(case: dict[str, Any]) -> None:
    """Falha cedo com mensagem clara se o caso tiver campo desconhecido ou faltando."""
    unknown = set(case) - KNOWN_KEYS
    if unknown:
        raise ValueError(f"Caso {case.get('id')!r}: campos desconhecidos {sorted(unknown)}")
    for required in ("id", "categoria", "turnos"):
        if not case.get(required):
            raise ValueError(f"Caso {case.get('id')!r}: campo obrigatório ausente: {required}")


def run_checks(case: dict[str, Any], trace: Trace) -> CheckResult:
    result = CheckResult()
    final = trace.replies[-1] if trace.replies else ""
    everything = "\n".join(trace.replies)
    called = set(trace.tool_names)

    for tool in case.get("tools_obrigatorias", []):
        if tool not in called:
            result.failures.append(f"não chamou a ferramenta obrigatória {tool}")
    one_of = case.get("tools_um_de", [])
    if one_of and not called & set(one_of):
        result.failures.append(f"não chamou nenhuma de {one_of}")
    for tool in case.get("tools_proibidas", []):
        if tool in called:
            result.failures.append(f"chamou a ferramenta proibida {tool}")
    if case.get("nenhuma_tool") and called:
        result.failures.append(f"chamou ferramentas ({sorted(called)}) num caso sem ferramentas")

    for snippet in case.get("deve_conter", []):
        if not contains(final, snippet):
            result.failures.append(f"resposta final não contém {snippet!r}")
    for group in case.get("deve_conter_algum", []):
        if not any(contains(final, s) for s in group):
            result.failures.append(f"resposta final não contém nenhum de {group}")
    for snippet in case.get("nao_deve_conter", []):
        if contains(everything, snippet):
            result.failures.append(f"resposta contém o trecho proibido {snippet!r}")
    for word in case.get("nao_deve_conter_palavra", []):
        if contains_word(everything, word):
            result.failures.append(f"resposta contém a palavra proibida {word!r}")
    opening = norm(final).lstrip(" \"'*_«“")
    for prefix in case.get("nao_comeca_com", []):
        if opening.startswith(norm(prefix)):
            result.failures.append(f"resposta final começa com {prefix!r}")
    if case.get("sem_contingencia") and trace.fallback:
        result.failures.append("o agente caiu na mensagem de contingência")
    return result
