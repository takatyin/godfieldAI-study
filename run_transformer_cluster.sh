#!/bin/bash

# run_transformer_cluster.sh
# 4枚のGPUをフル活用した非同期リーグ・トレーニング（Transformer版）起動スクリプト

echo "Starting Asynchronous League Training (Transformer) across 4 GPUs..."

# ログディレクトリの作成
mkdir -p logs

# 古いログをクリーンアップ
rm -f logs/transformer_worker_*.log

# ワーカーごとに変えるもの。
#
# seed を変えないとリーグにならない。以前は --seed を渡しておらず全ワーカーが
# 既定の 42 を使っていたため、ネットワークの初期重みも環境のシードも同一で、
# 実測で行動が 100% 一致していた（seed を変えると一致率は 11.6% になる）。
# 分岐していたのはプール抽選の乱数だけで、それも意図したものではなかった。
#
# エントロピー係数も変える。低いと方策が早く尖り、いちど確率が0になった行動は
# 二度とサンプルされないので勾配が流れない（対象選択が「常に相手」で固まったのが
# それ）。強さと多様性のどちらが効くかを1回の実行で見比べられる。
SEEDS=(42 43 44 45)
ENT_COEFS=(0.003 0.01 0.01 0.03)

# 4つのプロセスを独立して起動
for i in {0..3}; do
    echo "Launching Transformer Worker $i on GPU $i (seed=${SEEDS[$i]}, ent_coef=${ENT_COEFS[$i]})..."
    CUDA_VISIBLE_DEVICES=$i uv run python train.py \
        --use-transformer \
        --self-play \
        --start-opponent-model assets/models/best_mlp_gen50.zip \
        --pool-dir models/league_pool_transformer \
        --worker-id $i \
        --seed "${SEEDS[$i]}" \
        --ent-coef "${ENT_COEFS[$i]}" \
        --shape-hp 0.2 \
        --total-timesteps 50000000 \
        --self-play-save-freq 1000000 \
        --num-envs 500 \
        --batch-size 8192 \
        --tensorboard-log "logs/transformer_tb" \
        > "logs/transformer_worker_$i.log" 2>&1 &
done

echo "All 4 Transformer Workers launched in background!"
echo "They are independently training and sharing models in 'models/league_pool_transformer'."
echo "You can check logs with: tail -f logs/transformer_worker_0.log"
