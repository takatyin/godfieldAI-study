#!/bin/bash
# 4つのGPUそれぞれに独立したOptunaワーカーを割り当てて並列探索を行うスクリプト

# 特定のマシンのパスを直書きしていたので、リポジトリからの相対に直す
cd "$(dirname "$0")/.."

# 以前のDBがあればバックアップするかそのまま使うか（今回はそのまま追記）
echo "Starting Optuna distributed tuning across 4 GPUs..."
echo "Database: sqlite:///optuna_study.db"
echo "Study Name: godfield-ppo"

# 各GPU（0〜3）に対してバックグラウンドプロセスを立ち上げる
for i in {0..3}
do
    echo "Launching worker on GPU $i..."
    CUDA_VISIBLE_DEVICES=$i uv run python -m godfield_rl.tune \
        --storage sqlite:///optuna_study.db \
        --study-name godfield-ppo \
        --trials 10 \
        --total-timesteps 1500000 > "optuna_worker_$i.log" 2>&1 &
done

echo "All 4 workers launched in background!"
echo "You can check logs with: tail -f optuna_worker_0.log"
