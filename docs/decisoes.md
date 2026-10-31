# Decisões de arquitetura (ADR curto)

Formato: contexto → decisão → alternativas → consequência. Atualizado ao final de cada fase.

## ADR-001 — Sem framework de agente (LangChain/LlamaIndex)
- **Contexto:** 6 ferramentas, loop de conversa simples, avaliador quer ver o que acontece por baixo.
- **Decisão:** loop de *function calling* nativo com o SDK `openai` apontando para o OpenRouter.
- **Alternativas:** LangChain, LlamaIndex.
- **Consequência:** menos dependências e controle total dos limites (iterações, timeout, retry); mais código próprio para testar.

## ADR-002 — Dados em SQLite em memória, carregados dos CSVs originais
- **Contexto:** 65 produtos, 20 pedidos, 50 clientes (ver `00-analise-dados.md`). Arquivos de `data/` são intocáveis e têm nomes `desafio_tecnico_ai_eng - *.csv`.
- **Decisão:** carga na inicialização para SQLite, com camada de repositório; mapeamento explícito dos nomes reais dos arquivos.
- **Alternativas:** pandas (dependência pesada para o volume), consultar CSV direto.
- **Consequência:** SQL simples e testável; sem estado persistente.

## ADR-003 — Políticas: BM25 sobre fragmentos por seção
- **Contexto:** PDF de 8 páginas (~14 mil caracteres, ~25 seções/subseções).
- **Decisão:** extrair com `pypdf` em modo `layout`, fragmentar por seção numerada preservando número e título como metadado, indexar com BM25 (`rank_bm25`) com normalização de acentos/caixa.
- **Alternativas:** embeddings/banco vetorial (sobre-engenharia para o volume), colocar o PDF inteiro no prompt (perde a citação de seção e escala mal).
- **Consequência:** resposta cita a seção ("Política §4.1"); sem custo de embeddings.

## ADR-004 — Verificação de titularidade do pedido por e-mail
- **Contexto:** não há CPF na base; e-mail é o identificador disponível; existe e-mail duplicado (clientes 11 e 43).
- **Decisão:** `consultar_pedido(numero_pedido, email)` só devolve dados se o e-mail bater (case-insensitive) com o cliente **dono do pedido**. Falha de verificação e pedido inexistente têm a **mesma resposta** (sem enumeração).
- **Alternativas:** telefone, CPF parcial (inexistente).
- **Consequência:** simples e seguro; o e-mail duplicado não permite acessar pedido de outro cliente porque o pedido já determina o cliente.

## ADR-005 — Vigência de promoção = `is_active = 1`
- **Contexto:** `promotions.csv` não tem datas.
- **Decisão:** vigente é só `is_active = 1`; sempre mostrar preço original, percentual e preço final (política §6.2); sem acúmulo e sem desconto PIX sobre preço promocional.
- **Consequência:** limitação documentada no README.

## ADR-006 — Disponibilidade e produtos inconsistentes
- **Decisão:** disponível = `status = 'active'` **e** `stock_quantity > 0`. `discontinued`/`coming_soon` nunca são ofertados como disponíveis, mesmo com estoque.

## ADR-007 — Data de referência configurável
- **Contexto:** não há "hoje" nos dados; pedidos vão de 10/2025 a 03/2026; o eval precisa ser determinístico.
- **Decisão:** `REFERENCE_DATE` (ISO) opcional; padrão = data do sistema.

## ADR-008 — Devolução sem data de recebimento
- **Contexto:** prazo de 7 dias corre do recebimento (política §4.1); a base só tem `estimated_delivery`.
- **Decisão:** usar `estimated_delivery` como *aproximação declarada* para pedidos `delivered`; o agente explica a premissa, nunca aprova a devolução (não tem autoridade) e oferece encaminhar a um atendente. Pedido não entregue → sem direito a devolução ainda (informa status). §4.1 vale para compra online: o agente declara a premissa.

## ADR-009 — Contradições do PDF
- **Decisão:** seguir a regra mais específica (§3.1 sobre a tabela), citar os dois telefones rotulados, usar e-mail sem acento, nunca repetir "300+ produtos". Na dúvida, encaminhar a humano. Detalhes em `00-analise-dados.md` §4.

## ADR-010 — Modelo do agente
- **Decisão (provisória):** `anthropic/claude-haiku-5.5` via OpenRouter (`MODEL_ID`), juiz do eval `anthropic/claude-sonnet-5.5`. Será confirmado/ajustado na fase 6 com base nos resultados do eval.
- **Alternativas:** `deepseek/deepseek-v4-flash`, `google/gemini-3.x-flash`.

## ADR-011 — Ferramentas: registro próprio, saída JSON em português, cálculo em código
- **Contexto:** o LLM não deve fazer contas de data/preço nem ver dados pessoais; erros de ferramenta não podem vazar (regra 8).
- **Decisão:** `ToolRegistry` próprio (sem framework) com schema JSON (formato `tools` da API OpenAI), validação mínima de argumentos e `execute()` que **nunca levanta**: erro → `{"erro": "..."}` genérico, detalhe só no log (sem PII). Valores monetários/datas já formatados em pt-BR; dias decorridos calculados em código a partir de `REFERENCE_DATE`.
- **Sétima ferramenta:** `consultar_loja()` devolve endereço, horários e **os dois telefones rotulados** (1.2 e 7) por `get_section`, de forma determinística — o retriever BM25 não garante trazer a seção 7 para "telefone" (recomendação do QA na fase 3). Mantém `consultar_politicas` para o resto.
- **Consequência:** a decisão de elegibilidade de devolução continua do LLM (com a política citada), mas a aritmética de datas é determinística.
