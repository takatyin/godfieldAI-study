#!/bin/bash

# run_league_cluster.sh
# 4枚のGPUをフル活用した非同期リーグ・トレーニング（Self-Play）起動スクリプト

echo "Starting Asynchronous League Training across 4 GPUs..."

# ログディレクトリの作成
mkdir -p logs

# 古いログをクリーンアップ
rm -f logs/league_worker_*.log

# ワーカーごとに seed と探索の強さを変える。理由は run_transformer_cluster.sh の
# コメントを参照（seed が同じだと4ワーカーが完全に同じ経験を踏み、リーグにならない）。
SEEDS=(42 43 44 45)
ENT_COEFS=(0.003 0.01 0.01 0.03)

# 4つのプロセスを独立して起動
for i in {0..3}; do
    echo "Launching League Worker $i on GPU $i (seed=${SEEDS[$i]}, ent_coef=${ENT_COEFS[$i]})..."
    CUDA_VISIBLE_DEVICES=$i uv run python train.py \
        --self-play \
        --worker-id $i \
        --seed "${SEEDS[$i]}" \
        --ent-coef "${ENT_COEFS[$i]}" \
        --shape-hp 0.2 \
        --total-timesteps 50000000 \
        --self-play-save-freq 1000000 \
        --tensorboard-log "logs/league_tb" \
        > "logs/league_worker_$i.log" 2>&1 &
done

echo "All 4 League Workers launched in background!"
echo "They are independently training and sharing models in 'models/league_pool'."
echo "You can check logs with: tail -f logs/league_worker_0.log"
