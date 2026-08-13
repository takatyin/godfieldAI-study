#!/usr/bin/env bash
# Baseline PPO と Privileged Critic PPO を同一条件・別GPUで実行する。

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd -P)"
cd -- "$REPO_ROOT"

PYTHON="$REPO_ROOT/.venv/bin/python"
EXPERIMENT="privileged_critic"
EXPERIMENT_DIR="$REPO_ROOT/experiments/$EXPERIMENT"
RUNS_ROOT="$REPO_ROOT/runs/$EXPERIMENT"
RESULTS_DIR="$EXPERIMENT_DIR/results"
VARIANTS=(baseline privileged)

if [[ ! -f "$REPO_ROOT/train.py" || ! -f "$EXPERIMENT_DIR/common.toml" ]]; then
    echo "error: repository root or experiment definition is incomplete: $REPO_ROOT" >&2
    exit 2
fi
if [[ ! -x "$PYTHON" ]]; then
    echo "error: expected executable Python at $PYTHON" >&2
    exit 2
fi

# common.toml を既定値の正本とし、必要な値だけ同名の環境変数で上書きする。
defaults="$("$PYTHON" -c '
import tomllib
from pathlib import Path
c = tomllib.loads(Path("experiments/privileged_critic/common.toml").read_text())
keys = (
    ("training", "num_envs"), ("training", "total_timesteps"),
    ("training", "lr"), ("training", "n_steps"),
    ("training", "batch_size"), ("training", "n_epochs"),
    ("training", "target_kl"), ("training", "ent_coef"),
    ("training", "clip_range"), ("training", "gamma"),
    ("reward_shaping", "shape_hp"), ("reward_shaping", "shape_mp"),
    ("reward_shaping", "shape_money"),
    ("network", "d_model"), ("network", "nhead"),
    ("network", "num_layers"), ("network", "dim_feedforward"),
    ("network", "features_dim"), ("opponent", "kind"),
    ("evaluation", "opponent"), ("evaluation", "games_per_seat"),
    ("evaluation", "num_envs"), ("evaluation", "seed_offset_from_training"),
    ("network", "use_transformer"), ("network", "amp"),
    ("network", "grad_checkpointing"), ("opponent", "self_play"),
    ("evaluation", "both_seats"), ("evaluation", "deterministic"),
    ("evaluation", "amp"),
)
print(*[c[section][key] for section, key in keys], sep="\t")
')"
IFS=$'\t' read -r DEFAULT_NUM_ENVS DEFAULT_TIMESTEPS DEFAULT_LR DEFAULT_N_STEPS \
    DEFAULT_BATCH_SIZE DEFAULT_N_EPOCHS DEFAULT_TARGET_KL DEFAULT_ENT_COEF \
    DEFAULT_CLIP_RANGE DEFAULT_GAMMA DEFAULT_SHAPE_HP DEFAULT_SHAPE_MP \
    DEFAULT_SHAPE_MONEY DEFAULT_D_MODEL DEFAULT_NHEAD DEFAULT_NUM_LAYERS \
    DEFAULT_DIM_FEEDFORWARD DEFAULT_FEATURES_DIM DEFAULT_OPPONENT \
    EVAL_OPPONENT EVAL_GAMES_PER_SEAT EVAL_NUM_ENVS EVAL_SEED_OFFSET \
    DEFAULT_USE_TRANSFORMER DEFAULT_AMP DEFAULT_GRAD_CHECKPOINTING DEFAULT_SELF_PLAY \
    EVAL_BOTH_SEATS EVAL_DETERMINISTIC EVAL_AMP <<< "$defaults"

GPU_IDS="${GPU_IDS:-}"
SEED="${SEED:-42}"
TIMESTEPS="${TIMESTEPS:-$DEFAULT_TIMESTEPS}"
NUM_ENVS="${NUM_ENVS:-$DEFAULT_NUM_ENVS}"
LR="${LR:-$DEFAULT_LR}"
N_STEPS="${N_STEPS:-$DEFAULT_N_STEPS}"
BATCH_SIZE="${BATCH_SIZE:-$DEFAULT_BATCH_SIZE}"
N_EPOCHS="${N_EPOCHS:-$DEFAULT_N_EPOCHS}"
TARGET_KL="${TARGET_KL:-$DEFAULT_TARGET_KL}"
ENT_COEF="${ENT_COEF:-$DEFAULT_ENT_COEF}"
CLIP_RANGE="${CLIP_RANGE:-$DEFAULT_CLIP_RANGE}"
GAMMA="${GAMMA:-$DEFAULT_GAMMA}"
SHAPE_HP="${SHAPE_HP:-$DEFAULT_SHAPE_HP}"
SHAPE_MP="${SHAPE_MP:-$DEFAULT_SHAPE_MP}"
SHAPE_MONEY="${SHAPE_MONEY:-$DEFAULT_SHAPE_MONEY}"
SHAPE_HAND="${SHAPE_HAND:-0.0}"
D_MODEL="${D_MODEL:-$DEFAULT_D_MODEL}"
NHEAD="${NHEAD:-$DEFAULT_NHEAD}"
NUM_LAYERS="${NUM_LAYERS:-$DEFAULT_NUM_LAYERS}"
DIM_FEEDFORWARD="${DIM_FEEDFORWARD:-$DEFAULT_DIM_FEEDFORWARD}"
FEATURES_DIM="${FEATURES_DIM:-$DEFAULT_FEATURES_DIM}"
OPPONENT="${OPPONENT:-$DEFAULT_OPPONENT}"
RUN_KIND="${RUN_KIND:-full}"
STARTUP_CHECK_SEC="${STARTUP_CHECK_SEC:-10}"

require_uint() {
    local name="$1" value="$2"
    if [[ ! "$value" =~ ^[0-9]+$ ]]; then
        echo "error: $name must be a non-negative integer (got: $value)" >&2
        exit 2
    fi
}

require_number() {
    local name="$1" value="$2"
    if [[ ! "$value" =~ ^-?[0-9]+([.][0-9]+)?([eE][-+]?[0-9]+)?$ ]]; then
        echo "error: $name must be numeric (got: $value)" >&2
        exit 2
    fi
}

for item in "SEED:$SEED" "TIMESTEPS:$TIMESTEPS" "NUM_ENVS:$NUM_ENVS" \
    "N_STEPS:$N_STEPS" "BATCH_SIZE:$BATCH_SIZE" "N_EPOCHS:$N_EPOCHS" \
    "D_MODEL:$D_MODEL" "NHEAD:$NHEAD" "NUM_LAYERS:$NUM_LAYERS" \
    "DIM_FEEDFORWARD:$DIM_FEEDFORWARD" "FEATURES_DIM:$FEATURES_DIM" \
    "STARTUP_CHECK_SEC:$STARTUP_CHECK_SEC"; do
    require_uint "${item%%:*}" "${item#*:}"
done
for item in "LR:$LR" "TARGET_KL:$TARGET_KL" "ENT_COEF:$ENT_COEF" \
    "CLIP_RANGE:$CLIP_RANGE" "GAMMA:$GAMMA" "SHAPE_HP:$SHAPE_HP" \
    "SHAPE_MP:$SHAPE_MP" "SHAPE_MONEY:$SHAPE_MONEY" "SHAPE_HAND:$SHAPE_HAND"; do
    require_number "${item%%:*}" "${item#*:}"
done
if (( TIMESTEPS == 0 || NUM_ENVS == 0 || N_STEPS == 0 || BATCH_SIZE == 0 || N_EPOCHS == 0 )); then
    echo "error: TIMESTEPS, NUM_ENVS, N_STEPS, BATCH_SIZE, and N_EPOCHS must be positive" >&2
    exit 2
fi
EVAL_SEED=$((SEED + EVAL_SEED_OFFSET))
if (( BATCH_SIZE > NUM_ENVS * N_STEPS )); then
    echo "error: BATCH_SIZE ($BATCH_SIZE) exceeds one rollout ($((NUM_ENVS * N_STEPS)))" >&2
    exit 2
fi
if [[ "$RUN_KIND" != "full" && "$RUN_KIND" != "smoke_test" ]]; then
    echo "error: RUN_KIND must be 'full' or 'smoke_test' (got: $RUN_KIND)" >&2
    exit 2
fi
if [[ "$DEFAULT_USE_TRANSFORMER" != True || "$DEFAULT_AMP" != True \
    || "$DEFAULT_GRAD_CHECKPOINTING" != False || "$DEFAULT_SELF_PLAY" != False \
    || "$EVAL_BOTH_SEATS" != True || "$EVAL_DETERMINISTIC" != True || "$EVAL_AMP" != True ]]; then
    echo "error: common.toml boolean modes changed; update the runner's explicit CLI and metadata first" >&2
    exit 2
fi
if [[ ! "$OPPONENT" =~ ^[a-zA-Z0-9_-]+$ ]]; then
    echo "error: OPPONENT contains unsupported characters: $OPPONENT" >&2
    exit 2
fi

if [[ -z "$GPU_IDS" ]]; then
    echo "error: set GPU_IDS to at least two comma-separated GPU IDs (for example GPU_IDS=0,1)" >&2
    exit 2
fi
IFS=',' read -r -a GPUS <<< "$GPU_IDS"
if (( ${#GPUS[@]} < ${#VARIANTS[@]} )); then
    echo "error: ${#VARIANTS[@]} variants require at least ${#VARIANTS[@]} GPUs; GPU_IDS has ${#GPUS[@]}" >&2
    exit 2
fi
declare -A SEEN_GPUS=()
for gpu in "${GPUS[@]}"; do
    if [[ ! "$gpu" =~ ^[0-9]+$ ]]; then
        echo "error: GPU IDs must be non-negative integers (got: $gpu)" >&2
        exit 2
    fi
    if [[ -n "${SEEN_GPUS[$gpu]:-}" ]]; then
        echo "error: duplicate GPU ID: $gpu" >&2
        exit 2
    fi
    SEEN_GPUS[$gpu]=1
done
if (( ${#GPUS[@]} > ${#VARIANTS[@]} )); then
    echo "note: only the first ${#VARIANTS[@]} GPUs are used: ${GPUS[0]},${GPUS[1]}"
fi

# CUDA は各プロセスと同じ可視化条件で検査する。各学習プロセスからは割当GPUが cuda:0 に見える。
declare -a PYTHON_VERSIONS TORCH_VERSIONS TORCH_CUDA_VERSIONS GPU_NAMES
for i in "${!VARIANTS[@]}"; do
    gpu="${GPUS[$i]}"
    if ! gpu_info="$(CUDA_VISIBLE_DEVICES="$gpu" "$PYTHON" -c '
import platform
import torch
if not torch.cuda.is_available():
    raise SystemExit("CUDA is unavailable for the requested GPU")
if torch.cuda.device_count() != 1:
    raise SystemExit(f"expected exactly one visible GPU, got {torch.cuda.device_count()}")
print(platform.python_version())
print(torch.__version__)
print(torch.version.cuda or "unknown")
print(torch.cuda.get_device_name(0))
')"; then
        echo "error: CUDA preflight failed for ${VARIANTS[$i]} on requested GPU $gpu" >&2
        exit 3
    fi
    mapfile -t gpu_lines <<< "$gpu_info"
    if (( ${#gpu_lines[@]} != 4 )); then
        echo "error: unexpected CUDA preflight output for GPU $gpu" >&2
        exit 3
    fi
    PYTHON_VERSIONS[$i]="${gpu_lines[0]}"
    TORCH_VERSIONS[$i]="${gpu_lines[1]}"
    TORCH_CUDA_VERSIONS[$i]="${gpu_lines[2]}"
    GPU_NAMES[$i]="${gpu_lines[3]}"
done

GIT_COMMIT="$(git rev-parse HEAD)"
GIT_BRANCH="$(git branch --show-current)"
GIT_BRANCH="${GIT_BRANCH:-DETACHED}"
if [[ -n "$(git status --porcelain --untracked-files=normal)" ]]; then
    GIT_DIRTY=true
else
    GIT_DIRTY=false
fi
if [[ -f "$REPO_ROOT/uv.lock" ]]; then
    UV_LOCK_SHA256="$(sha256sum "$REPO_ROOT/uv.lock" | awk '{print $1}')"
else
    UV_LOCK_SHA256=""
fi

STARTED_AT_COMPACT="$(date -u +%Y%m%dT%H%M%SZ)"
STARTED_AT_ISO="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
PAIR_ID="${EXPERIMENT}_s${SEED}_${STARTED_AT_COMPACT}"

mkdir -p -- "$RUNS_ROOT" "$RESULTS_DIR"
declare -a RUN_IDS RUN_DIRS PIDS
for i in "${!VARIANTS[@]}"; do
    variant="${VARIANTS[$i]}"
    run_id="${EXPERIMENT}_${variant}_s${SEED}_${STARTED_AT_COMPACT}"
    run_dir="$RUNS_ROOT/$run_id"
    if [[ -e "$run_dir" || -e "$RESULTS_DIR/$run_id.toml" ]]; then
        echo "error: refusing to overwrite existing run: $run_id" >&2
        exit 4
    fi
    RUN_IDS[$i]="$run_id"
    RUN_DIRS[$i]="$run_dir"
done
for i in "${!VARIANTS[@]}"; do
    variant="${VARIANTS[$i]}"
    run_dir="${RUN_DIRS[$i]}"
    mkdir -- "$run_dir"
    mkdir -- "$run_dir/checkpoints" "$run_dir/logs" "$run_dir/tensorboard" "$run_dir/definitions"
    cp -- "$EXPERIMENT_DIR/common.toml" "$run_dir/definitions/common.toml"
    cp -- "$EXPERIMENT_DIR/$variant/variant.toml" "$run_dir/definitions/variant.toml"
done

toml_escape() {
    local value="$1"
    value="${value//\\/\\\\}"
    value="${value//\"/\\\"}"
    value="${value//$'\n'/\\n}"
    printf '%s' "$value"
}

write_metadata() {
    local i="$1" status="$2" finished_at="$3" exit_code="$4" model_sha="$5" note="$6"
    local variant="${VARIANTS[$i]}" run_id="${RUN_IDS[$i]}" run_dir="${RUN_DIRS[$i]}"
    local privileged=false
    [[ "$variant" == "privileged" ]] && privileged=true
    local relative_dir="runs/$EXPERIMENT/$run_id"
    local tmp="$run_dir/run_meta.toml.tmp.$$"
    {
        printf 'schema_version = 1\n'
        printf 'run_id = "%s"\n' "$(toml_escape "$run_id")"
        printf 'pair_id = "%s"\n' "$(toml_escape "$PAIR_ID")"
        printf 'experiment = "%s"\n' "$EXPERIMENT"
        printf 'variant = "%s"\n' "$variant"
        printf 'run_kind = "%s"\n' "$RUN_KIND"
        printf 'status = "%s"\n' "$status"
        printf 'started_at_utc = "%s"\n' "$STARTED_AT_ISO"
        printf 'finished_at_utc = "%s"\n' "$(toml_escape "$finished_at")"
        printf 'exit_code = %s\n\n' "$exit_code"
        printf '[source]\n'
        printf 'git_commit = "%s"\n' "$GIT_COMMIT"
        printf 'git_branch = "%s"\n' "$(toml_escape "$GIT_BRANCH")"
        printf 'working_tree_dirty = %s\n' "$GIT_DIRTY"
        printf 'uv_lock_sha256 = "%s"\n' "$UV_LOCK_SHA256"
        printf 'common_definition = "experiments/%s/common.toml"\n' "$EXPERIMENT"
        printf 'variant_definition = "experiments/%s/%s/variant.toml"\n\n' "$EXPERIMENT" "$variant"
        printf '[resolved_training]\n'
        printf 'seed = %s\nnum_envs = %s\ntotal_timesteps = %s\n' "$SEED" "$NUM_ENVS" "$TIMESTEPS"
        printf 'lr = %s\nn_steps = %s\nbatch_size = %s\nn_epochs = %s\n' "$LR" "$N_STEPS" "$BATCH_SIZE" "$N_EPOCHS"
        printf 'target_kl = %s\nent_coef = %s\nclip_range = %s\ngamma = %s\n' "$TARGET_KL" "$ENT_COEF" "$CLIP_RANGE" "$GAMMA"
        printf 'shape_hp = %s\nshape_mp = %s\nshape_money = %s\nshape_hand = %s\n' "$SHAPE_HP" "$SHAPE_MP" "$SHAPE_MONEY" "$SHAPE_HAND"
        printf 'opponent = "%s"\nself_play = false\n' "$OPPONENT"
        printf 'use_transformer = true\nd_model = %s\nnhead = %s\nnum_layers = %s\n' "$D_MODEL" "$NHEAD" "$NUM_LAYERS"
        printf 'dim_feedforward = %s\nfeatures_dim = %s\namp = true\ngrad_checkpointing = false\n' "$DIM_FEEDFORWARD" "$FEATURES_DIM"
        printf 'privileged_critic = %s\n\n' "$privileged"
        printf '[inherited_ppo_defaults]\n'
        printf 'gae_lambda = 0.95\nclip_range_vf = "none"\nnormalize_advantage = true\n'
        printf 'vf_coef = 0.5\nmax_grad_norm = 0.5\npolicy_mlp_pi = [64, 64]\npolicy_mlp_vf = [64, 64]\n\n'
        printf 'activation = "Tanh"\northogonal_initialization = true\n\n'
        printf '[resolved_evaluation]\n'
        printf 'opponent = "%s"\ngames_per_seat = %s\nnum_envs = %s\nseed = %s\n' \
            "$EVAL_OPPONENT" "$EVAL_GAMES_PER_SEAT" "$EVAL_NUM_ENVS" "$EVAL_SEED"
        printf 'both_seats = true\ndeterministic = true\namp = true\n\n'
        printf '[environment]\n'
        printf 'python_executable = ".venv/bin/python"\n'
        printf 'python_version = "%s"\ntorch_version = "%s"\n' "${PYTHON_VERSIONS[$i]}" "${TORCH_VERSIONS[$i]}"
        printf 'torch_cuda_version = "%s"\nrequested_gpu_id = "%s"\n' "${TORCH_CUDA_VERSIONS[$i]}" "${GPUS[$i]}"
        printf 'visible_cuda_device = "cuda:0"\ngpu_name = "%s"\n\n' "$(toml_escape "${GPU_NAMES[$i]}")"
        printf '[artifacts]\n'
        printf 'directory = "%s"\n' "$relative_dir"
        printf 'model = "%s/checkpoints/final_model.zip"\n' "$relative_dir"
        printf 'model_sha256 = "%s"\n' "$model_sha"
        printf 'tensorboard = "%s/tensorboard"\n' "$relative_dir"
        printf 'stdout_log = "%s/logs/train.log"\n' "$relative_dir"
        printf 'command_log = "%s/logs/command.log"\n\n' "$relative_dir"
        printf 'eval_log = "%s/logs/eval.log"\n' "$relative_dir"
        printf 'wandb_run = ""\n\n'
        printf '[notes]\ntext = "%s"\n' "$(toml_escape "$note")"
    } > "$tmp"
    mv -- "$tmp" "$run_dir/run_meta.toml"

    local result_tmp="$RESULTS_DIR/$run_id.toml.tmp.$$"
    cp -- "$run_dir/run_meta.toml" "$result_tmp"
    mv -- "$result_tmp" "$RESULTS_DIR/$run_id.toml"
}

COMMON_ARGS=(
    --seed "$SEED"
    --num-envs "$NUM_ENVS"
    --total-timesteps "$TIMESTEPS"
    --lr "$LR"
    --n-steps "$N_STEPS"
    --batch-size "$BATCH_SIZE"
    --n-epochs "$N_EPOCHS"
    --target-kl "$TARGET_KL"
    --ent-coef "$ENT_COEF"
    --clip-range "$CLIP_RANGE"
    --gamma "$GAMMA"
    --shape-hp "$SHAPE_HP"
    --shape-mp "$SHAPE_MP"
    --shape-money "$SHAPE_MONEY"
    --shape-hand "$SHAPE_HAND"
    --opponent "$OPPONENT"
    --d-model "$D_MODEL"
    --nhead "$NHEAD"
    --num-layers "$NUM_LAYERS"
    --dim-feedforward "$DIM_FEEDFORWARD"
    --features-dim "$FEATURES_DIM"
)

run_variant() {
    local i="$1" variant="${VARIANTS[$1]}" run_id="${RUN_IDS[$1]}" run_dir="${RUN_DIRS[$1]}"
    local gpu="${GPUS[$1]}" child_pid="" final_status final_note model_sha="" rc
    local command=("$PYTHON" "$REPO_ROOT/train.py" "${COMMON_ARGS[@]}"
        --tensorboard-log "$run_dir/tensorboard"
        --save-path "$run_dir/checkpoints/final_model")
    if [[ "$variant" == "privileged" ]]; then
        command+=(--privileged-critic)
    fi

    handle_signal() {
        trap - INT TERM HUP
        if [[ -n "$child_pid" ]] && kill -0 "$child_pid" 2>/dev/null; then
            kill "$child_pid" 2>/dev/null || true
            wait "$child_pid" 2>/dev/null || true
        fi
        write_metadata "$i" interrupted "$(date -u +%Y-%m-%dT%H:%M:%SZ)" 143 "" \
            "terminated before the paired comparison completed"
        exit 143
    }
    trap handle_signal INT TERM HUP

    {
        printf 'CUDA_VISIBLE_DEVICES=%q ' "$gpu"
        printf '%q ' "${command[@]}"
        printf '\n'
    } > "$run_dir/logs/command.log"
    write_metadata "$i" running "" -1 "" ""

    CUDA_VISIBLE_DEVICES="$gpu" "${command[@]}" > "$run_dir/logs/train.log" 2>&1 &
    child_pid=$!
    set +e
    wait "$child_pid"
    rc=$?
    set -e
    child_pid=""

    if (( rc == 0 )); then
        if [[ ! -f "$run_dir/checkpoints/final_model.zip" ]]; then
            rc=66
            final_note="training exited successfully but final_model.zip is missing"
        elif ! find "$run_dir/tensorboard" -type f -name 'events.out.tfevents.*' -print -quit | grep -q .; then
            rc=67
            final_note="training exited successfully but no TensorBoard event file was found"
        else
            model_sha="$(sha256sum "$run_dir/checkpoints/final_model.zip" | awk '{print $1}')"
            if [[ "$RUN_KIND" == "smoke_test" ]]; then
                final_status=smoke_test
            else
                final_status=completed
            fi
            final_note="artifacts validated"
        fi
    fi
    if (( rc != 0 )); then
        final_status=failed
        final_note="${final_note:-training command exited non-zero; see logs/train.log}"
    fi
    write_metadata "$i" "$final_status" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$rc" "$model_sha" "$final_note"
    return "$rc"
}

declare -a ACTIVE
stop_active_runs() {
    local i
    trap - INT TERM HUP
    for i in "${!PIDS[@]}"; do
        if [[ "${ACTIVE[$i]:-0}" == 1 ]] && kill -0 "${PIDS[$i]}" 2>/dev/null; then
            kill "${PIDS[$i]}" 2>/dev/null || true
        fi
    done
    for i in "${!PIDS[@]}"; do
        if [[ "${ACTIVE[$i]:-0}" == 1 ]]; then
            wait "${PIDS[$i]}" 2>/dev/null || true
            ACTIVE[$i]=0
        fi
    done
}

on_parent_signal() {
    echo "received a signal; stopping both variants" >&2
    stop_active_runs
    exit 130
}
on_parent_exit() {
    local rc=$?
    if (( rc != 0 )); then
        stop_active_runs
    fi
}
trap on_parent_signal INT TERM HUP
trap on_parent_exit EXIT

echo "Starting paired privileged critic experiment"
echo "  pair       : $PAIR_ID"
echo "  source     : $GIT_BRANCH @ $GIT_COMMIT (dirty=$GIT_DIRTY)"
echo "  conditions : seed=$SEED timesteps=$TIMESTEPS envs=$NUM_ENVS run_kind=$RUN_KIND"
for i in "${!VARIANTS[@]}"; do
    echo "  ${VARIANTS[$i]}: GPU ${GPUS[$i]} (${GPU_NAMES[$i]}) -> ${RUN_DIRS[$i]}"
    run_variant "$i" &
    PIDS[$i]=$!
    ACTIVE[$i]=1
done

echo "Checking process startup for ${STARTUP_CHECK_SEC}s..."
sleep "$STARTUP_CHECK_SEC"
startup_failed=0
for i in "${!PIDS[@]}"; do
    if kill -0 "${PIDS[$i]}" 2>/dev/null; then
        echo "  ${VARIANTS[$i]} is alive (pid=${PIDS[$i]})"
    else
        set +e
        wait "${PIDS[$i]}"
        rc=$?
        set -e
        ACTIVE[$i]=0
        if (( rc == 0 )); then
            echo "  ${VARIANTS[$i]} already completed successfully"
        else
            echo "  ${VARIANTS[$i]} failed during startup (exit=$rc)" >&2
            tail -n 20 "${RUN_DIRS[$i]}/logs/train.log" >&2 || true
            startup_failed=1
        fi
    fi
done
if (( startup_failed != 0 )); then
    echo "A variant failed during startup; stopping its paired run." >&2
    stop_active_runs
    exit 1
fi

pair_status=0
while :; do
    waiting_pids=()
    for i in "${!PIDS[@]}"; do
        if [[ "${ACTIVE[$i]}" == 1 ]]; then
            waiting_pids+=("${PIDS[$i]}")
        fi
    done
    if (( ${#waiting_pids[@]} == 0 )); then
        break
    fi
    completed_pid=""
    set +e
    wait -n -p completed_pid "${waiting_pids[@]}"
    rc=$?
    set -e
    completed_index=""
    for i in "${!PIDS[@]}"; do
        if [[ "${PIDS[$i]}" == "$completed_pid" ]]; then
            completed_index="$i"
            break
        fi
    done
    if [[ -z "$completed_index" ]]; then
        echo "error: could not identify completed child process: $completed_pid" >&2
        pair_status=1
        stop_active_runs
        break
    fi
    i="$completed_index"
    ACTIVE[$i]=0
    if (( rc == 0 )); then
        echo "${VARIANTS[$i]}: completed and artifacts validated"
    else
        echo "${VARIANTS[$i]}: failed (exit=$rc); stopping the paired run" >&2
        tail -n 20 "${RUN_DIRS[$i]}/logs/train.log" >&2 || true
        pair_status=1
        stop_active_runs
        break
    fi
done

if (( pair_status == 0 )); then
    echo "Paired run complete. Compare with: .venv/bin/tensorboard --logdir runs/$EXPERIMENT"
fi
exit "$pair_status"
