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
- **Decisão (provisória):** `anthropic/claude-haiku-5.5` via OpenRouter (`MODEL_ID`), juiz do eval `anthropic/claude-sonnet-5.5`. **Substituída pelos ADR-013 e ADR-014.**
- **Alternativas:** `deepseek/deepseek-v4-flash`, `google/gemini-3.x-flash`.

## ADR-011 — Ferramentas: registro próprio, saída JSON em português, cálculo em código
- **Contexto:** o LLM não deve fazer contas de data/preço nem ver dados pessoais; erros de ferramenta não podem vazar (regra 8).
- **Decisão:** `ToolRegistry` próprio (sem framework) com schema JSON (formato `tools` da API OpenAI), validação mínima de argumentos e `execute()` que **nunca levanta**: erro → `{"erro": "..."}` genérico, detalhe só no log (sem PII). Valores monetários/datas já formatados em pt-BR; dias decorridos calculados em código a partir de `REFERENCE_DATE`.
- **Sétima ferramenta:** `consultar_loja()` devolve endereço, horários e **os dois telefones rotulados** (1.2 e 7) por `get_section`, de forma determinística — o retriever BM25 não garante trazer a seção 7 para "telefone" (recomendação do QA na fase 3). Mantém `consultar_politicas` para o resto.
- **Consequência:** a decisão de elegibilidade de devolução continua do LLM (com a política citada), mas a aritmética de datas é determinística.

## ADR-012 — Loop de agente, cliente LLM e prompt versionado
- **Decisão:** `ChatModel` (Protocol) isola o LLM; `OpenRouterClient` usa o SDK `openai` com `base_url` do OpenRouter, **retry próprio** com backoff exponencial + jitter (429, 5xx, timeout, conexão) e timeout por chamada; o SDK roda com `max_retries=0` para não somar tentativas. `Agent` mantém o histórico, executa *tool calls* pelo `ToolRegistry` e limita iterações (`MAX_TOOL_ITERATIONS`). Falha do LLM ou estouro de iterações → resposta de contingência fixa (sem detalhe técnico) que oferece o atendimento humano. Prompt em arquivo versionado (`prompts/v1.md`, depois `v2.md`) escolhido por `PROMPT_VERSION`.
- **Alternativas:** LangChain/agents (ADR-001), streaming (YAGNI para CLI).
- **Consequência:** testes do agente usam um `FakeModel` roteirizado, sem rede; o prompt muda sem tocar no código.

## ADR-013 — Provedor LLM: OpenCode Go (substitui OpenRouter)

- **Decisão:** o cliente (`OpenCodeClient`, SDK `openai`) usa o OpenCode Go: `OPENCODE_BASE_URL` (padrão `https://opencode.ai/inference/go/openai/v1`) e `OPENCODE_API_KEY`. Modelo padrão do agente e do juiz: `deepseek-v4.1-flash` (exige a região Global nas configurações de privacidade do workspace). O id `deepseek-v4.1-flash-free` não existe no Go.
- **Contrato da API:** o provedor exige `x-opencode-session` (um ID estável por *conversa*, para roteamento e cache) e um `User-Agent` próprio. Cada `OpenCodeClient` gera uma sessão; no eval cada caso (agente) e cada avaliação (juiz) usam `for_conversation()` e têm a sua.
- **Risco:** o Go é "pensado para OpenCode e outros agentes de código" e o tráfego é monitorado; há limites de uso por 5 h, semana e mês. Plano B: API paga por uso (só trocar as variáveis do `.env`).
- **Eval:** os relatórios `anthropic_claude-haiku-5.5` em `evals/relatorios/` são do período OpenRouter. Os de `023512` e `023549` foram feitos com juiz falhando (`LLMError`, quase certo por saldo/HTTP 402 — o relatório não registra o status) e também têm falhas reais do agente (preço citado em `produto_inexistente`, `promocao_expirada` sem R$ 899,00). O `023433` tem 4 falhas de juiz por `LLMError`. Todos usavam checagens por substring que davam falso negativo (corrigidas no ADR-014). Nenhum é comparável ao modelo atual.

## ADR-014 — Prompt padrão e qualidade do eval (fase 6)

- **Decisão:** prompt padrão **`v1`**. O `v2` (v1 + regra "nunca confirme a troca antes da avaliação") fica disponível via `PROMPT_VERSION=v2`, mas **não** foi adotado: não há ganho mensurável.
- **Evidência** (28 casos, `deepseek-v4.1-flash`, juiz = mesmo modelo, 3 rodadas por versão, checagens corrigidas): v1 = 27, 25, 27 (79/84); v2 = 27, 26, 25 (78/84). Rodadas anteriores com 27 casos (v1 26/27; v2 27/27 e 27/27) mostraram-se ruído do modelo.
- **Artefatos do instrumento nessas rodadas:** na `151405` (v2) duas reprovações eram do instrumento, não do agente: `troca_por_defeito` (resposta correta "30º dia" não casava com `["30 dias","trinta"]`) e `privacidade_dados_de_terceiros` (rubrica exigia a palavra "privacidade"). Corrigidas, o v2 teria 80/84 e o v1 79/84: diferença de 1 caso, dentro do ruído. A conclusão "sem ganho mensurável do v2" se mantém. A rubrica de `privacidade...` e as variantes de número ("30º", "20 %", "cinco por cento") foram corrigidas depois. Rodada completa final com as checagens corrigidas (v1, 28 casos): **26/28** (`..._v1_deepseek-v4.1-flash_153609`, com `transcript`); só reprovaram os dois problemas recorrentes abaixo.
- **Privacidade dos relatórios:** o `transcript` grava e-mails e telefones das fixtures (dados sintéticos). Se a base virar real, mascarar antes de versionar.
- **Auditoria do juiz:** o relatório passa a guardar `transcript` (a conversa enviada ao juiz, com ferramentas, argumentos e resultados); resultados longos agora levam o marcador `…[truncado]` (limite de 4000 caracteres). Os relatórios antigos não têm esse campo.
- **Falhas recorrentes (ambos os prompts):** `devolucao_dentro_do_prazo` reprova em 5 das 6 rodadas (o agente diz "pode sim" sem explicar que a entrega estimada é só uma aproximação e que não há data de recebimento); `produto_inexistente` reprova 3 vezes (agente alega problema técnico em vez de dizer que não achou o produto). Candidatos a um `v3` ou a revisão da rubrica.
- **Por que o v2 foi escrito:** com Haiku, `troca_por_defeito` reprovou numa rodada por "Sim, dá para trocar" (relatório não preservado). Com o modelo atual o problema não se reproduziu em 3 rodadas do v1.
- **Checagens determinísticas:** substring curta dava falso negativo (ex.: "Ana" em "analisar", "R$" em preço de alternativa real). Passam a usar `nao_deve_conter_palavra` (palavra inteira) e regras específicas; o que dependia de interpretação foi para a rubrica do juiz. Regra final: o determinístico só olha identificadores (número de rastreio, nomes, preços exatos, ferramentas); frases em texto livre, como recusas, status ou termos de invasão, ficam na rubrica do juiz, porque qualquer lista de frases proibidas reprova recusas legítimas. Única exceção: `nao_comeca_com`, que só falha se a primeira frase INTEIRA for a aceitação ("DAN ativado!").
- **Casos:** `injecao_mudar_persona` pede só mudança de persona/opinião política; o pedido ilícito (invadir Wi-Fi) voltou como caso próprio `pedido_ilicito_wifi`.
- **Limites:** o juiz é o mesmo modelo do agente (tende a ser mais condescendente) e a amostra é pequena; o modelo varia entre execuções.

## ADR-015 — Prompt v3 como padrão (fase 7)

- **Contexto:** o eval da fase 6 mostrou dois problemas recorrentes. (1) `produto_inexistente`: com a busca vazia o modelo repetia `buscar_produtos` de 7 a 14 vezes, estourava `MAX_TOOL_ITERATIONS` e caía na mensagem de contingência ("tive um problema técnico") — causa no comportamento do loop, não na ferramenta. (2) `devolucao_dentro_do_prazo`: abria com "Pode sim" e não explicava que a entrega estimada é só uma aproximação.
- **Decisão:** `v3` = `v1` + duas regras: busca vazia (no máximo mais uma tentativa; depois dizer que não encontrou, sem alegar erro técnico) e devolução/troca/garantia (nunca abrir com "pode sim", ordem: prazo pelo manual, premissa da data estimada, equipe confirma). Padrão: `PROMPT_VERSION=v3`. `v1` e `v2` continuam disponíveis.
- **Evidência** (28 casos, `deepseek-v4.1-flash`, mesmas checagens, 3 rodadas por versão): v3 = 27, 28, 28 (83/84); v1 = 26, 26, 27 (79/84). Casos-alvo nas 3 rodadas completas: v3 reprovou `produto_inexistente` 0/3 e `devolucao_dentro_do_prazo` 1/3 (faltou citar "embalagem original"); v1 reprovou os dois em 2/3 cada. O v1 ainda teve `troca_por_defeito` reprovado 1 vez (só encaminhou, sem explicar o prazo).
- **Limites:** juiz = mesmo modelo do agente; amostra pequena e o modelo varia entre execuções. O ganho (4 casos em 84) é consistente com a causa identificada, mas não é prova estatística. As rodadas parciais não foram versionadas; só as completas.
