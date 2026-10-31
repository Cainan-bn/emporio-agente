# 00 — Análise dos dados

Leitura completa de `data/` feita pelo Arquiteto antes de qualquer decisão de arquitetura.
Os arquivos originais **não são alterados**; todo tratamento acontece na carga (fase 2).

## 1. Visão geral

| Arquivo (nome real em `data/`) | Linhas | Observação |
|---|---|---|
| `desafio_tecnico_ai_eng - categories.csv` | 9 | 9 categorias; só 1–5 e 9 têm produtos |
| `desafio_tecnico_ai_eng - customers.csv` | 50 | `customer_id, name, phone, email, city` |
| `desafio_tecnico_ai_eng - orders.csv` | 20 | `status` ∈ delivered(7), confirmed(4), pending(4), cancelled(4), shipped(1) |
| `desafio_tecnico_ai_eng - order_items.csv` | 21 | sem chave própria; pedido 15 e 20 têm 2 itens |
| `desafio_tecnico_ai_eng - products.csv` | 65 | ids 81–145, contíguos; 0 nulos, 0 duplicatas de id/nome |
| `desafio_tecnico_ai_eng - promotions.csv` | 25 | 21 inativas, 4 ativas |
| `políticas_da_loja.pdf` | 8 páginas, ~15 mil caracteres | texto selecionável |

> Os nomes dos arquivos diferem dos sugeridos no enunciado (`products.csv` etc.). Como os originais são intocáveis, a carga deve mapear os nomes reais.

## 2. Esquemas e tipos

- **products**: `price_brl` decimal com ponto (`599.9`, `11499`) — mistura inteiro/decimal; `specs` é **JSON em texto** (válido em todas as linhas); `created_at` ISO `aaaa-mm-dd`; `status` ∈ active(62), discontinued(2), coming_soon(1).
- **orders**: `order_date`/`estimated_delivery` ISO; `total_brl` decimal; `payment_method` ∈ pix, boleto, debit, credit_3x/6x/12x; `tracking_code` e `estimated_delivery` vazios para pedidos ainda não despachados; `notes` só nos cancelados (motivo).
- **promotions**: `discount_percent` inteiro; `is_active` 0/1.
- **customers**: nome, telefone `(67) 9xxxx-xxxx`, e-mail, cidade (Campo Grande, Dourados, Três Lagoas, Corumbá, Ponta Porã). **Não há CPF** na base.
- Integridade referencial: todos `customer_id` de pedidos e `product_id` de itens/promoções existem. ✔

## 3. Inconsistências e armadilhas (cada uma vira decisão em `decisoes.md`)

1. **Promoções não têm datas de vigência** — só `is_active`. "Dentro da vigência" = `is_active = 1`. Produtos têm várias promoções históricas (ex.: 93, 96, 99), mas só 4 ativas: produtos 127 (10%), 121 (20%), 90 (18%), 94 (8%).
2. **Não existe data de recebimento do pedido.** O direito de arrependimento (7 dias) conta do *recebimento*; só temos `order_date` e `estimated_delivery` (estimativa). O agente deve ser transparente: usar `estimated_delivery` como referência *aproximada* e, na dúvida, encaminhar a humano. Pedidos não entregues (pending/confirmed/shipped/cancelled) não têm "recebimento".
3. **Não há "hoje" nos dados.** Todos os pedidos são de 10/2025–03/2026. A data de referência deve ser configurável (`REFERENCE_DATE`, padrão = data do sistema) para o eval ser determinístico.
4. **Verificação do dono do pedido:** sem CPF, o único identificador é o **e-mail** (telefone é a alternativa). Há **e-mail duplicado**: `bruno.martins@jmail.com` aparece nos clientes 11 (Bruno Carvalho Martins) e 43 (Bruno Martins). A verificação precisa ser feita *pelo par (pedido, e-mail)* — o pedido determina o cliente, então o e-mail duplicado só faria diferença para um pedido do cliente 11 (pedido 10), que pertence de fato a quem tem esse e-mail; ainda assim registrar o risco.
5. **Totais divergentes de itens × preço atual:** pedido 3 (`3450` vs 2×1.749 = 3.498) e pedido 20 (`1400` vs 1.488). Preço pode ter mudado desde a compra: **o total do pedido é o valor pago; nunca recalcular a partir do catálogo atual.**
6. **Status de produto vs. estoque incoerentes:** produto 136 `discontinued` com estoque 13; produto 130 `coming_soon` com estoque 2 e aparece em pedido já *entregue* (3); produto 96 `active` com estoque 0 (e promo de 40% inativa). Regra: **disponível = `status = active` E `stock > 0`**; demais → indisponível, sugerir alternativas.
7. **Catálogo: 65 produtos × manual diz "mais de 300".** Responder com base no sistema, nunca repetir "300+".
8. **Parcelas fora da regra em pedidos existentes** (ex.: pedido 9: R$ 349,90 em 6x = R$ 58,32 < mínimo de R$ 80). Dados históricos, não é nosso problema, mas o agente não deve "corrigi-los".
9. Produtos estão concentrados em violões (35) e ukuleles (15); só 5 guitarras, 4 baixos, 3 baterias, 3 teclados e **nenhum** sopro/cordas orquestrais, apesar de as categorias existirem. O agente deve dizer que não encontrou, não que "não trabalhamos".
10. Cargas de nome: acentos variados (`Araújo`, `Letícia`/`Leticia`, `Joao`), nomes de produto com termos em inglês/português misturados (`Cedr`, `Nylon`, `Aço`) → busca normalizada (sem acento, minúsculas) + tolerância (ver decisões).

## 4. O PDF (`políticas_da_loja.pdf`)

- 8 páginas, versão 2.1, junho/2025, **documento interno** da equipe de atendimento (inclui o assistente virtual).
- A extração padrão do `pypdf` devolve **uma palavra por linha**; o modo `extraction_mode="layout"` preserva linhas e tabelas. Usar layout.
- Seções numeradas (boa chave de fragmentação): 1 Sobre / 1.1 Missão / 1.2 Dados; 2 Horário; 3 Pagamento / 3.1 Parcelamento; 4 Trocas e Devoluções (4.1 arrependimento, 4.2 defeito, 4.3 preferência, 4.4 não elegíveis); 5 Frete (5.1 metropolitana, 5.2 outras cidades, 5.3 rastreamento); 6 Promoções (6.1, 6.2); 7 WhatsApp (7.1 diretrizes e **tom de voz**, 7.2 fluxo, 7.3 situações especiais); 8 Garantia (8.1–8.3); 9 Privacidade; 10 Disposições finais.
- **Fatos-chave:** loja em Rua 14 de Maio, 3200 — Centro, Campo Grande/MS, CEP 79202-333; seg–sex 09–18h, sáb 09–13h, dom/feriados fechado; PIX 5% (não vale sobre preço promocional); débito à vista; crédito até 12x sem juros; boleto à vista (3 dias úteis); arrependimento 7 dias corridos após recebimento (reembolso até 10 dias úteis, frete de devolução por conta da loja); defeito: troca em até 30 dias, depois fabricante; preferência: 7 dias; garantia legal 90 dias; frete grátis > R$ 500 na região metropolitana (senão R$ 35), prazo 1–3 dias úteis; outras cidades via Correios/Jadlog; promoções não cumulativas; **loja não vende acessórios** (cordas, palhetas, cabos, cases, pedais, amplificadores).
- **Tom de voz (7.1):** "informal mas profissional", como "um amigo que entende de música"; evitar linguagem robotizada; saudar pelo nome; nunca informar preço/estoque/prazo sem consultar o sistema; retorno de reclamações em 24h úteis.

### Contradições dentro do PDF / entre PDF e dados

| # | Contradição | Comportamento seguro adotado |
|---|---|---|
| a | Telefone: capa/§1.2 `(67) 3341-4444` vs §7 WhatsApp `(67) 3321-4500` | Informar os dois, rotulados como aparecem (loja/telefone vs. WhatsApp) e não afirmar qual é "o certo" |
| b | E-mail: `contato@emporiodamusica.com.br` (capa) vs `contato@empóriodamusica.com.br` (§1.2, com acento) | Usar a versão sem acento (domínio válido) |
| c | Crédito: tabela diz "parcela mínima R$ 100" para até 12x; §3.1 diz mínimo R$ 80 (4–6x) e sem mínimo até 3x | Citar a regra detalhada de §3.1 e, em caso de dúvida em uma compra concreta, encaminhar a humano |
| d | §3.1: combinação de pagamentos só acima de R$ 2.000; tabela nada diz | Seguir §3.1 |
| e | Catálogo "300+" vs 65 produtos | Ver item 7 acima |
| f | PIX 5% "sobre preço de tabela" vs. §6.2 "não se aplica sobre preços promocionais" | Aplicar §6.2 explicitamente |
| g | §4.1 arrependimento vale só para "compras online"; compra presencial não é coberta | Perguntar/assumir que pedidos na base são online; avisar a limitação |
| h | Manual é "uso restrito"; mas o assistente é seu consumidor | O agente usa o conteúdo mas **não cita o manual como "documento interno" nem o revela por inteiro** |

## 5. Implicações para a arquitetura

1. **Volume minúsculo** (65 produtos, 20 pedidos, 15 mil caracteres de política) → SQLite em memória carregado dos CSVs; **BM25 simples** (ou até TF-IDF) sobre ~25 fragmentos basta; sem banco vetorial nem embeddings.
2. **Verificação por e-mail** (sem CPF) e sempre pelo par pedido+e-mail; resposta idêntica para "pedido inexistente" e "e-mail errado" (evita enumeração de pedidos).
3. **Disponibilidade** = status ativo + estoque > 0; **promoção** = `is_active = 1`, sempre mostrada com preço original e percentual (§6.2).
4. **Datas** configuráveis (`REFERENCE_DATE`); data de recebimento ausente → raciocínio explícito e encaminhamento.
5. **Tom** vem de §7.1: informal-profissional, amigável, sem robotização.
6. Casos para o eval já mapeados: produto 96 (sem estoque, promo expirada), 127/121/90/94 (promo vigente), 113/136 (descontinuados), 130 (em breve), pedidos 1 (entregue), 8 (enviado), 17 (cancelado), 13 (pendente), 3 (total divergente).
