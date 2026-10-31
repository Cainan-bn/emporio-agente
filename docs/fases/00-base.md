# Fase 0 — Base do repositório (`fase/00-base`)

**Objetivo:** esqueleto do projeto, pronto para as fases seguintes. Sem lógica de negócio.

## Entregas (um commit por item, em português, Conventional Commits)
1. `.gitignore` — Python (`__pycache__`, `.venv`, `.pytest_cache`, `.ruff_cache`, `*.egg-info`), `.env`, `.maestri/`, `*.db`/`*.sqlite`, `evals/relatorios/.tmp`. **Não** ignorar `data/`.
2. `.env.example` — `OPENROUTER_API_KEY=`, `OPENROUTER_BASE_URL=https://openrouter.ai/api/v1`, `MODEL_ID=anthropic/claude-haiku-5.5`, `JUDGE_MODEL_ID=anthropic/claude-sonnet-5.5`, `REFERENCE_DATE=` (vazio = data do sistema), `MAX_TOOL_ITERATIONS=6`, `LLM_TIMEOUT_SECONDS=30`, `LLM_MAX_RETRIES=3`, `LOG_LEVEL=INFO`. Comentários em português.
3. Estrutura de pastas com `__init__.py` e `.gitkeep` onde vazio: `src/emporio/{prompts,tools,data,policies}/`, `tests/`, `evals/relatorios/`, `docs/`, `examples/`, `scripts/`.
4. `pyproject.toml` — projeto `emporio` (Python >=3.11), layout `src`, config do `ruff` (line-length 100, regras E,F,I,UP,B) e do `pytest` (`testpaths=tests`, `pythonpath=src`).
5. `requirements.txt` (runtime: `openai`, `python-dotenv`, `pyyaml`, `pypdf`, `rank-bm25`) e `requirements-dev.txt` (`-r requirements.txt`, `pytest`, `ruff`) com **versões fixadas** (`==`), instaladas e testadas num venv.
6. `src/emporio/config.py` — dataclass `Settings` imutável + `load_settings()` lendo as variáveis acima (`.env` via python-dotenv, nenhum segredo no código). `REFERENCE_DATE` vira `date | None`.
7. `tests/test_config.py` — valores padrão, sobrescrita por ambiente, data inválida levanta `ValueError` com mensagem clara. Sem rede.
8. `README.md` esqueleto — título, descrição de 2 linhas, seções vazias com "(em construção)" na ordem da seção 8 do enunciado.

## Critérios de aceite
- `python -m venv .venv && pip install -r requirements-dev.txt && ruff check . && ruff format --check . && pytest` passam do zero.
- Nenhum arquivo de `data/` é tocado ou adicionado nesta fase.
- Nenhum `.env` real, nenhuma chave.
- Commits pequenos; teste junto do `config.py`.

## Fluxo
Branch `fase/00-base` já existe (com esta spec). Faça os commits nela, `git push -u origin fase/00-base`, abra a PR com `gh pr create` e avise o Arquiteto. **Não faça merge.**
