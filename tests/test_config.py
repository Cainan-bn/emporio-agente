from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from emporio.config import Settings, load_settings

ENV_VARS = [
    "OPENCODE_API_KEY",
    "OPENCODE_BASE_URL",
    "MODEL_ID",
    "JUDGE_MODEL_ID",
    "REFERENCE_DATE",
    "MAX_TOOL_ITERATIONS",
    "LLM_TIMEOUT_SECONDS",
    "LLM_MAX_RETRIES",
    "LOG_LEVEL",
]


def _make_env(tmp_path: Path, content: str = "") -> Path:
    env_file = tmp_path / ".env"
    env_file.write_text(content)
    return env_file


def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def test_default_values(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    env_file = _make_env(tmp_path)
    settings = load_settings(env_file)
    assert settings.opencode_api_key == ""
    assert settings.opencode_base_url == "https://opencode.ai/inference/go/openai/v1"
    assert settings.model_id == "deepseek-v4.1-flash"
    assert settings.judge_model_id == "deepseek-v4.1-flash"
    assert settings.reference_date is None
    assert settings.max_tool_iterations == 6
    assert settings.llm_timeout_seconds == 30
    assert settings.llm_max_retries == 3
    assert settings.log_level == "INFO"


def test_environment_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("OPENCODE_API_KEY", "sk-test-key")
    monkeypatch.setenv("MODEL_ID", "custom-model")
    monkeypatch.setenv("MAX_TOOL_ITERATIONS", "10")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    env_file = _make_env(tmp_path)
    settings = load_settings(env_file)
    assert settings.opencode_api_key == "sk-test-key"
    assert settings.model_id == "custom-model"
    assert settings.max_tool_iterations == 10
    assert settings.log_level == "DEBUG"


def test_reference_date_valid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    env_file = _make_env(tmp_path, "REFERENCE_DATE=2026-03-15")
    settings = load_settings(env_file)
    assert settings.reference_date == date(2026, 3, 15)


def test_reference_date_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    env_file = _make_env(tmp_path, "REFERENCE_DATE=")
    settings = load_settings(env_file)
    assert settings.reference_date is None


def test_reference_date_invalid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    env_file = _make_env(tmp_path, "REFERENCE_DATE=31/02/2026")
    with pytest.raises(ValueError) as excinfo:
        load_settings(env_file)
    assert "REFERENCE_DATE" in str(excinfo.value)
    assert "31/02/2026" in str(excinfo.value)


def test_reference_date_garbage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    env_file = _make_env(tmp_path, "REFERENCE_DATE=not-a-date")
    with pytest.raises(ValueError) as excinfo:
        load_settings(env_file)
    assert "REFERENCE_DATE" in str(excinfo.value)
    assert "not-a-date" in str(excinfo.value)


def test_invalid_max_tool_iterations(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_TOOL_ITERATIONS", "abc")
    with pytest.raises(ValueError) as excinfo:
        load_settings()
    assert "MAX_TOOL_ITERATIONS" in str(excinfo.value)
    assert "abc" in str(excinfo.value)


def test_invalid_llm_timeout_seconds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "xyz")
    with pytest.raises(ValueError) as excinfo:
        load_settings()
    assert "LLM_TIMEOUT_SECONDS" in str(excinfo.value)
    assert "xyz" in str(excinfo.value)


def test_settings_is_frozen() -> None:
    settings = Settings(
        opencode_api_key="",
        opencode_base_url="https://opencode.ai/inference/go/openai/v1",
        model_id="test",
        judge_model_id="judge",
        reference_date=None,
        max_tool_iterations=6,
        llm_timeout_seconds=30,
        llm_max_retries=3,
        llm_temperature=0.2,
        prompt_version="v1",
        log_level="INFO",
    )
    with pytest.raises(AttributeError):
        settings.model_id = "changed"  # type: ignore[misc]


def test_llm_temperature_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    env_file = _make_env(tmp_path)
    settings = load_settings(env_file)
    assert settings.llm_temperature == 0.2


def test_llm_temperature_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    env_file = _make_env(tmp_path, "LLM_TEMPERATURE=0.5")
    settings = load_settings(env_file)
    assert settings.llm_temperature == 0.5


def test_prompt_version_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    env_file = _make_env(tmp_path)
    settings = load_settings(env_file)
    assert settings.prompt_version == "v1"


def test_prompt_version_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    env_file = _make_env(tmp_path, "PROMPT_VERSION=v2")
    settings = load_settings(env_file)
    assert settings.prompt_version == "v2"


def test_nao_carrega_env_de_diretorio_ancestral(tmp_path, monkeypatch) -> None:
    (tmp_path / ".env").write_text("MODEL_ID=modelo-do-pai\n")
    filho = tmp_path / "projeto"
    filho.mkdir()
    monkeypatch.chdir(filho)
    monkeypatch.delenv("MODEL_ID", raising=False)
    assert load_settings().model_id != "modelo-do-pai"


def test_carrega_env_do_diretorio_atual(tmp_path, monkeypatch) -> None:
    (tmp_path / ".env").write_text("MODEL_ID=modelo-local\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MODEL_ID", raising=False)
    assert load_settings().model_id == "modelo-local"
    monkeypatch.delenv("MODEL_ID", raising=False)


@pytest.mark.parametrize("valor", ["nan", "inf", "-1", "2.5", "abc"])
def test_temperatura_invalida(valor, monkeypatch) -> None:
    monkeypatch.setenv("LLM_TEMPERATURE", valor)
    with pytest.raises(ValueError, match="LLM_TEMPERATURE"):
        load_settings()


def test_max_tokens_padrao_e_invalido(monkeypatch) -> None:
    monkeypatch.delenv("LLM_MAX_TOKENS", raising=False)
    assert load_settings().llm_max_tokens == 1024
    monkeypatch.setenv("LLM_MAX_TOKENS", "muito")
    with pytest.raises(ValueError, match="LLM_MAX_TOKENS"):
        load_settings()
