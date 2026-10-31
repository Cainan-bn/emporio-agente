from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from emporio.llm import ChatModel, ToolCall
from emporio.tools.base import ToolRegistry

log = logging.getLogger(__name__)

_MAX_TOOL_CALLS_PER_RESPONSE = 8

_CONTINGENCY = (
    "Desculpe, tive um problema técnico. "
    "Você pode falar com a equipe pelo WhatsApp (67) 3321-4500, "
    "pelo telefone (67) 3341-4444 ou pelo e-mail contato@emporiodamusica.com.br. "
    "Uma pessoa da nossa equipe vai te atender em até 24 horas úteis."
)


@dataclass
class ToolCallRecord:
    name: str
    arguments: dict[str, Any]
    result: dict[str, Any]


@dataclass
class AgentReply:
    text: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    iterations: int = 0
    fallback: bool = False


def _serialize_tool_calls(tool_calls: list[ToolCall]) -> list[dict]:
    return [
        {
            "id": tc.id,
            "type": "function",
            "function": {"name": tc.name, "arguments": tc.arguments},
        }
        for tc in tool_calls
    ]


def _parse_arguments(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


class Agent:
    """Loop de conversa com *function calling*, histórico e limites de segurança."""

    def __init__(
        self,
        model: ChatModel,
        registry: ToolRegistry,
        system_prompt: str,
        max_iterations: int = 6,
        max_history_messages: int = 40,
        max_user_chars: int = 2000,
    ):
        self._model = model
        self._registry = registry
        self._system_prompt = system_prompt
        self._max_iterations = max_iterations
        self._max_history = max_history_messages
        self._max_user_chars = max_user_chars
        self._history: list[dict] = []

    def reply(self, user_text: str) -> AgentReply:
        """Responde ao cliente. Nunca levanta: falhas viram a mensagem de contingência."""
        if not user_text.strip():
            return AgentReply(
                text="Olá! Como posso ajudar? "
                "Pergunte sobre produtos, pedidos ou políticas da loja."
            )
        text = user_text[: self._max_user_chars]
        if len(user_text) > self._max_user_chars:
            log.info("user_text truncado de %d para %d", len(user_text), self._max_user_chars)

        self._trim_history()
        checkpoint = len(self._history)  # início do turno; falha => volta para cá
        self._history.append({"role": "user", "content": text})
        records: list[ToolCallRecord] = []
        try:
            reply = self._run_turn(records)
        except BaseException as exc:
            del self._history[checkpoint:]
            if isinstance(exc, Exception):
                log.warning("turno abortado erro=%s", type(exc).__name__)
                return AgentReply(text=_CONTINGENCY, tool_calls=records, fallback=True)
            raise  # Ctrl-C etc.: histórico já está consistente
        if reply is None:
            del self._history[checkpoint:]
            return AgentReply(
                text=_CONTINGENCY,
                tool_calls=records,
                iterations=self._max_iterations,
                fallback=True,
            )
        return reply

    def reset(self) -> None:
        self._history.clear()

    def _run_turn(self, records: list[ToolCallRecord]) -> AgentReply | None:
        """Executa o loop de tool calling; `None` se estourar o limite de iterações."""
        for iteration in range(1, self._max_iterations + 1):
            started = time.perf_counter()
            turn = self._model.complete(
                [{"role": "system", "content": self._system_prompt}] + self._history,
                self._registry.schemas(),
            )
            if not turn.tool_calls:
                content = (turn.content or "").strip()
                if not content:
                    raise ValueError("resposta vazia do modelo")
                self._history.append({"role": "assistant", "content": content})
                log.info("iteracoes=%d duracao=%.2fs", iteration, time.perf_counter() - started)
                return AgentReply(text=content, tool_calls=records, iterations=iteration)

            calls = self._normalize_ids(turn.tool_calls, iteration)
            self._history.append(
                {
                    "role": "assistant",
                    "content": turn.content or None,
                    "tool_calls": _serialize_tool_calls(calls),
                }
            )
            for position, call in enumerate(calls):
                self._run_tool(call, position, records)
        return None

    def _run_tool(self, call: ToolCall, position: int, records: list[ToolCallRecord]) -> None:
        if position >= _MAX_TOOL_CALLS_PER_RESPONSE:
            result_str = json.dumps({"erro": "Muitas ferramentas na mesma resposta"})
        else:
            result_str = self._registry.execute(call.name, call.arguments)
        try:
            result = json.loads(result_str)
        except json.JSONDecodeError:
            result = {"erro": "resposta inválida da ferramenta"}
        log.info("tool=%s ok=%s", call.name, "erro" not in result)
        records.append(
            ToolCallRecord(
                name=call.name, arguments=_parse_arguments(call.arguments), result=result
            )
        )
        self._history.append({"role": "tool", "tool_call_id": call.id, "content": result_str})

    @staticmethod
    def _normalize_ids(calls: list[ToolCall], iteration: int) -> list[ToolCall]:
        """Garante ids únicos e não vazios (a API exige uma resposta `tool` por id)."""
        seen: set[str] = set()
        normalized = []
        for position, call in enumerate(calls):
            call_id = call.id if call.id and call.id not in seen else f"call_{iteration}_{position}"
            seen.add(call_id)
            normalized.append(ToolCall(id=call_id, name=call.name, arguments=call.arguments))
        return normalized

    def _trim_history(self) -> None:
        """Descarta os turnos mais antigos, sempre cortando no início de uma fala do usuário
        (nunca separa `assistant`/`tool` nem começa o histórico por `tool`)."""
        while len(self._history) > self._max_history:
            start = next(
                (i for i in range(1, len(self._history)) if self._history[i]["role"] == "user"),
                None,
            )
            if start is None:
                return
            del self._history[:start]
