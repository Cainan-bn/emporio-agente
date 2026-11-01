"""Executa os casos dourados contra o agente real e monta o relatório."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

from emporio.agent import Agent
from emporio.llm import ChatModel
from emporio.prompts import load_system_prompt
from emporio.tools import build_registry
from evals.checks import Trace, run_checks, validate_case
from evals.judge import Judge, format_transcript


@dataclass
class CaseResult:
    id: str
    categoria: str
    passed: bool
    deterministic_failures: list[str] = field(default_factory=list)
    judge_approved: bool | None = None  # None = sem rubrica ou juiz desligado
    judge_reason: str = ""
    replies: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    error: str = ""


def load_cases(path: Path) -> tuple[list[dict[str, Any]], str]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    cases = data["casos"]
    ids = [c.get("id") for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("ids de casos repetidos")
    for case in cases:
        validate_case(case)
    return cases, str(data.get("data_referencia_padrao", "2026-03-20"))


def run_case(
    case: dict[str, Any],
    model: ChatModel,
    judge: Judge | None,
    prompt_version: str,
    default_date: str,
    max_iterations: int = 6,
) -> CaseResult:
    base = CaseResult(id=case["id"], categoria=case["categoria"], passed=False)
    try:
        today = date.fromisoformat(str(case.get("data_referencia", default_date)))
        for_conversation = getattr(model, "for_conversation", None)
        agent = Agent(
            for_conversation() if for_conversation else model,  # sessão própria por caso
            build_registry(today=today),  # uma conexão SQLite por caso (thread própria)
            load_system_prompt(prompt_version, today),
            max_iterations=max_iterations,
        )
        replies = [agent.reply(turn) for turn in case["turnos"]]
    except Exception as exc:  # um caso quebrado não derruba o relatório
        base.error = f"{type(exc).__name__}: {exc}"
        base.deterministic_failures = ["erro de execução do caso"]
        return base

    tools = [(c.name, c.arguments, c.result) for r in replies for c in r.tool_calls]
    trace = Trace(
        replies=[r.text for r in replies],
        tool_names=[name for name, _, _ in tools],
        fallback=any(r.fallback for r in replies),
    )
    checks = run_checks(case, trace)
    base.deterministic_failures = checks.failures
    base.replies = trace.replies
    base.tools = trace.tool_names

    if judge is not None and case.get("rubrica"):
        transcript = format_transcript(
            [
                (user, reply.text, [(c.name, c.arguments, c.result) for c in reply.tool_calls])
                for user, reply in zip(case["turnos"], replies, strict=True)
            ]
        )
        verdict = judge.evaluate(case["rubrica"], transcript)
        base.judge_approved = verdict.approved
        base.judge_reason = verdict.reason
    base.passed = checks.passed and base.judge_approved is not False
    return base


def run_all(
    cases: list[dict[str, Any]],
    model: ChatModel,
    judge: Judge | None,
    prompt_version: str,
    default_date: str,
    workers: int = 4,
    max_iterations: int = 6,
) -> list[CaseResult]:
    def _one(case: dict[str, Any]) -> CaseResult:
        return run_case(case, model, judge, prompt_version, default_date, max_iterations)

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        return list(pool.map(_one, cases))


def summarize(results: list[CaseResult]) -> dict[str, Any]:
    by_category: dict[str, list[int]] = {}
    for r in results:
        passed, total = by_category.setdefault(r.categoria, [0, 0])
        by_category[r.categoria] = [passed + int(r.passed), total + 1]
    return {
        "total": len(results),
        "aprovados": sum(r.passed for r in results),
        "falha_deterministica": sum(bool(r.deterministic_failures) for r in results),
        "falha_juiz": sum(r.judge_approved is False for r in results),
        "por_categoria": by_category,
    }


def render_markdown(meta: dict[str, Any], results: list[CaseResult]) -> str:
    s = summarize(results)
    pct = 100 * s["aprovados"] / max(1, s["total"])
    lines = [
        f"# Relatório do eval — prompt {meta['prompt']}",
        "",
        f"- Modelo do agente: `{meta['model']}`",
        f"- Modelo do juiz: `{meta['judge_model'] or 'desligado'}`",
        f"- Data de execução: {meta['executado_em']}",
        f"- **Aprovados: {s['aprovados']}/{s['total']} ({pct:.0f}%)** — "
        f"falhas determinísticas: {s['falha_deterministica']}, falhas do juiz: {s['falha_juiz']}",
        "",
        "## Por categoria",
        "",
        "| Categoria | Aprovados |",
        "|---|---|",
    ]
    lines += [f"| {cat} | {p}/{t} |" for cat, (p, t) in sorted(s["por_categoria"].items())]
    lines += ["", "## Casos", "", "| Caso | Resultado | Ferramentas |", "|---|---|---|"]
    for r in results:
        tools = ", ".join(r.tools) or "—"
        lines.append(f"| `{r.id}` | {'✅' if r.passed else '❌'} | {tools} |")
    failed = [r for r in results if not r.passed]
    if failed:
        lines += ["", "## Falhas", ""]
        for r in failed:
            lines.append(f"### `{r.id}` ({r.categoria})")
            if r.error:
                lines.append(f"- Erro: {r.error}")
            lines += [f"- Checagem: {f}" for f in r.deterministic_failures]
            if r.judge_approved is False:
                lines.append(f"- Juiz: {r.judge_reason}")
            for reply in r.replies:
                lines.append(f"- Resposta: {reply!r}")
            lines.append("")
    return "\n".join(lines) + "\n"


def write_report(
    out_dir: Path, meta: dict[str, Any], results: list[CaseResult]
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = meta["model"].replace("/", "_").replace(":", "_")
    when = meta["executado_em"]  # aaaa-mm-ddTHH:MM:SS
    stem = f"{when[:10]}_{meta['prompt']}_{slug}_{when[11:19].replace(':', '')}"
    json_path, md_path = out_dir / f"{stem}.json", out_dir / f"{stem}.md"
    payload = {"meta": meta, "resumo": summarize(results), "casos": [asdict(r) for r in results]}
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(meta, results), encoding="utf-8")
    return json_path, md_path


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")
