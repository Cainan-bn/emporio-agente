from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from emporio.llm import ChatModel, LLMError
from emporio.tools.base import ToolRegistry

log = logging.getLogger(__name__)

_CONTINGENCY = (
    "Desculpe, tive um problema técnico. "
    "Você pode entrar em contato pelo WhatsApp (67) 3321-4500 "
    "ou e-mail contato@emporiodamusica.com.br. "
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


def _truncate_tool_calls(tc: list) -> list[dict]:
    result = []
    for t in tc:
        result.append(
            {
                "id": t.id,
                "type": "function",
                "function": {"name": t.name, "arguments": t.arguments},
            }
        )
    return result


class Agent:
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
        if not user_text.strip():
            return AgentReply(
                text="Olá! Como posso ajudar? "
                "Pergunte sobre produtos, pedidos ou políticas da loja.",
                fallback=False,
            )

        text = user_text[: self._max_user_chars]
        if len(user_text) > self._max_user_chars:
            log.info("user_text truncated from %d to %d", len(user_text), self._max_user_chars)

        self._history.append({"role": "user", "content": text})

        tool_records: list[ToolCallRecord] = []

        for iteration in range(self._max_iterations):
            try:
                turn = self._model.complete(
                    [{"role": "system", "content": self._system_prompt}] + self._history,
                    self._registry.schemas(),
                )
            except LLMError:
                self._history.pop()
                return AgentReply(text=_CONTINGENCY, fallback=True, iterations=iteration + 1)

            if not turn.tool_calls:
                content = turn.content or _CONTINGENCY
                self._history.append({"role": "assistant", "content": content})
                self._trim_history()
                return AgentReply(
                    text=content,
                    tool_calls=tool_records,
                    iterations=iteration + 1,
                )

            assistant_msg: dict = {"role": "assistant", "content": turn.content or None}
            if turn.tool_calls:
                assistant_msg["tool_calls"] = _truncate_tool_calls(turn.tool_calls)
            self._history.append(assistant_msg)

            for tcall in turn.tool_calls:
                try:
                    raw_args = (
                        json.loads(tcall.arguments) if isinstance(tcall.arguments, str) else {}
                    )
                except json.JSONDecodeError:
                    raw_args = {}
                result_str = self._registry.execute(tcall.name, tcall.arguments)
                try:
                    result_dict = json.loads(result_str)
                except json.JSONDecodeError:
                    result_dict = {"erro": "resposta inválida da ferramenta"}

                tool_records.append(
                    ToolCallRecord(
                        name=tcall.name,
                        arguments=raw_args,
                        result=result_dict,
                    )
                )

                self._history.append(
                    {
                        "role": "tool",
                        "tool_call_id": tcall.id,
                        "content": result_str,
                    }
                )

            self._trim_history()

        # Max iterations reached
        self._history.pop()
        return AgentReply(text=_CONTINGENCY, fallback=True, iterations=self._max_iterations)

    def reset(self) -> None:
        self._history.clear()

    def _trim_history(self) -> None:
        if len(self._history) <= self._max_history:
            return
        len(self._history) - self._max_history
        cut = 0
        for i, msg in enumerate(self._history):
            if msg["role"] == "user":
                cut = i
                break
            if (
                msg["role"] == "assistant"
                and i + 1 < len(self._history)
                and self._history[i + 1]["role"] == "tool"
            ):
                continue
            cut = i + 1
        # Ensure we don't cut in the middle of a tool call pair
        for i in range(cut, len(self._history)):
            if self._history[i]["role"] == "tool":
                cut = i + 1
            else:
                break
        self._history = self._history[cut:]
