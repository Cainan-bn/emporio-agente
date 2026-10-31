from __future__ import annotations

from emporio.text import compact, normalize


def test_normalize_basic() -> None:
    assert normalize("Violão") == "violao"
    assert normalize("VIOLÃO") == "violao"
    assert normalize("  Gd  20  ") == "gd 20"
    assert normalize("Takamine GD20") == "takamine gd20"
    assert normalize("ukulele") == "ukulele"


def test_normalize_removes_accents() -> None:
    assert normalize("Ação") == "acao"
    assert normalize("João Silva") == "joao silva"
    assert normalize("Letícia") == "leticia"


def test_normalize_drops_punctuation() -> None:
    assert normalize("GD-20") == "gd 20"
    assert normalize("C40 (Nylon)") == "c40 nylon"
    assert normalize("R$ 1.234,56") == "r 1 234 56"


def test_compact_basic() -> None:
    assert compact("GD 20") == "gd20"
    assert compact("gd20") == "gd20"
    assert compact("Gd-20") == "gd20"


def test_compact_violao() -> None:
    assert compact("Violão") == "violao"
    assert compact("VIOLÃO") == "violao"


def test_compact_empty() -> None:
    assert compact("") == ""
