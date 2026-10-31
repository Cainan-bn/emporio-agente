from __future__ import annotations

from typing import Any

import pytest

from emporio.config import Settings
from emporio.llm import AssistantTurn, LLMError, OpenRouterClient, ToolCall


class _FakeChoice:
    def __init__(self, content: str | None, tool_calls: list | None, finish: str = "stop"):
        self.finish_reason = finish

        class _Msg:
            content = content
            tool_calls = tool_calls

        self.message = _Msg()


class _FakeTC:
    def __init__(self, name: str, args: str, id: str = "call_1"):
        self.id = id
        self.type = "function"

        class _Fn:
            def __init__(self):
                self.name = name
                self.arguments = args

        self.function = _Fn()


class _FakeResponse:
    def __init__(self, choices: list | None = None):
        self.choices = choices


@pytest.fixture
def settings() -> Settings:
    return Settings(
        openrouter_api_key="sk-test",
        openrouter_base_url="https://openrouter.ai/api/v1",
        model_id="test-model",
        judge_model_id="judge",
        reference_date=None,
        max_tool_iterations=6,
        llm_timeout_seconds=30,
        llm_max_retries=2,
        llm_temperature=0.2,
        prompt_version="v1",
        log_level="INFO",
    )


def test_openrouter_client_import() -> None:
    from emporio.llm import ChatModel

    assert ChatModel is not None


def test_tool_call_dataclass() -> None:
    tc = ToolCall(id="call_1", name="buscar_produtos", arguments='{"termo": "violao"}')
    assert tc.id == "call_1"
    assert tc.name == "buscar_produtos"


def test_assistant_turn_dataclass() -> None:
    turn = AssistantTurn(content="Olá!", tool_calls=[])
    assert turn.content == "Olá!"
    assert turn.tool_calls == []


def test_llm_error_message() -> None:
    err = LLMError("Erro de teste")
    assert "Erro de teste" in str(err)
    assert "sk-test" not in str(err)


def test_retry_chain_ends_with_llm_error(settings: Settings) -> None:
    sleeps: list[float] = []
    client = OpenRouterClient(
        settings,
        sleep_fn=lambda s: sleeps.append(s),
        random_fn=lambda: 0.5,
    )
    # Monkey-patch the internal client to always raise 429
    calls = 0

    def _fake(*a: Any, **kw: Any) -> None:
        nonlocal calls
        calls += 1
        import httpx
        from openai import RateLimitError

        raise RateLimitError(
            message="rate limited",
            response=httpx.Response(429, request=httpx.Request("POST", "https://test.com")),
            body=None,
        )

    client._client.chat.completions.create = _fake

    with pytest.raises(LLMError):
        client.complete([{"role": "user", "content": "hi"}], [])

    assert calls == 3  # initial + 2 retries
    assert len(sleeps) == 2
    for s in sleeps:
        assert 0.5 <= s <= 8.0


def test_empty_response_error(settings: Settings) -> None:
    client = OpenRouterClient(settings)
    client._client.chat.completions.create = lambda *a, **kw: _FakeResponse(choices=[])

    with pytest.raises(LLMError):
        client.complete([{"role": "user", "content": "hi"}], [])


def test_400_no_retry(settings: Settings) -> None:
    client = OpenRouterClient(settings)
    calls = 0

    def _fake(*a: Any, **kw: Any) -> None:
        nonlocal calls
        calls += 1
        import httpx
        from openai import APIStatusError

        raise APIStatusError(
            message="bad request",
            response=httpx.Response(400, request=httpx.Request("POST", "https://test.com")),
            body=None,
        )

    client._client.chat.completions.create = _fake

    with pytest.raises(LLMError):
        client.complete([{"role": "user", "content": "hi"}], [])
    assert calls == 1  # no retry on 400


def test_500_retry(settings: Settings) -> None:
    client = OpenRouterClient(settings)
    calls = 0

    def _fake(*a: Any, **kw: Any) -> None:
        nonlocal calls
        calls += 1
        import httpx
        from openai import APIStatusError

        raise APIStatusError(
            message="server error",
            response=httpx.Response(500, request=httpx.Request("POST", "https://test.com")),
            body=None,
        )

    client._client.chat.completions.create = _fake
    with pytest.raises(LLMError):
        client.complete([{"role": "user", "content": "hi"}], [])
    assert calls == 3  # initial + 2 retries


def test_no_api_key_in_error(settings: Settings, caplog: pytest.LogCaptureFixture) -> None:
    client = OpenRouterClient(settings)
    client._client.chat.completions.create = lambda *a, **kw: (_ for _ in ()).throw(
        Exception("internal error with sk-test-key")
    )
    import logging

    with caplog.at_level(logging.WARNING):
        with pytest.raises(LLMError) as exc:
            client.complete([], [])
    assert "sk-test" not in str(exc.value)
    log_text = " ".join(caplog.messages)
    assert "sk-test" not in log_text
