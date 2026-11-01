# Empório da Música — Agente de Atendimento

Assistente virtual (o **Téo**) para o atendimento da loja Empório da Música, de Campo Grande/MS. O Téo conversa em português, consulta os dados da loja por *function calling* e responde sobre catálogo, promoções, pedidos e políticas, sem inventar informação.

O projeto não usa framework de agente (LangChain/LlamaIndex): o loop de conversa, o registro de ferramentas e o cliente do modelo são código próprio, para que dê para ver e testar o que acontece por baixo (ADR-001).

## Funcionalidades

- **Catálogo:** busca e consulta de produtos (preço, estoque, produto descontinuado ou "em breve") com alternativas disponíveis.
- **Promoções:** mostra preço original, percentual e preço promocional, só das promoções vigentes.
- **Pedidos:** status e rastreio, **somente** com número do pedido e e-mail do dono. A falha de verificação usa uma mensagem genérica, sem dizer qual dado está errado.
- **Políticas da loja:** troca, devolução, pagamento, frete, garantia, horário e endereço, a partir do manual em PDF, citando a seção (ex.: "§4.1").
- **Devolução e troca:** o Téo informa a regra e as datas, mas **não aprova** nada: a equipe confirma, e ele oferece o encaminhamento para um atendente.
- **Segurança:** recusa assuntos fora da loja, ignora tentativas de mudar a persona ou revelar o prompt, não revela dados de outros clientes e, quando não sabe, diz que não sabe.
- **CLI interativa** com os comandos `/sair`, `/limpar` e `/ajuda`, e modo `--debug` que mostra as ferramentas chamadas (com e-mails mascarados).

## Tecnologias

- Python 3.11+ (testado com 3.14)
- SDK `openai` apontando para o **OpenCode Go** (API compatível com OpenAI); modelo padrão `deepseek-v4.1-flash`
- SQLite em memória, carregado dos CSVs originais
- `pypdf` + `rank-bm25` para as políticas (fragmentos por seção, busca BM25)
- `pytest` e `ruff` para testes e estilo

## Pré-requisitos

- Python 3.11 ou superior
- Uma chave de API do **OpenCode Go** com acesso ao modelo `deepseek-v4.1-flash`. Esse modelo exige a região **Global** nas configurações de privacidade do workspace do OpenCode.

## Instalação

```bash
git clone https://github.com/Cainan-bn/emporio-agente.git
cd emporio-agente
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt   # dependências de execução (requirements.txt), pytest e ruff
pip install -e .                      # cria o comando `emporio`; precisa vir depois da linha acima
```

## Configuração

Copie o arquivo de exemplo e preencha a chave:

```bash
cp .env.example .env
# edite o .env e preencha OPENCODE_API_KEY
```

O `.env` não é versionado. As variáveis (todas com padrão, exceto a chave):

| Variável | Padrão | Para quê |
|---|---|---|
| `OPENCODE_API_KEY` | — (obrigatória) | Chave da API |
| `OPENCODE_BASE_URL` | `https://opencode.ai/inference/go/openai/v1` | Endereço da API |
| `MODEL_ID` | `deepseek-v4.1-flash` | Modelo do agente |
| `JUDGE_MODEL_ID` | `deepseek-v4.1-flash` | Modelo do juiz do eval |
| `PROMPT_VERSION` | `v3` | Prompt de sistema (`src/emporio/prompts/vN.md`) |
| `REFERENCE_DATE` | vazio (data do sistema) | "Hoje" para cálculos de prazo |
| `MAX_TOOL_ITERATIONS` | `6` | Limite de rodadas de ferramentas por mensagem |
| `LLM_TIMEOUT_SECONDS` / `LLM_MAX_RETRIES` | `30` / `3` | Timeout e tentativas (backoff exponencial com jitter) |
| `LLM_TEMPERATURE` / `LLM_MAX_TOKENS` | `0.2` / `1024` | Parâmetros de geração |
| `LOG_LEVEL` | `INFO` | Nível de log |

## Uso

```bash
emporio              # ou: python -m emporio
emporio --debug      # mostra as ferramentas chamadas
emporio --data-dir caminho/dos/dados
```

Exemplos de conversa:

```
Você: Tem violão até R$ 1.000?
Você: Qual o status do pedido 7? Meu e-mail é leticia.rocha@jmail.com
Você: Posso devolver? Me arrependi da compra.
Você: Vocês parcelam em 10x? E no PIX tem desconto?
```

Sem `OPENCODE_API_KEY`, o programa explica o que falta e sai com código 2, sem *stack trace*.

### Exemplos de interação

A pasta [`examples/`](examples/) traz 4 conversas reais com o agente, cada uma mostrando as chamadas de ferramenta (nome, argumentos e resultado) que o Téo fez nos bastidores:

| Exemplo | Cenário |
|---|---|
| [`01-catalogo-violoes.md`](examples/01-catalogo-violoes.md) | Consulta de catálogo: violões até R$ 1.000 |
| [`02-endereco-da-loja.md`](examples/02-endereco-da-loja.md) | Informação geral: endereço e horário da loja |
| [`03-preco-takamine-gd20.md`](examples/03-preco-takamine-gd20.md) | Consulta de preço de um produto |
| [`04-devolucao-pedido.md`](examples/04-devolucao-pedido.md) | Cruzamento de pedido e política: pedido de devolução |

Para refazê-los (faz chamadas reais ao modelo e usa a data fixa 20/02/2026): `python scripts/gerar_exemplos.py`.

## Estrutura do Projeto

```
data/                   CSVs e PDF originais (não alterar)
docs/                   análise dos dados, persona, decisões (ADRs) e specs das fases
evals/                  casos dourados, checagens, juiz, runner e relatórios
examples/               transcrições reais de exemplo, com as chamadas de ferramenta
scripts/                profiling dos dados, repetição do eval e geração dos exemplos
src/emporio/
  agent.py              loop de conversa com function calling, histórico e limites
  llm.py                cliente do modelo (retry, backoff, sem vazar chave)
  cli.py, config.py     chat interativo e configuração por ambiente
  data/                 carga dos CSVs para SQLite e repositórios
  policies/             ingestão do PDF, fragmentação por seção e retriever BM25
  tools/                as 7 ferramentas e o registro com validação
  prompts/              prompts de sistema versionados (v1, v2, v3)
tests/                  testes sem rede
```

As ferramentas expostas ao modelo: `buscar_produtos`, `consultar_produto`, `consultar_promocoes`, `consultar_pedido`, `consultar_politicas`, `consultar_loja` e `encaminhar_para_humano`.

## Testes

```bash
ruff check .
ruff format --check .
pytest               # 303 testes, sem chamadas de rede
```

### Avaliação do agente (eval)

O eval roda 28 conversas em português contra o modelo real, com checagens determinísticas (ferramentas chamadas, preços, identificadores) e um LLM-juiz com rubrica por caso. **Faz chamadas reais e consome o limite do plano.**

```bash
python evals/run.py --prompt v3                  # todos os casos
python evals/run.py --only produto_inexistente   # casos específicos
python evals/run.py --no-judge                   # só as checagens determinísticas
scripts/rodar_eval_repetido.sh v3 3              # 3 rodadas (o modelo varia entre execuções)
```

Os relatórios (`.json` com a conversa completa, desde a fase 6, e `.md`) ficam em `evals/relatorios/`. Resultado atual do prompt padrão (`v3`, `deepseek-v4.1-flash`, 3 rodadas): 27, 28 e 28 de 28 casos; o `v1` fez 26, 26 e 27. Detalhes e limites desse resultado no ADR-014 e no ADR-015.

## Decisões e limites conhecidos

As decisões de arquitetura estão em [`docs/decisoes.md`](docs/decisoes.md) (15 ADRs). Vale saber:

- **Juiz = mesmo modelo do agente.** Ele tende a ser mais condescendente do que um juiz maior, e a amostra do eval é pequena; o modelo varia entre execuções.
- **Provedor.** O projeto começou no OpenRouter e migrou para o OpenCode Go (ADR-013). O Go é pensado para agentes de código, tem limites de uso por janela e monitora o tráfego; para uso em produção convém uma API paga por uso (basta trocar `OPENCODE_BASE_URL`, a chave e o `MODEL_ID`). Os ADRs mais antigos que citam OpenRouter são histórico.
- **Sem persistência.** Os dados são carregados em memória a cada execução e a conversa não é salva.
- **Identificação por e-mail.** A base não tem CPF; o e-mail é o identificador disponível, e há e-mails duplicados nos clientes 11 e 43, aprovados como estão.
- **Data de recebimento.** Os pedidos não têm data de recebimento; o prazo de arrependimento usa a entrega estimada como aproximação, e o Téo diz isso ao cliente (ADR-008).
- **Busca limitada a 8 itens.** `src/emporio/tools/search_products.py` chama a busca com `limit=8`: `buscar_produtos` devolve no máximo 8 itens, sem paginação e sem indicar que há mais resultados. Em [`examples/01-catalogo-violoes.md`](examples/01-catalogo-violoes.md) o Téo diz "Achei 7 violões em estoque até R$ 1.000", mas o CSV tem 12 violões ativos, em estoque e até R$ 1.000 — o retorno trouxe 7 violões e o ukulele Kala KA-B (que casa por citar "violão" na descrição). O agente apresenta a contagem do retorno como se fosse o total, e o cliente pode achar que não há mais opções. Não há mitigação implementada; candidatos para o futuro: avisar no prompt que a lista é parcial, aumentar o limite ou paginar a ferramenta informando o total.

## Licença

Nenhuma licença foi definida para este projeto.

## Notas de processo

Registros honestos do histórico, mantido sem reescrita:

- Fase 3: o Arquiteto assumiu o código do `retriever` depois de duas rodadas sem convergir com o Dev; o QA revisou como se fosse do Dev (resolvido).
- Há commits vermelhos ou grandes no histórico, como o `e7c7605` (teste do marcador de truncamento do juiz commitado antes da implementação, que veio no `3bb2425`). Não foram reescritos.
- Dados originais: os e-mails duplicados dos clientes 11 e 43 foram aprovados como estão.
- Provedor: o projeto migrou do OpenRouter para o OpenCode Go (ADR-013); relatórios antigos de eval usam outro modelo.
