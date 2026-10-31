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
    def __init__(
        self,
        settings: Settings,
        sleep_fn: Callable[[float], None] = time.sleep,
        random_fn: Callable[[], float] = random.random,
    ) -> None:
        self._model = settings.model_id
        self._temperature = settings.llm_temperature
        self._max_retries = settings.llm_max_retries
        self._sleep = sleep_fn
        self._random = random_fn
        self._client = openai.OpenAI(
            base_url=settings.openrouter_base_url,
            api_key=settings.openrouter_api_key,
            timeout=settings.llm_timeout_seconds,
            max_retries=0,
        )

    def complete(self, messages: list[dict], tools: list[dict]) -> AssistantTurn:
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                kwargs: dict[str, Any] = {
                    "model": self._model,
                    "messages": messages,
                    "temperature": self._temperature,
                }
                if tools:
                    kwargs["tools"] = tools

                response = self._client.chat.completions.create(**kwargs)

                if not response.choices:
                    raise LLMError("Resposta do modelo veio vazia")

                choice = response.choices[0]
                msg = choice.message

                tool_calls: list[ToolCall] = []
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        tool_calls.append(
                            ToolCall(
                                id=tc.id,
                                name=tc.function.name,
                                arguments=tc.function.arguments,
                            )
                        )

                return AssistantTurn(content=msg.content, tool_calls=tool_calls)

            except _RETRYABLE as exc:
                last_error = exc
                log.warning(
                    "model=%s attempt=%d/%d erro=%s",
                    self._model,
                    attempt + 1,
                    self._max_retries + 1,
                    type(exc).__name__,
                )
                if attempt < self._max_retries:
                    wait = min(
                        _BACKOFF_BASE * (2**attempt),
                        _BACKOFF_MAX,
                    )
                    jitter = wait * self._random() * 0.5
                    self._sleep(wait + jitter)
            except APIStatusError as exc:
                if exc.status_code in _RETRY_STATUSES:
                    last_error = exc
                    log.warning(
                        "model=%s attempt=%d/%d status=%d",
                        self._model,
                        attempt + 1,
                        self._max_retries + 1,
                        exc.status_code,
                    )
                    if attempt < self._max_retries:
                        wait = min(
                            _BACKOFF_BASE * (2**attempt),
                            _BACKOFF_MAX,
                        )
                        jitter = wait * self._random() * 0.5
                        self._sleep(wait + jitter)
                else:
                    raise LLMError(
                        "Erro na comunicação com o modelo de IA. "
                        "Tente novamente em alguns instantes."
                    ) from exc
            except Exception as exc:
                last_error = exc
                log.warning(
                    "model=%s attempt=%d/%d erro=%s",
                    self._model,
                    attempt + 1,
                    self._max_retries + 1,
                    type(exc).__name__,
                )
                if attempt < self._max_retries:
                    self._sleep(_BACKOFF_MAX)
                else:
                    raise LLMError(
                        "Não foi possível contactar o modelo de IA "
                        "após várias tentativas. Tente novamente mais tarde."
                    ) from exc

        raise LLMError(
            "Não foi possível contactar o modelo de IA após várias tentativas. "
            "Tente novamente mais tarde."
        ) from last_error
