from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from dotenv import load_dotenv


def _parse_float_env(name: str, default: str) -> float:
    """Converte variável de ambiente para float, com mensagem de erro clara."""
    raw = os.getenv(name, default)
    try:
        return float(raw)
    except ValueError:
        msg = f"{name} deve ser um número, recebido {raw!r}"
        raise ValueError(msg) from None


@dataclass(frozen=True)
class Settings:
    """Configurações imutáveis carregadas de variáveis de ambiente."""

    openrouter_api_key: str
    openrouter_base_url: str
    model_id: str
    judge_model_id: str
    reference_date: date | None
    max_tool_iterations: int
    llm_timeout_seconds: int
    llm_max_retries: int
    llm_temperature: float
    prompt_version: str
    log_level: str
    llm_max_tokens: int = 1024


def _parse_int_env(name: str, default: str) -> int:
    """Converte variável de ambiente para int, com mensagem de erro clara."""
    raw = os.getenv(name, default)
    try:
        return int(raw)
    except ValueError:
        msg = f"{name} deve ser um inteiro, recebido {raw!r}"
        raise ValueError(msg) from None


def _parse_temperature() -> float:
    """LLM_TEMPERATURE precisa estar em [0, 2] (nan/inf/negativos são rejeitados)."""
    value = _parse_float_env("LLM_TEMPERATURE", "0.2")
    if not 0.0 <= value <= 2.0:
        msg = f"LLM_TEMPERATURE deve estar entre 0 e 2, recebido {value!r}"
        raise ValueError(msg)
    return value


def load_settings(env_file: str | Path | None = None) -> Settings:
    """Carrega configurações a partir de um arquivo .env e variáveis de ambiente."""
    # só o .env do diretório atual: o padrão do python-dotenv sobe pastas e pegaria um .env alheio
    load_dotenv(dotenv_path=env_file if env_file is not None else Path.cwd() / ".env")

    raw_date = os.getenv("REFERENCE_DATE", "")
    reference_date: date | None = None
    if raw_date:
        try:
            reference_date = date.fromisoformat(raw_date)
        except ValueError:
            msg = f"REFERENCE_DATE inválida: {raw_date!r}. Use o formato ISO aaaa-mm-dd."
            raise ValueError(msg) from None

    return Settings(
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY", ""),
        openrouter_base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        model_id=os.getenv("MODEL_ID", "anthropic/claude-haiku-5.5"),
        judge_model_id=os.getenv("JUDGE_MODEL_ID", "anthropic/claude-sonnet-5.5"),
        reference_date=reference_date,
        max_tool_iterations=_parse_int_env("MAX_TOOL_ITERATIONS", "6"),
        llm_timeout_seconds=_parse_int_env("LLM_TIMEOUT_SECONDS", "30"),
        llm_max_retries=_parse_int_env("LLM_MAX_RETRIES", "3"),
        llm_temperature=_parse_temperature(),
        prompt_version=os.getenv("PROMPT_VERSION", "v1"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        llm_max_tokens=_parse_int_env("LLM_MAX_TOKENS", "1024"),
    )
