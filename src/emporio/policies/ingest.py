from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pypdf


class PolicyLoadError(Exception):
    """Erro ao carregar o PDF de políticas."""


HEADER_PATTERN = re.compile(r"Empório da Música\s+Manual de Políticas e Procedimentos")
FOOTER_PATTERN = re.compile(r"Página\s+\d+")
EMAIL_PATTERN = re.compile(r"([\w.+-]+)@([\w.-]+)")
COVER_HEADER = "EMPÓRIO DA MÚSICA"


def ascii_email_domains(text: str) -> str:
    """Tira os acentos do domínio dos e-mails (ADR-009: o PDF traz `empóriodamusica`, inválido)."""

    def _fix(match: re.Match[str]) -> str:
        domain = unicodedata.normalize("NFKD", match.group(2))
        return f"{match.group(1)}@{''.join(c for c in domain if not unicodedata.combining(c))}"

    return EMAIL_PATTERN.sub(_fix, text)


def extract_pages(pdf_path: str | Path) -> list[str]:
    """Extrai cada página do PDF em modo layout, removendo cabeçalho/rodapé repetidos."""
    try:
        reader = pypdf.PdfReader(str(pdf_path))
    except Exception as exc:
        msg = f"Erro ao ler o PDF: {exc}"
        raise PolicyLoadError(msg) from exc

    if not reader.pages:
        msg = "PDF vazio ou sem páginas"
        raise PolicyLoadError(msg)

    pages: list[str] = []
    for page in reader.pages:
        raw = page.extract_text(extraction_mode="layout")
        lines: list[str] = []
        for line in raw.split("\n"):
            stripped = line.strip()
            if stripped and HEADER_PATTERN.fullmatch(stripped):
                continue
            if stripped and FOOTER_PATTERN.fullmatch(stripped):
                continue
            lines.append(line)
        text = "\n".join(lines)
        # remove trailing blank lines
        text = text.rstrip("\n")
        pages.append(ascii_email_domains(text))

    return pages
