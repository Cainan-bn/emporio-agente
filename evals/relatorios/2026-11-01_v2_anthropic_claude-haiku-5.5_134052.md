# Relatório do eval — prompt v2

- Modelo do agente: `anthropic/claude-haiku-5.5`
- Modelo do juiz: `anthropic/claude-sonnet-5.5`
- Data de execução: 2026-11-01T13:40:52
- **Aprovados: 2/2 (100%)** — falhas determinísticas: 0, falhas do juiz: 0

## Por categoria

| Categoria | Aprovados |
|---|---|
| devolucao | 2/2 |

## Casos

| Caso | Resultado | Ferramentas |
|---|---|---|
| `devolucao_dentro_do_prazo` | ✅ | consultar_pedido, consultar_politicas |
| `troca_por_defeito` | ✅ | consultar_pedido, consultar_politicas |
