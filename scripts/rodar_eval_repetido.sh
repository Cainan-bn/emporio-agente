#!/usr/bin/env bash
# Roda o eval N vezes para uma versão de prompt (o modelo varia entre execuções).
# Uso: scripts/rodar_eval_repetido.sh v1 3
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
versao="${1:?informe a versão do prompt, ex.: v1}"
vezes="${2:-3}"
for i in $(seq 1 "$vezes"); do
  echo "== execução $i/$vezes (prompt $versao)"
  # 2 workers: poupa o limite do plano do OpenCode Go
  "${PYTHON:-python3}" evals/run.py --prompt "$versao" --workers 2
  codigo=$?
  # 0 = tudo aprovado, 1 = há casos reprovados; qualquer outro código é erro de configuração/API
  if [ "$codigo" -gt 1 ]; then
    echo "erro (código $codigo): abortando" >&2
    exit "$codigo"
  fi
done
