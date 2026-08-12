#!/usr/bin/env bash
# Hashimoto 用: baseline PPO と Privileged Critic PPO の比較学習を起動する。
#
# 使い方:
#   ./run_Hashimoto.sh                 # baseline -> privileged の順で両方実行
#   ./run_Hashimoto.sh baseline        # baseline だけ実行
#   ./run_Hashimoto.sh privileged      # privileged だけ実行
#
# 主な上書き例:
#   GPU_ID=1 SEED=43 ./run_Hashimoto.sh both
#   TIMESTEPS=512000 DRY_RUN=1 ./run_Hashimoto.sh privileged

set -Eeuo pipefail

# どこから呼び出しても、パスはリポジトリルートを基準にする。
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

MODE="${1:-both}"
SEED="${SEED:-42}"
NUM_ENVS="${NUM_ENVS:-1000}"
TIMESTEPS="${TIMESTEPS:-5000000}"
GPU_ID="${GPU_ID:-}"
USE_WANDB="${USE_WANDB:-0}"
DRY_RUN="${DRY_RUN:-0}"
ALLOW_CPU="${ALLOW_CPU:-0}"

case "$MODE" in
    both|baseline|privileged) ;;
    *)
        echo "使い方: $0 [both|baseline|privileged]" >&2
        exit 2
        ;;
esac

for value_name in SEED NUM_ENVS TIMESTEPS; do
    value="${!value_name}"
    if [[ ! "$value" =~ ^[0-9]+$ ]] || (( value <= 0 )); then
        echo "$value_name は正の整数で指定してください: $value" >&2
        exit 2
    fi
done

if [[ -n "$GPU_ID" ]]; then
    if [[ ! "$GPU_ID" =~ ^[0-9]+$ ]]; then
        echo "GPU_ID は0以上の整数で指定してください: $GPU_ID" >&2
        exit 2
    fi
    export CUDA_VISIBLE_DEVICES="$GPU_ID"
fi

if [[ "$DRY_RUN" != "1" ]]; then
    command -v uv >/dev/null 2>&1 || {
        echo "uv が見つかりません。uv を利用できる環境で実行してください。" >&2
        exit 1
    }

    # CUDAが使えないまま長時間の学習をCPUで始める事故を防ぐ。
    if ! uv run --frozen python -c \
        'import sys, torch; print(f"PyTorch {torch.__version__} / CUDA available: {torch.cuda.is_available()}"); sys.exit(not torch.cuda.is_available())'
    then
        if [[ "$ALLOW_CPU" != "1" ]]; then
            echo "CUDAを利用できないため開始しません。GPU割り当てとドライバーを確認してください。" >&2
            echo "意図的にCPUで実行する場合だけ ALLOW_CPU=1 を指定してください。" >&2
            exit 1
        fi
        echo "警告: ALLOW_CPU=1 のためCPUで実行します。"
    fi
fi

if [[ -n "$(git status --porcelain 2>/dev/null)" ]]; then
    echo "警告: working tree に未コミットの変更があります。公式比較に使う前に状態を確認してください。"
fi

COMMON_ARGS=(
    --seed "$SEED"
    --num-envs "$NUM_ENVS"
    --total-timesteps "$TIMESTEPS"
    --lr 5.845e-5
    --n-steps 256
    --batch-size 2048
    --n-epochs 10
    --target-kl 0.03
    --ent-coef 0.01
    --clip-range 0.3
    --gamma 0.995
    --shape-hp 0.2
    --shape-mp 0.0
    --shape-money 0.0
    --opponent strategic
    --d-model 192
    --nhead 8
    --num-layers 4
    --dim-feedforward 768
    --features-dim 256
)

run_variant() {
    local variant="$1"
    local started_at run_id run_dir
    local -a variant_args=()
    local -a wandb_args=()

    started_at="$(date -u +%Y%m%dT%H%M%SZ)"
    run_id="pc_${variant}_s${SEED}_${started_at}"
    run_dir="runs/privileged_critic/${run_id}"

    if [[ "$variant" == "privileged" ]]; then
        variant_args=(--privileged-critic)
    fi
    if [[ "$USE_WANDB" == "1" ]]; then
        wandb_args=(
            --wandb
            --wandb-project godfield-rl-privileged-critic
            --wandb-name "$run_id"
        )
    fi

    local -a command=(
        uv run --frozen python train.py
        "${COMMON_ARGS[@]}"
        --tensorboard-log "$run_dir/tensorboard"
        --save-path "$run_dir/checkpoints/final_model"
        "${variant_args[@]}"
        "${wandb_args[@]}"
    )

    echo
    echo "[$variant] 学習設定"
    echo "  run ID   : $run_id"
    echo "  seed     : $SEED"
    echo "  GPU      : ${CUDA_VISIBLE_DEVICES:-自動選択（cuda:0）}"
    echo "  steps    : $TIMESTEPS"
    echo "  envs     : $NUM_ENVS"
    echo "  出力先   : $run_dir"
    printf '  command  : '
    printf '%q ' "${command[@]}"
    printf '\n'

    if [[ "$DRY_RUN" == "1" ]]; then
        return 0
    fi

    mkdir -p "$run_dir/checkpoints" "$run_dir/logs" "$run_dir/wandb"
    printf '%q ' "${command[@]}" > "$run_dir/logs/command.log"
    printf '\n' >> "$run_dir/logs/command.log"

    if WANDB_DIR="$run_dir/wandb" PYTHONUNBUFFERED=1 \
        "${command[@]}" 2>&1 | tee "$run_dir/logs/train.log"
    then
        echo "[$variant] 完了: $run_dir/checkpoints/final_model.zip"
    else
        local status=$?
        echo "[$variant] 異常終了（exit $status）: $run_dir/logs/train.log" >&2
        return "$status"
    fi
}

case "$MODE" in
    both)
        run_variant baseline
        run_variant privileged
        ;;
    baseline|privileged)
        run_variant "$MODE"
        ;;
esac

echo
if [[ "$DRY_RUN" == "1" ]]; then
    echo "ドライラン完了: 学習は開始していません。"
else
    echo "指定された学習がすべて完了しました。"
fi
