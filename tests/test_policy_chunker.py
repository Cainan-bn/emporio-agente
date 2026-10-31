from __future__ import annotations

from emporio.policies.chunker import split_sections
from emporio.policies.ingest import extract_pages

PAGES = extract_pages("data/políticas_da_loja.pdf")
CHUNKS = split_sections(PAGES)
BY_ID = {c.section_id: c for c in CHUNKS}

EXPECTED_IDS = {
    "capa",
    "1",
    "1.1",
    "1.2",
    "2",
    "3",
    "3.1",
    "4.1",
    "4.2",
    "4.3",
    "4.4",
    "5.1",
    "5.2",
    "5.3",
    "6.1",
    "6.2",
    "7.1",
    "7.2",
    "7.3",
    "8.1",
    "8.2",
    "8.3",
    "9",
    "10",
}


def test_all_ids_present() -> None:
    got = {c.section_id for c in CHUNKS}
    assert got == EXPECTED_IDS, f"Missing: {EXPECTED_IDS - got}, Extra: {got - EXPECTED_IDS}"


def test_section_5_2_contains_jadlog() -> None:
    assert "Jadlog" in BY_ID["5.2"].text


def test_section_5_2_contains_pac() -> None:
    assert "PAC" in BY_ID["5.2"].text


def test_section_3_contains_pix() -> None:
    assert "PIX" in BY_ID["3"].text


def test_section_3_contains_5_percent() -> None:
    assert "5%" in BY_ID["3"].text


def test_section_3_1_contains_80() -> None:
    assert "R$ 80,00" in BY_ID["3.1"].text


def test_section_4_1_contains_7_dias() -> None:
    assert "7 (sete) dias" in BY_ID["4.1"].text


def test_section_4_2_contains_30_dias() -> None:
    assert "30 (trinta) dias" in BY_ID["4.2"].text


def test_section_2_contains_hours() -> None:
    assert "09:00" in BY_ID["2"].text
    assert "13:00" in BY_ID["2"].text


def test_internal_only_expected() -> None:
    internal = {c.section_id for c in CHUNKS if c.internal}
    assert internal == {"7.1", "7.2", "7.3", "10"}, f"Got: {internal}"


def test_citation_format() -> None:
    assert BY_ID["4.1"].citation == (
        "Manual de Políticas §4.1 — Direito de Arrependimento (Compras Online) (p. 4)"
    )


def test_capa_citation() -> None:
    assert BY_ID["capa"].citation == "Capa do Manual de Políticas"


def test_no_empty_chunks() -> None:
    empty = [c.section_id for c in CHUNKS if not c.text.strip()]
    assert not empty, f"Empty chunks: {empty}"
