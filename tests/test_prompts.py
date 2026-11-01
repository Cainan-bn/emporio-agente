from __future__ import annotations

from datetime import date

import pytest

from emporio.prompts import PromptNotFoundError, load_system_prompt


def test_v1_loads() -> None:
    prompt = load_system_prompt("v1", date(2026, 3, 20))
    assert len(prompt) > 100
    assert "20/03/2026" in prompt


def test_v1_contains_key_rules() -> None:
    prompt = load_system_prompt("v1", date(2026, 3, 20))
    assert "Nunca invente" in prompt
    assert "Privacidade" in prompt
    assert "Fora do escopo" in prompt
    assert "Segurança" in prompt
    assert "Téo" in prompt


def test_v1_has_today() -> None:
    prompt = load_system_prompt("v1", date(2026, 12, 25))
    assert "25/12/2026" in prompt


def test_invalid_version_format() -> None:
    with pytest.raises(PromptNotFoundError):
        load_system_prompt("../x", date.today())


def test_version_traversal() -> None:
    with pytest.raises(PromptNotFoundError):
        load_system_prompt("v1; rm", date.today())


def test_nonexistent_version() -> None:
    with pytest.raises(PromptNotFoundError):
        load_system_prompt("v999", date.today())


def test_empty_version() -> None:
    with pytest.raises(PromptNotFoundError):
        load_system_prompt("", date.today())


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_every_version_has_today_and_key_rules(version: str) -> None:
    prompt = load_system_prompt(version, date(2026, 3, 20))
    assert "20/03/2026" in prompt and "{hoje}" not in prompt
    assert "Nunca invente" in prompt and "Privacidade" in prompt


def test_v2_never_confirms_exchange_before_review() -> None:
    prompt = load_system_prompt("v2", date(2026, 3, 20))
    assert "nunca confirme a troca" in prompt
