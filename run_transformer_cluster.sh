#!/bin/bash

# run_transformer_cluster.sh
# 4枚のGPUをフル活用した非同期リーグ・トレーニング（Transformer版）起動スクリプト

echo "Starting Asynchronous League Training (Transformer) across 4 GPUs..."

# ログディレクトリの作成
mkdir -p logs

# 古いログをクリーンアップ
rm -f logs/transformer_worker_*.log

# 4つのプロセスを独立して起動
for i in {0..3}; do
    echo "Launching Transformer Worker $i on GPU $i..."
    CUDA_VISIBLE_DEVICES=$i uv run python train.py \
        --use-transformer \
        --self-play \
        --start-opponent-model assets/models/best_mlp_gen50.zip \
        --pool-dir models/league_pool_transformer \
        --worker-id $i \
        --total-timesteps 50000000 \
        --self-play-save-freq 1000000 \
        --num-envs 250 \
        --batch-size 4096 \
        --tensorboard-log "logs/transformer_tb" \
        > "logs/transformer_worker_$i.log" 2>&1 &
done

echo "All 4 Transformer Workers launched in background!"
echo "They are independently training and sharing models in 'models/league_pool_transformer'."
echo "You can check logs with: tail -f logs/transformer_worker_0.log"
