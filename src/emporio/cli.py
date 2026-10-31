from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

from emporio.agent import Agent
from emporio.config import load_settings
from emporio.data.loader import DATA_DIR
from emporio.llm import OpenRouterClient
from emporio.prompts import load_system_prompt
from emporio.tools import build_registry

log = logging.getLogger(__name__)

_EMAIL_MASK = re.compile(r"([\w.+-]+)@")


def _mask_email(text: str) -> str:
    return _EMAIL_MASK.sub(lambda m: m.group(1)[:1] + "***@", text)


def build_agent(
    settings: Any = None,
    data_dir: Path | None = None,
    model: Any = None,
) -> Agent:
    if settings is None:
        settings = load_settings()
    today = settings.reference_date or date.today()

    if model is not None:
        llm = model
    else:
        llm = OpenRouterClient(settings)

    base = data_dir if data_dir is not None else DATA_DIR
    registry = build_registry(today=today, data_dir=base)
    prompt = load_system_prompt(settings.prompt_version, today)

    return Agent(
        model=llm,
        registry=registry,
        system_prompt=prompt,
        max_iterations=settings.max_tool_iterations,
    )


def run_chat(
    agent: Agent,
    input_fn: Any = input,
    output_fn: Any = print,
    show_tools: bool = False,
) -> None:
    output_fn(
        "╔══════════════════════════════════════╗\n"
        "║  Téo — Empório da Música 🎸          ║\n"
        "║  Digite /ajuda para ver os comandos  ║\n"
        "╚══════════════════════════════════════╝"
    )

    while True:
        try:
            raw = input_fn("\nVocê: ")
        except EOFError:
            output_fn("\nAté logo! 🎶")
            return
        except KeyboardInterrupt:
            output_fn("\nAté logo! 🎶")
            return

        user_text = raw.strip()
        if not user_text:
            continue
        if user_text.startswith("/"):
            _handle_command(user_text[1:], agent, output_fn)
            continue

        reply = agent.reply(user_text)
        if reply.tool_calls and show_tools:
            for tc in reply.tool_calls:
                args_str = json_dumps_safe(tc.arguments)
                masked = _mask_email(args_str)
                output_fn(f"\033[90m🔧 {tc.name}({masked})\033[0m")
        output_fn(f"\nTéo: {reply.text}")


def _handle_command(cmd: str, agent: Agent, output_fn: Any) -> None:
    cmd = cmd.strip().lower()
    if cmd in ("sair", "quit", "exit"):
        output_fn("Até logo! 🎶")
        sys.exit(0)
    elif cmd in ("limpar", "clear", "reset"):
        agent.reset()
        output_fn("Histórico limpo!")
    elif cmd in ("ajuda", "help"):
        output_fn(
            "Comandos:\n"
            "  /sair   — encerrar o chat\n"
            "  /limpar — limpar o histórico\n"
            "  /ajuda  — mostrar esta ajuda"
        )
    else:
        output_fn(f"Comando desconhecido: /{cmd}")


def json_dumps_safe(obj: Any) -> str:

    return json.dumps(obj, ensure_ascii=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Téo — Assistente virtual da Empório da Música")
    parser.add_argument("--debug", action="store_true", help="Mostrar ferramentas chamadas")
    parser.add_argument("--data-dir", type=Path, help="Diretório com os dados")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.WARNING)

    settings = load_settings()
    if not settings.openrouter_api_key:
        print(
            "Erro: OPENROUTER_API_KEY não configurada.\n"
            "Crie um arquivo .env com OPENROUTER_API_KEY=sua-chave\n"
            "ou exporte a variável de ambiente.",
            file=sys.stderr,
        )
        return 2

    try:
        agent = build_agent(settings, data_dir=args.data_dir)
    except Exception as exc:
        print(f"Erro ao iniciar: {exc}", file=sys.stderr)
        return 1

    run_chat(agent, show_tools=args.debug)
    return 0
