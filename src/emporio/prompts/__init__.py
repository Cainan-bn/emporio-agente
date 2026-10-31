from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from emporio.formatting import format_date

_VALID_VERSION = re.compile(r"^v\d+$")
_PROMPTS_DIR = Path(__file__).resolve().parent


class PromptNotFoundError(FileNotFoundError):
    """Versão de prompt não encontrada ou inválida."""


def load_system_prompt(version: str, today: date) -> str:
    """Carrega o prompt versionado de prompts/{version}.md e substitui {hoje}."""
    if not _VALID_VERSION.match(version):
        msg = f"Formato de versão inválido: {version!r}"
        raise PromptNotFoundError(msg)

    path = _PROMPTS_DIR / f"{version}.md"
    if not path.exists():
        msg = f"Prompt {version} não encontrado em {path}"
        raise PromptNotFoundError(msg)

    text = path.read_text(encoding="utf-8")
    text = text.replace("{hoje}", format_date(today))
    return text
