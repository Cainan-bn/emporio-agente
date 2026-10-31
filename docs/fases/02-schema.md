# Fase 2 — Schema e repositórios (`fase/02-schema`)

**Objetivo:** carregar os CSVs originais em SQLite (em memória) e expor **repositórios** tipados, sem lógica de LLM. Decisões: ADR-002, 004, 005, 006 (`docs/decisoes.md`) e achados em `docs/00-analise-dados.md`.

## Arquivos
- `src/emporio/text.py` — `normalize(text) -> str` (NFKD, remove acentos, minúsculas, colapsa espaços/pontuação) e `compact(text) -> str` (só `[a-z0-9]`; ex.: "GD 20" e "gd20" → `gd20`).
- `src/emporio/formatting.py` — `format_brl(Decimal) -> "R$ 1.234,56"`, `format_date(date) -> "dd/mm/aaaa"`. Testes com 0, centavos, milhares e valores ≥ 1 milhão.
- `src/emporio/data/models.py` — `@dataclass(frozen=True)`: `Category`, `Product` (preço `Decimal`; `specs: dict`; propriedade `is_available` = `status == "active" and stock_quantity > 0`), `Promotion`, `OrderItem` (com `product_name`), `Order` (`items`, total `Decimal`, `order_date`/`estimated_delivery` como `date | None`; **sem** dados pessoais do cliente), `Customer` (uso interno do repositório; nunca retornado pelas tools).
- `src/emporio/data/loader.py` — `load_database(data_dir: Path) -> sqlite3.Connection`: localiza arquivos por **sufixo** (reutilize a lógica de `scripts/profile_data.py` movendo-a para o pacote, e faça o script importar dela, sem duplicar), cria o schema (tabelas, PK/FK, `CHECK` de domínio de `status`), converte tipos (preço/total → inteiro em centavos no banco, datas ISO), tolera vazio → `NULL`. Falha com mensagem clara em português se arquivo faltar. **Não altera `data/`.**
- `src/emporio/data/repositories.py`:
  - `ProductRepository`: `search(term, category=None, max_price=None, only_available=False, limit=10) -> list[Product]`; `get(product_id)`; `find_by_name(term) -> list[Product]`; `list_categories()`.
  - `PromotionRepository`: `get_active_for_product(product_id) -> Promotion | None` (só `is_active = 1`); `list_active()`; `final_price(product, promotion) -> Decimal` (2 casas, arredondamento `ROUND_HALF_UP`).
  - `OrderRepository`: `get_for_customer(order_id: int, email: str) -> Order | None` — devolve o pedido **somente** se o e-mail (strip + case-insensitive) pertencer ao cliente dono do pedido; **qualquer falha (pedido inexistente, e-mail errado, e-mail vazio, entrada não numérica) retorna `None`**, indistinguível (ADR-004).
- `src/emporio/data/__init__.py` exporta o necessário.

## Busca de produtos (requisitos)
Deve tolerar: caixa e acentos ("violao" ↔ "Violão"), parcial ("gd20", "gd 20" → Takamine GD20…), marca + modelo ("takamine gd20"), categoria por nome ("violões", "ukulele"/"ukuleles", "guitarra"), variação de plural. Ranking: (1) todos os tokens presentes no nome/descrição/categoria normalizados; (2) comparação `compact`; (3) `difflib.SequenceMatcher` para typos leves ("yamha" → Yamaha) com limiar fixo documentado. Sem dependência nova. Termo vazio → lista vazia (não "tudo"). `max_price` em reais, inclusive. `only_available=True` aplica `is_available`. Resultado determinístico (desempate por preço, depois id).

## Testes (`tests/`, sem rede, usam `data/` real)
- `test_text.py`, `test_formatting.py`.
- `test_loader.py`: contagens 65/20/50/25/9/22; preço de `product_id=93` é `Decimal("11499")`; arquivo ausente → erro claro (tmp_path); `data/` não é modificado (checksum antes/depois).
- `test_product_repository.py`: "violao"/"Violão"/"VIOLÃO"; "gd 20"; "yamha"; filtro `max_price=1000` em violões (confira cada item ≤ 1000); `only_available` exclui produto 96 (estoque 0), 113 e 136 (descontinuados) e 130 (`coming_soon`); termo vazio; termo inexistente ("trombone") → vazio.
- `test_promotion_repository.py`: ativas = {127, 121, 90, 94}; produto 96 (promo expirada) → `None`; `final_price` de 121 (R$ 549,00 −20%) = R$ 439,20.
- `test_order_repository.py`: pedido 1 + e-mail do cliente 3 → ok com itens; e-mail de outro cliente → `None`; pedido 999 → `None`; maiúsculas/espaços no e-mail → ok; `"1; DROP TABLE orders"` e `None`/`""` → `None` (consultas parametrizadas, nunca f-string em SQL); total do pedido 3 = R$ 3.450,00 (valor pago, **não** recalculado); pedido 17 devolve `notes` do cancelamento; `Order` não contém e-mail/telefone/nome do cliente.

## Critérios de aceite
`ruff check .`, `ruff format --check .`, `pytest` verdes em venv limpo; **cada commit** passa `ruff format --check`; commits pequenos em português (ex.: `feat(texto): normaliza acentos e caixa`, `feat(schema): cria tabelas no SQLite`, `feat(repositorios): busca de produtos`…), teste no mesmo commit do código; SQL sempre parametrizado; sem dependências novas; `data/` intocado; sem `style` de correção; erros próprios (ex.: `DataLoadError`) em vez de `FileNotFoundError` cru para arquivos ausentes/múltiplos.

## Fluxo
Branch `fase/02-schema` já existe (com esta spec). `git pull`, implemente, push, `gh pr create` (base `main`), avise o Arquiteto. Não faça merge. Nunca force-push.
