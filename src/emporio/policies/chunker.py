from __future__ import annotations

import re
from dataclasses import dataclass

INTERNAL_SECTIONS = frozenset({"7.1", "7.2", "7.3", "10"})

SECTION_PATTERN = re.compile(r"^(\d+(?:\.\d+)?)\.?\s+([A-ZÁ-Ú][^:\n]*[A-Za-zÁ-Úá-ú0-9)])\s*$")


@dataclass(frozen=True)
class PolicyChunk:
    section_id: str
    title: str
    parent_title: str | None
    page: int
    text: str
    internal: bool = False

    @property
    def citation(self) -> str:
        if self.section_id == "capa":
            return "Capa do Manual de Políticas"
        return f"Manual de Políticas §{self.section_id} — {self.title} (p. {self.page})"


def split_sections(pages: list[str]) -> list[PolicyChunk]:
    """Fragmenta páginas extraídas em chunks por seção numerada."""
    chunks: list[PolicyChunk] = []

    if pages and pages[0].strip():
        chunks.append(
            PolicyChunk(
                section_id="capa",
                title="Capa",
                parent_title=None,
                page=1,
                text=pages[0].strip(),
                internal=True,
            )
        )

    current_id: str | None = None
    current_title: str | None = None
    current_page: int = 0
    current_lines: list[str] = []
    current_internal: bool = False

    for page_idx in range(1, len(pages)):
        for line in pages[page_idx].split("\n"):
            m = SECTION_PATTERN.match(line.strip())
            if m:
                _close_section(
                    chunks, current_id, current_title, current_page, current_lines, current_internal
                )

                raw_id = m.group(1)
                raw_title = m.group(2).strip()
                current_id = raw_id
                current_title = raw_title
                current_page = page_idx + 1
                current_lines = []
                current_internal = raw_id in INTERNAL_SECTIONS

                rest_of_line = line.strip()[m.end() :].strip()
                if rest_of_line:
                    current_lines.append(rest_of_line)
            else:
                if current_id is not None:
                    current_lines.append(line)

    _close_section(chunks, current_id, current_title, current_page, current_lines, current_internal)

    return chunks


def _close_section(
    chunks: list[PolicyChunk],
    section_id: str | None,
    title: str | None,
    page: int,
    lines: list[str],
    internal: bool,
) -> None:
    if section_id is None:
        return
    body = "\n".join(lines).strip()
    if body:
        parent = _find_parent_title(section_id)
        chunks.append(
            PolicyChunk(
                section_id=section_id,
                title=title or "",
                parent_title=parent,
                page=page,
                text=body,
                internal=internal,
            )
        )


_PARENT_TITLES: dict[str, str] = {
    "1": "Sobre a Empório da Música",
    "2": "Horário de Funcionamento",
    "3": "Formas de Pagamento",
    "4": "Política de Trocas e Devoluções",
    "5": "Política de Frete e Entregas",
    "6": "Promoções e Descontos",
    "7": "Atendimento via WhatsApp",
    "8": "Garantia",
    "9": "Privacidade e Proteção de Dados",
    "10": "Disposições Finais",
}


def _find_parent_title(section_id: str) -> str | None:
    parts = section_id.split(".")
    if len(parts) <= 1:
        return None
    return _PARENT_TITLES.get(parts[0])
