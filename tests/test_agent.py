from __future__ import annotations

from datetime import date

import pytest

from emporio.agent import Agent, ToolCallRecord
from emporio.llm import AssistantTurn, ToolCall
from emporio.tools import build_registry
from emporio.tools.base import ToolRegistry


class _FakeModel:
    def __init__(self, turns: list[AssistantTurn]) -> None:
        self._turns = list(turns)
        self._idx = 0

    def complete(self, messages: list[dict], tools: list[dict]) -> AssistantTurn:
        if self._idx >= len(self._turns):
            return AssistantTurn(content="OK, concluído.", tool_calls=[])
        turn = self._turns[self._idx]
        self._idx += 1
        return turn


@pytest.fixture
def registry() -> ToolRegistry:
    return build_registry(today=date(2026, 3, 20))


@pytest.fixture
def agent(registry: ToolRegistry) -> Agent:
    model = _FakeModel([])
    return Agent(
        model=model,
        registry=registry,
        system_prompt="Você é o Téo, assistente.",
        max_iterations=3,
    )


def test_direct_response(agent: Agent) -> None:
    agent._model = _FakeModel(
        [
            AssistantTurn(content="Olá! Como posso ajudar?", tool_calls=[]),
        ]
    )
    reply = agent.reply("qual o horário?")
    assert reply.text == "Olá! Como posso ajudar?"
    assert reply.iterations == 1
    assert not reply.fallback


def test_tool_call_flow(agent: Agent) -> None:
    agent._model = _FakeModel(
        [
            AssistantTurn(
                content=None,
                tool_calls=[
                    ToolCall(id="call_1", name="consultar_loja", arguments="{}"),
                ],
            ),
            AssistantTurn(
                content="Estamos na Rua 14 de Maio.",
                tool_calls=[],
            ),
        ]
    )
    reply = agent.reply("qual o endereço?")
    assert "Rua 14 de Maio" in reply.text
    assert len(reply.tool_calls) == 1
    assert reply.tool_calls[0].name == "consultar_loja"
    assert reply.tool_calls[0].result["endereco_e_dados"] is not None


def test_max_iterations_fallback(agent: Agent) -> None:
    agent._model = _FakeModel(
        [
            AssistantTurn(
                content=None,
                tool_calls=[
                    ToolCall(id="c1", name="consultar_loja", arguments="{}"),
                ],
            ),
            AssistantTurn(
                content=None,
                tool_calls=[
                    ToolCall(id="c2", name="consultar_loja", arguments="{}"),
                ],
            ),
            AssistantTurn(
                content=None,
                tool_calls=[
                    ToolCall(id="c3", name="consultar_loja", arguments="{}"),
                ],
            ),
        ]
    )
    reply = agent.reply("endereço")
    assert reply.fallback
    assert "24 horas" in reply.text


def test_empty_text(agent: Agent) -> None:
    reply = agent.reply("")
    assert reply.text
    assert not reply.fallback
    assert reply.iterations == 0


def test_text_truncated(agent: Agent, caplog: pytest.LogCaptureFixture) -> None:
    agent._max_user_chars = 5
    import logging

    with caplog.at_level(logging.INFO):
        agent._model = _FakeModel(
            [
                AssistantTurn(content="OK", tool_calls=[]),
            ]
        )
        reply = agent.reply("x" * 100)
    assert reply.text is not None


def test_tool_error_continues(agent: Agent) -> None:
    agent._model = _FakeModel(
        [
            AssistantTurn(
                content=None,
                tool_calls=[
                    ToolCall(id="c1", name="consultar_produto", arguments='{"produto":"999999"}'),
                ],
            ),
            AssistantTurn(content="Produto não encontrado.", tool_calls=[]),
        ]
    )
    reply = agent.reply("produto 999999")
    assert "não encontrado" in reply.text


def test_reset(agent: Agent) -> None:
    agent._model = _FakeModel(
        [
            AssistantTurn(content="Oi", tool_calls=[]),
        ]
    )
    agent.reply("teste")
    agent.reset()
    assert agent._history == []


def test_tool_call_record(registry: ToolRegistry) -> None:
    record = ToolCallRecord(
        name="consultar_loja",
        arguments={},
        result={"endereco_e_dados": "Rua 14 de Maio"},
    )
    assert record.name == "consultar_loja"
    assert "Rua" in record.result["endereco_e_dados"]
