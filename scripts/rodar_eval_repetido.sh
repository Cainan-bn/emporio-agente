#!/usr/bin/env bash
# Roda o eval N vezes para uma versão de prompt (o modelo varia entre execuções).
# Uso: scripts/rodar_eval_repetido.sh v1 3
set -euo pipefail
cd "$(dirname "$0")/.."
versao="${1:?informe a versão do prompt, ex.: v1}"
vezes="${2:-3}"
for i in $(seq 1 "$vezes"); do
  echo "== execução $i/$vezes (prompt $versao)"
  python evals/run.py --prompt "$versao" || true   # código 1 = há casos reprovados
done
