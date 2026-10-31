# Fase 1 — Dados (`fase/01-dados`)

**Objetivo:** versionar os dados originais e criar um script de *profiling* reproduzível que confirma os achados de `docs/00-analise-dados.md` (já escrito pelo Arquiteto e commitado nesta branch).

## Entregas (commits pequenos)
1. `data/` — os 6 CSVs e o PDF **sem nenhuma alteração** (`git add data/`; um commit só: `feat(dados): adiciona CSVs e PDF originais`).
2. `scripts/profile_data.py` — usa só biblioteca padrão + `pypdf`. Localiza os arquivos por sufixo (`*products.csv`, `*orders.csv`, … e `*.pdf`; os nomes reais têm prefixo `desafio_tecnico_ai_eng - `). Imprime em português, por arquivo: nº de linhas, colunas, nulos por coluna, duplicatas de chave, valores distintos de colunas categóricas (`status`, `payment_method`, `is_active`, `category_id`); e checagens de integridade: FKs órfãs; pedidos cujo `total_brl` ≠ soma(qty × preço atual) (esperado: pedidos 3 e 20); e-mails duplicados (esperado: `bruno.martins@jmail.com`); produtos com `status != active`, estoque 0, e produtos "indisponíveis" com estoque; promoções ativas; PDF: nº de páginas, nº de caracteres, e lista de títulos de seção numerados (`^\d+(\.\d+)?\.? [A-ZÁ-Ú]`) extraídos com `extraction_mode="layout"`.
3. Funções puras e pequenas (`load_csv`, `find_data_file`, `check_orphans`, `check_order_totals`, `find_duplicate_values`, `extract_sections_titles`…), `main()` fino, type hints.
4. `tests/test_profile_data.py` — roda as funções contra os dados reais de `data/` e afirma os achados: 65 produtos, 20 pedidos, 50 clientes, 25 promoções (4 ativas), totais divergentes = {3, 20}, e-mail duplicado = 1, seções do PDF incluem "4.1", "7.1", "8.1" e "10". Mais um teste com CSV mínimo em `tmp_path` para valores nulos/duplicados. Sem rede.
5. `fix(config)`: em `load_settings`, `int()` inválido deve levantar `ValueError` citando o **nome da variável** (ex.: `MAX_TOOL_ITERATIONS deve ser um inteiro, recebido 'abc'`) + teste. (Observação do QA na fase 0.)
6. Todos os arquivos terminam com newline final.

## Critérios de aceite
- `ruff check .`, `ruff format --check .`, `pytest` verdes em venv limpo.
- `git diff main -- data/` só mostra arquivos **adicionados**, e `git status` mostra o conteúdo idêntico aos originais (checksum igual).
- `python scripts/profile_data.py` imprime o relatório sem erros.
- **Cada commit** deve passar `ruff format --check` (rode o formatter antes de commitar; sem commits `style` de correção).

## Fluxo
Branch `fase/01-dados` existe (com `docs/00-analise-dados.md` e `docs/decisoes.md`). Commit, push, `gh pr create`, avise o Arquiteto. Não faça merge. Nunca force-push.
