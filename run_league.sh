#!/bin/bash
#
# 4枚のGPUで非同期リーグ学習を起動する。
#
# 以前は run_league_cluster.sh と run_transformer_cluster.sh に同じループが
# 二重にあり、MLP版とTransformer版で設定が食い違っていた。ワーカーごとの違いは
# 下の表だけにまとめてある。
#
# 【ワーカーごとに変えるもの】
#
#   seed  … 変えないとリーグにならない。以前は --seed を渡しておらず全ワーカーが
#           既定の42を使っていたため、実測で行動が100%一致していた
#           （seedを変えると一致率は11.6%）。
#   ent   … エントロピー係数。低いと方策が早期に尖り、いちど確率が0になった行動は
#           二度とサンプルされない。強さと多様性のどちらが効くかを1回で見比べる。
#   model … 容量の違う個体を混ぜる。プールは学習済みモデルを個別に読むので、
#           大きさが違っても同じリーグに同居できる。
#
# 【VRAM】batch_size がVRAMを決める（num_envs ではない）。24GBでの実測上限は
#   tools/measure_vram.py 参照。bf16(--amp, 既定)で d128:9472 / d192:2816 / d256:1536。
#
set -euo pipefail

POOL_DIR="${POOL_DIR:-models/league_v2}"
# 学習し終えた最終モデルの置き場。--save-path を渡さないと全ワーカーが既定の
# godfield_agent.zip に書くため、先に終わったワーカーの結果が後から終わった
# ワーカーに黙って上書きされる。プールとは別のディレクトリにする
# （プールは *.zip をグロブして対戦相手に読み込むので、混ぜると最終モデルまで
# 対戦相手として拾われる）。
FINAL_DIR="${FINAL_DIR:-models/league_v2_final}"
TIMESTEPS="${TIMESTEPS:-50000000}"
NUM_ENVS="${NUM_ENVS:-500}"

# worker: seed  ent_coef  d_model nhead layers ff    batch
WORKERS=(
  "42  0.003  128  4  2   256  8192"
  "43  0.010  192  8  4   768  2048"
  "44  0.010  192  8  4   768  2048"
  "45  0.030  256  8  6  1024  1024"
)

# FINAL_DIR は SB3 の save が自動で作るが、保存は数十時間後なので先に作っておく
# （起動直後に置き場所を確認できるようにする）
mkdir -p logs "$POOL_DIR" "$FINAL_DIR"
rm -f logs/league_worker_*.log

echo "リーグ学習を開始します（プール: $POOL_DIR）"
for i in "${!WORKERS[@]}"; do
    read -r seed ent d_model nhead layers ff batch <<< "${WORKERS[$i]}"
    echo "  worker $i (GPU $i): seed=$seed ent=$ent d${d_model} h${nhead} L${layers} ff${ff} batch=${batch}"
    CUDA_VISIBLE_DEVICES=$i uv run python train.py \
        --self-play \
        --opponent strategic \
        --pool-dir "$POOL_DIR" \
        --save-path "$FINAL_DIR/worker_$i" \
        --worker-id "$i" \
        --seed "$seed" \
        --ent-coef "$ent" \
        --d-model "$d_model" \
        --nhead "$nhead" \
        --num-layers "$layers" \
        --dim-feedforward "$ff" \
        --batch-size "$batch" \
        --num-envs "$NUM_ENVS" \
        --total-timesteps "$TIMESTEPS" \
        --tensorboard-log "logs/league_tb" \
        > "logs/league_worker_$i.log" 2>&1 &
done

echo
echo "4ワーカーを起動しました。共有プール: $POOL_DIR"
echo "  ログ:       tail -f logs/league_worker_0.log"
echo "  進捗:       tensorboard --logdir logs/league_tb"
echo "  方策の診断: uv run python tools/diagnose_policy.py $POOL_DIR/best_worker_0/best_model.zip"
echo
echo "保存先:"
echo "  評価で最良だったモデル: $POOL_DIR/best_worker_<i>/best_model.zip"
echo "  学習し終えた最終モデル: $FINAL_DIR/worker_<i>.zip"
wait
