"""Roda o eval: `python evals/run.py --prompt v1` (ver --help)."""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from emporio.config import load_settings  # noqa: E402
from emporio.llm import OpenRouterClient  # noqa: E402
from evals.judge import Judge  # noqa: E402
from evals.runner import load_cases, now_iso, run_all, summarize, write_report  # noqa: E402

JUDGE_MAX_TOKENS = 3000


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Eval do agente Téo")
    parser.add_argument("--prompt", help="versão do prompt (padrão: PROMPT_VERSION)")
    parser.add_argument("--model", help="modelo do agente (padrão: MODEL_ID)")
    parser.add_argument("--cases", type=Path, default=ROOT / "evals" / "casos.yaml")
    parser.add_argument("--only", nargs="*", help="rodar só estes ids de caso")
    parser.add_argument("--no-judge", action="store_true", help="só checagens determinísticas")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--out", type=Path, default=ROOT / "evals" / "relatorios")
    args = parser.parse_args(argv)

    try:
        settings = load_settings(ROOT / ".env")
    except ValueError as exc:
        print(f"Erro de configuração: {exc}", file=sys.stderr)
        return 2
    if not settings.openrouter_api_key:
        print(
            "Erro: OPENROUTER_API_KEY não configurada (.env na raiz do projeto).", file=sys.stderr
        )
        return 2
    settings = replace(
        settings,
        prompt_version=args.prompt or settings.prompt_version,
        model_id=args.model or settings.model_id,
    )

    cases, default_date = load_cases(args.cases)
    if args.only:
        cases = [c for c in cases if c["id"] in set(args.only)]
        if not cases:
            print("Nenhum caso corresponde a --only.", file=sys.stderr)
            return 2

    agent_model = OpenRouterClient(settings)
    judge = None
    if not args.no_judge:
        judge_settings = replace(
            settings,
            model_id=settings.judge_model_id,
            llm_temperature=0.0,
            llm_max_tokens=JUDGE_MAX_TOKENS,  # o juiz gasta tokens raciocinando antes do JSON
        )
        judge = Judge(OpenRouterClient(judge_settings))

    print(f"Rodando {len(cases)} casos | prompt {settings.prompt_version} | {settings.model_id}")
    results = run_all(
        cases,
        agent_model,
        judge,
        settings.prompt_version,
        default_date,
        workers=args.workers,
        max_iterations=settings.max_tool_iterations,
    )
    meta = {
        "prompt": settings.prompt_version,
        "model": settings.model_id,
        "judge_model": None if args.no_judge else settings.judge_model_id,
        "executado_em": now_iso(),
    }
    json_path, md_path = write_report(args.out, meta, results)
    s = summarize(results)
    print(f"Aprovados: {s['aprovados']}/{s['total']}  →  {md_path.relative_to(ROOT)}")
    for r in results:
        if not r.passed:
            print(f"  ❌ {r.id}: {'; '.join(r.deterministic_failures) or r.judge_reason}")
    return 0 if s["aprovados"] == s["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
