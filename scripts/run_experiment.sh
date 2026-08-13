#!/usr/bin/env bash
# experiments/<name> のTOML定義を読み、全variantを指定GPU群で比較実行する。
# Hand Value shaping比較例:
#   DRY_RUN=1 ./scripts/run_experiment.sh hand_value_shaping
#   RUN_KIND=smoke_test TIMESTEPS=10000 GPU_IDS=0,1 \
#     ./scripts/run_experiment.sh hand_value_shaping

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd -P)"
PYTHON="$REPO_ROOT/.venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
    echo "error: expected executable Python at $PYTHON" >&2
    exit 2
fi

exec "$PYTHON" "$SCRIPT_DIR/run_experiment.py" "$@"
