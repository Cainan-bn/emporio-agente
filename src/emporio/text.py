from __future__ import annotations

import re
import unicodedata


def normalize(text: str) -> str:
    """Normaliza texto: NFKD → remove acentos → minúsculas → colapsa espaços e pontuação."""
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_only = nfkd.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_only.lower()
    cleaned = re.sub(r"[^a-z0-9\s]", " ", lowered)
    return re.sub(r"\s+", " ", cleaned).strip()


def compact(text: str) -> str:
    """Remove tudo que não for [a-z0-9]; ex.: 'GD 20' e 'gd20' → 'gd20'."""
    return re.sub(r"[^a-z0-9]", "", normalize(text))
