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


@pytest.fixture(scope="module")
def registry():
    return build_registry(today=date(2026, 3, 20))


@pytest.fixture
def agent(registry) -> Agent:
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
    run_chat(agent, input_fn=lambda _: next(inputs), output_fn=outputs.append)
    output_text = "\n".join(outputs)
    assert "Téo" in output_text


def test_run_chat_ajuda(agent: Agent) -> None:
    inputs = iter(["/ajuda", "/sair"])
    outputs: list[str] = []
    run_chat(agent, input_fn=lambda _: next(inputs), output_fn=outputs.append)
    output_text = "\n".join(outputs)
    assert "/sair" in output_text


def test_run_chat_limpar(agent: Agent) -> None:
    inputs = iter(["/limpar", "/sair"])
    outputs: list[str] = []
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


def test_main_sem_chave_devolve_2(monkeypatch: pytest.MonkeyPatch, capsys, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENCODE_API_KEY", raising=False)
    assert main([]) == 2
    err = capsys.readouterr().err
    assert "OPENCODE_API_KEY" in err and "Traceback" not in err


def test_main_config_invalida_devolve_2_sem_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys, tmp_path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENCODE_API_KEY", "sk-x")
    monkeypatch.setenv("LLM_TEMPERATURE", "nan")
    assert main([]) == 2
    err = capsys.readouterr().err
    assert "LLM_TEMPERATURE" in err and "Traceback" not in err and "sk-x" not in err


def test_main_ajuda_sai_com_zero() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0


def test_python_m_emporio_sem_chave_sai_com_codigo_2(tmp_path) -> None:
    import os
    import subprocess
    import sys
    from pathlib import Path

    env = {k: v for k, v in os.environ.items() if k != "OPENCODE_API_KEY"}
    env["PYTHONPATH"] = str(Path("src").resolve())
    done = subprocess.run(
        [sys.executable, "-m", "emporio"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert done.returncode == 2
    assert "Traceback" not in done.stderr


class _CtrlCModel:
    def complete(self, messages, tools):
        raise KeyboardInterrupt


def test_ctrl_c_durante_resposta_nao_derruba_o_chat(registry) -> None:
    agent = Agent(_CtrlCModel(), registry, "sys", max_iterations=2)
    inputs = iter(["oi", "/sair"])
    outputs: list[str] = []
    run_chat(agent, input_fn=lambda _: next(inputs), output_fn=outputs.append)
    assert any("interrompida" in o for o in outputs)


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
