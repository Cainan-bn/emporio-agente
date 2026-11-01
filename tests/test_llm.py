from __future__ import annotations

import logging
from typing import Any

import pytest
from openai import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError

from emporio.config import Settings
from emporio.llm import AssistantTurn, LLMError, OpenCodeClient, ToolCall


class _Stub:
    """Objeto simples com atributos arbitrários (fake de resposta/requisição HTTP)."""

    def __init__(self, **attrs: Any) -> None:
        self.__dict__.update(attrs)


def _http_response(status: int) -> _Stub:
    return _Stub(status_code=status, headers={}, request=_Stub(method="POST", url="x"))


def _response(content: str | None = "Olá!", tool_calls: list | None = None) -> _Stub:
    message = _Stub(content=content, tool_calls=tool_calls)
    return _Stub(choices=[_Stub(message=message)])


def _client(settings: Settings, create: Any) -> tuple[OpenCodeClient, list[float]]:
    sleeps: list[float] = []
    client = OpenCodeClient(settings, sleep_fn=sleeps.append, random_fn=lambda: 0.5)
    client._client.chat.completions.create = create
    return client, sleeps


@pytest.fixture
def settings() -> Settings:
    return Settings(
        opencode_api_key="sk-test",
        opencode_base_url="https://opencode.ai/inference/go/openai/v1",
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


def test_opencode_client_import() -> None:
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


def _failing(exc_factory: Any) -> tuple[Any, dict[str, int]]:
    counter = {"calls": 0}

    def _create(*a: Any, **kw: Any) -> None:
        counter["calls"] += 1
        raise exc_factory()

    return _create, counter


def test_sucesso_devolve_turno(settings: Settings) -> None:
    client, sleeps = _client(settings, lambda **kw: _response("Oi!"))
    turn = client.complete([{"role": "user", "content": "oi"}], [])
    assert turn == AssistantTurn(content="Oi!", tool_calls=[])
    assert sleeps == []


def test_tool_calls_sao_convertidas(settings: Settings) -> None:
    function = _Stub(name="consultar_loja", arguments="{}")
    call = _Stub(id="c1", function=function)
    client, _ = _client(settings, lambda **kw: _response(None, [call]))
    turn = client.complete([], [{"type": "function"}])
    assert turn.tool_calls == [ToolCall(id="c1", name="consultar_loja", arguments="{}")]


@pytest.mark.parametrize(
    "factory",
    [
        lambda: RateLimitError("limite", response=_http_response(429), body=None),
        lambda: APIStatusError("erro", response=_http_response(503), body=None),
        lambda: APITimeoutError(request=_Stub()),
        lambda: APIConnectionError(request=_Stub()),
    ],
    ids=["429", "503", "timeout", "conexao"],
)
def test_falhas_transitorias_repetem_com_backoff(settings: Settings, factory: Any) -> None:
    create, counter = _failing(factory)
    client, sleeps = _client(settings, create)
    with pytest.raises(LLMError):
        client.complete([], [])
    assert counter["calls"] == 3  # 1 tentativa + 2 retries
    assert sleeps == [1.25, 2.5]  # 1 s e 2 s + jitter de 25% (random fixo em 0,5)


def test_backoff_tem_teto(settings: Settings) -> None:
    client, _ = _client(settings, lambda **kw: None)
    assert client._backoff(10) == 10.0  # teto de 8 s + jitter


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_4xx_nao_repete(settings: Settings, status: int) -> None:
    create, counter = _failing(
        lambda: APIStatusError("ruim", response=_http_response(status), body={"x": "sk-test"})
    )
    client, sleeps = _client(settings, create)
    with pytest.raises(LLMError) as exc:
        client.complete([], [])
    assert counter["calls"] == 1
    assert sleeps == []
    assert "sk-test" not in str(exc.value)


def test_resposta_vazia_nao_repete(settings: Settings) -> None:
    create, counter = _failing(lambda: AssertionError())
    client, sleeps = _client(settings, lambda **kw: _Stub(choices=[]))
    with pytest.raises(LLMError):
        client.complete([], [])
    assert sleeps == []
    del create, counter


def test_bug_inesperado_nao_repete_e_nao_vaza(
    settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    create, counter = _failing(lambda: RuntimeError("segredo sk-test-key /home/x"))
    client, sleeps = _client(settings, create)
    with caplog.at_level(logging.WARNING), pytest.raises(LLMError) as exc:
        client.complete([{"role": "user", "content": "meu email é a@b.com"}], [])
    assert counter["calls"] == 1
    assert sleeps == []
    assert "sk-test" not in str(exc.value)
    assert "sk-test" not in " ".join(caplog.messages)
    assert "a@b.com" not in " ".join(caplog.messages)


def test_envia_max_tokens_ao_provedor(settings: Settings) -> None:
    enviados: list[dict] = []

    def _create(**kwargs: Any) -> _Stub:
        enviados.append(kwargs)
        return _response("ok")

    client, _ = _client(settings, _create)
    client.complete([{"role": "user", "content": "oi"}], [])
    assert enviados[0]["max_tokens"] == settings.llm_max_tokens == 1024


def test_client_sends_session_header_and_user_agent(settings: Settings) -> None:
    client = OpenCodeClient(settings)
    headers = client._client.default_headers
    assert headers["x-opencode-session"]
    assert headers["User-Agent"].startswith("emporio-agente/")
