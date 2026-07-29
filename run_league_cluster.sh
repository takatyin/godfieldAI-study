#!/bin/bash

# run_league_cluster.sh
# 4枚のGPUをフル活用した非同期リーグ・トレーニング（Self-Play）起動スクリプト

echo "Starting Asynchronous League Training across 4 GPUs..."

# ログディレクトリの作成
mkdir -p logs

# 古いログをクリーンアップ
rm -f logs/league_worker_*.log

# 4つのプロセスを独立して起動
for i in {0..3}; do
    echo "Launching League Worker $i on GPU $i..."
    CUDA_VISIBLE_DEVICES=$i uv run python train.py \
        --self-play \
        --worker-id $i \
        --total-timesteps 50000000 \
        --self-play-save-freq 1000000 \
        --tensorboard-log "logs/league_tb" \
        > "logs/league_worker_$i.log" 2>&1 &
done

echo "All 4 League Workers launched in background!"
echo "They are independently training and sharing models in 'models/league_pool'."
echo "You can check logs with: tail -f logs/league_worker_0.log"
