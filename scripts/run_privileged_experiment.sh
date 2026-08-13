#!/usr/bin/env bash
# 後方互換用。新規の実験は run_experiment.sh <experiment> から起動する。

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
exec "$SCRIPT_DIR/run_experiment.sh" privileged_critic "$@"
