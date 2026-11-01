from __future__ import annotations

from pathlib import Path

import pytest

from emporio.policies.ingest import PolicyLoadError, ascii_email_domains, extract_pages

PDF_PATH = Path("data/políticas_da_loja.pdf")


def test_extract_pages_count() -> None:
    pages = extract_pages(PDF_PATH)
    assert len(pages) == 8


def test_no_header_footer() -> None:
    pages = extract_pages(PDF_PATH)
    for i, p in enumerate(pages):
        assert "Manual de Políticas e Procedimentos" not in p, f"Header on page {i + 1}"
        assert f"Página {i + 1}" not in p, f"Footer on page {i + 1}"


def test_no_chopped_words() -> None:
    pages = extract_pages(PDF_PATH)
    for i, p in enumerate(pages):
        lines = p.split("\n")
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            # Single isolated words are OK (table cells, short labels)
            if " " not in stripped:
                if stripped.endswith(".") or len(stripped) <= 12:
                    continue
            assert " " in stripped, f"Page {i + 1} has short line: {stripped!r}"


def test_missing_pdf(tmp_path: Path) -> None:
    with pytest.raises(PolicyLoadError):
        extract_pages(tmp_path / "nonexistent.pdf")


def test_ascii_email_domains_only_touches_the_domain() -> None:
    assert ascii_email_domains("E-mail: contato@empóriodamusica.com.br.") == (
        "E-mail: contato@emporiodamusica.com.br."
    )
    assert ascii_email_domains("josé@jmail.com e Empório da Música") == (
        "josé@jmail.com e Empório da Música"
    )


def test_pdf_emails_have_no_accent() -> None:
    text = "\n".join(extract_pages(PDF_PATH))
    assert "contato@emporiodamusica.com.br" in text
    assert "empóriodamusica" not in text
