from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

import openai
from openai import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError

from emporio.config import Settings

log = logging.getLogger(__name__)

_RETRYABLE = (RateLimitError, APITimeoutError, APIConnectionError)
_RETRY_STATUSES = {500, 502, 503, 504}
_BACKOFF_BASE = 1.0
_BACKOFF_MAX = 8.0

_MSG_REJECTED = "O modelo de IA recusou a requisição. Tente novamente em alguns instantes."
_MSG_EXHAUSTED = "Não foi possível contactar o modelo de IA após várias tentativas."
_MSG_UNEXPECTED = "Erro inesperado ao consultar o modelo de IA."
_MSG_EMPTY = "O modelo de IA devolveu uma resposta vazia."


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str


@dataclass(frozen=True)
class AssistantTurn:
    content: str | None
    tool_calls: list[ToolCall]


class LLMError(Exception):
    """Erro do LLM sem detalhes técnicos nem chave."""


@runtime_checkable
class ChatModel(Protocol):
    def complete(self, messages: list[dict], tools: list[dict]) -> AssistantTurn: ...


class OpenRouterClient:
    """Cliente do OpenRouter (SDK `openai`) com retry próprio e backoff exponencial."""

    def __init__(
        self,
        settings: Settings,
        sleep_fn: Callable[[float], None] = time.sleep,
        random_fn: Callable[[], float] = random.random,
    ) -> None:
        self._model = settings.model_id
        self._temperature = settings.llm_temperature
        self._max_tokens = settings.llm_max_tokens
        self._max_retries = settings.llm_max_retries
        self._sleep = sleep_fn
        self._random = random_fn
        self._client = openai.OpenAI(
            base_url=settings.openrouter_base_url,
            api_key=settings.openrouter_api_key,
            timeout=settings.llm_timeout_seconds,
            max_retries=0,  # o retry é nosso; o do SDK somaria tentativas
        )

    def complete(self, messages: list[dict], tools: list[dict]) -> AssistantTurn:
        """Chama o modelo com retry/backoff para falhas transitórias (429, 5xx, timeout, rede).

        Erros 4xx e bugs inesperados não são repetidos. Nunca expõe chave, corpo da resposta
        nem conteúdo das mensagens (nem nos logs).
        """
        attempts = self._max_retries + 1
        for attempt in range(1, attempts + 1):
            try:
                return self._request(messages, tools)
            except LLMError:
                raise
            except _RETRYABLE as exc:
                reason = type(exc).__name__
            except APIStatusError as exc:
                if exc.status_code not in _RETRY_STATUSES:
                    log.warning("model=%s status=%d sem retry", self._model, exc.status_code)
                    raise LLMError(_MSG_REJECTED) from None
                reason = f"HTTP{exc.status_code}"
            except Exception as exc:  # bug inesperado: repetir não ajuda
                log.warning("model=%s erro_inesperado=%s", self._model, type(exc).__name__)
                raise LLMError(_MSG_UNEXPECTED) from None
            log.warning("model=%s attempt=%d/%d erro=%s", self._model, attempt, attempts, reason)
            if attempt < attempts:
                self._sleep(self._backoff(attempt))
        raise LLMError(_MSG_EXHAUSTED)

    def _backoff(self, attempt: int) -> float:
        """Espera exponencial (1 s, 2 s, 4 s… até 8 s) mais jitter de até 50%."""
        wait = min(_BACKOFF_BASE * (2 ** (attempt - 1)), _BACKOFF_MAX)
        return wait + wait * self._random() * 0.5

    def _request(self, messages: list[dict], tools: list[dict]) -> AssistantTurn:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": self._temperature,
            # sem teto o OpenRouter reserva o máximo do modelo e recusa (402) contas com pouco saldo
            "max_tokens": self._max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
        response = self._client.chat.completions.create(**kwargs)
        choices = getattr(response, "choices", None)
        if not choices:
            raise LLMError(_MSG_EMPTY)
        message = choices[0].message
        tool_calls = [
            ToolCall(id=tc.id or "", name=tc.function.name, arguments=tc.function.arguments or "")
            for tc in (message.tool_calls or [])
        ]
        return AssistantTurn(content=message.content, tool_calls=tool_calls)
