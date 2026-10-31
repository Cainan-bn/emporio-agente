from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar

INTERNAL_SECTIONS: ClassVar[set[str]] = {"7.1", "7.2", "7.3", "10"}
PARENT_SECTIONS: ClassVar[set[str]] = {"4", "5", "6", "7", "8"}

SECTION_PATTERN = re.compile(r"^(\d+(?:\.\d+)?)\.?\s+([A-ZÁ-Ú][^:\n]*[A-Za-zÁ-Úá-ú0-9)])\s*$")
TOP_LEVEL_LABELS = {"1", "2", "3", "4", "5", "6", "7", "8", "9", "10"}


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

    # Cover page
    cover_text = pages[0] if pages else ""
    if cover_text:
        chunks.append(
            PolicyChunk(
                section_id="capa",
                title="Capa",
                parent_title=None,
                page=1,
                text=cover_text.strip(),
                internal=False,
            )
        )

    # Track section hierarchy for parent_title
    section_stack: list[tuple[str, str]] = []  # [(id, title)]

    current_id: str | None = None
    current_title: str | None = None
    current_page: int = 0
    current_lines: list[str] = []
    current_internal: bool = False

    for page_idx in range(1, len(pages)):
        page_text = pages[page_idx]
        lines = page_text.split("\n")
        for _line_num, line in enumerate(lines):
            m = SECTION_PATTERN.match(line.strip())
            if m:
                # Save previous section if it has content and is not a parent-only
                if current_id is not None and current_lines:
                    body = "\n".join(current_lines).strip()
                    if body and current_id not in PARENT_SECTIONS:
                        chunks.append(
                            PolicyChunk(
                                section_id=current_id,
                                title=current_title or "",
                                parent_title=_find_parent_title(current_id, section_stack),
                                page=current_page,
                                text=body,
                                internal=current_internal,
                            )
                        )

                # Start new section
                raw_id = m.group(1)
                raw_title = m.group(2).strip()
                parts = raw_id.split(".")
                if len(parts) >= 2:
                    parent_id = parts[0]
                    # push sub-section onto stack
                    if section_stack and section_stack[-1][0] == parent_id:
                        pass  # parent already on stack
                    else:
                        # find the parent
                        for i in range(len(section_stack) - 1, -1, -1):
                            if section_stack[i][0] == parent_id:
                                break
                        else:
                            pass
                    section_stack.append((raw_id, raw_title))
                else:
                    # top-level section
                    section_stack = [(raw_id, raw_title)]

                current_id = raw_id
                current_title = raw_title
                current_page = page_idx + 1
                current_lines = []
                current_internal = raw_id in INTERNAL_SECTIONS

                # Skip body that's on the same line (just the title)
                rest_of_line = line.strip()[m.end() :].strip()
                if rest_of_line:
                    current_lines.append(rest_of_line)
            else:
                if current_id is not None:
                    current_lines.append(line)

    # Save last section
    if current_id is not None and current_lines:
        body = "\n".join(current_lines).strip()
        if body and current_id not in PARENT_SECTIONS:
            chunks.append(
                PolicyChunk(
                    section_id=current_id,
                    title=current_title or "",
                    parent_title=_find_parent_title(current_id, section_stack),
                    page=current_page,
                    text=body,
                    internal=current_internal,
                )
            )

    return chunks


def _find_parent_title(section_id: str, stack: list[tuple[str, str]]) -> str | None:
    parts = section_id.split(".")
    if len(parts) <= 1:
        return None
    parent_id = parts[0]
    for sid, stitle in stack:
        if sid == parent_id:
            return stitle
    return None
