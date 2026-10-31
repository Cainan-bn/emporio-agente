from __future__ import annotations

from datetime import date

import pytest

from emporio.agent import Agent
from emporio.cli import _mask_email, main, run_chat
from emporio.llm import AssistantTurn
from emporio.tools import build_registry


class _FakeModel:
    def __init__(self, turns: list[AssistantTurn] | None = None) -> None:
        self._turns = list(turns or [])
        self._idx = 0

    def complete(self, messages: list[dict], tools: list[dict]) -> AssistantTurn:
        if self._idx >= len(self._turns):
            return AssistantTurn(content="OK", tool_calls=[])
        turn = self._turns[self._idx]
        self._idx += 1
        return turn


@pytest.fixture
def agent() -> Agent:
    registry = build_registry(today=date(2026, 3, 20))
    return Agent(
        model=_FakeModel([AssistantTurn(content="Bem-vindo!", tool_calls=[])]),
        registry=registry,
        system_prompt="test",
        max_iterations=3,
    )


def test_mask_email() -> None:
    assert _mask_email("p***@jmail.com")


def test_run_chat_sair(agent: Agent) -> None:
    inputs = iter(["/sair"])
    outputs: list[str] = []
    with pytest.raises(SystemExit):
        run_chat(agent, input_fn=lambda _: next(inputs), output_fn=outputs.append)
    output_text = "\n".join(outputs)
    assert "Téo" in output_text


def test_run_chat_ajuda(agent: Agent) -> None:
    inputs = iter(["/ajuda", "/sair"])
    outputs: list[str] = []
    with pytest.raises(SystemExit):
        run_chat(agent, input_fn=lambda _: next(inputs), output_fn=outputs.append)
    output_text = "\n".join(outputs)
    assert "/sair" in output_text


def test_run_chat_limpar(agent: Agent) -> None:
    inputs = iter(["/limpar", "/sair"])
    outputs: list[str] = []
    with pytest.raises(SystemExit):
        run_chat(agent, input_fn=lambda _: next(inputs), output_fn=outputs.append)
    output_text = "\n".join(outputs)
    assert "Histórico" in output_text


def test_run_chat_eof(agent: Agent) -> None:
    def raise_eof(prompt: str = "") -> str:
        raise EOFError

    outputs: list[str] = []
    run_chat(agent, input_fn=raise_eof, output_fn=outputs.append)
    output_text = "\n".join(outputs)
    assert "Até logo" in output_text


def test_main_no_key() -> None:
    import os

    key = os.environ.pop("OPENROUTER_API_KEY", None)
    try:
        with pytest.raises(SystemExit):
            main(["--help"])
    finally:
        if key:
            os.environ["OPENROUTER_API_KEY"] = key


def test_build_agent_integration() -> None:
    registry = build_registry(today=date(2026, 3, 20))
    agent = Agent(
        model=_FakeModel(
            [
                AssistantTurn(
                    content=None,
                    tool_calls=[
                        type(
                            "_TC",
                            (),
                            {
                                "id": "c1",
                                "name": "consultar_loja",
                                "arguments": "{}",
                                "type": "function",
                            },
                        )(),
                    ],
                ),
                AssistantTurn(content="Rua 14 de Maio", tool_calls=[]),
            ]
        ),
        registry=registry,
        system_prompt="teste",
    )
    reply = agent.reply("Qual o endereço?")
    assert "Rua 14 de Maio" in reply.text
