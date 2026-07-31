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
# 【VRAM と更新回数】batch_size がVRAMを決める（num_envs ではない）。ところが
# 1ロールアウトあたりの勾配更新回数は rollout ÷ batch_size × n_epochs で決まるため、
# 大きいモデルほどVRAMの都合で batch を下げると更新回数が跳ね上がる。前回の実行では
# それが原因で approx_kl が worker 0 の 0.025 に対し worker 1〜3 は 0.35〜0.44 に達し、
# 大きいモデルほど弱くなった（対 strategic で d128:68.6% / d192:50〜54% / d256:31.4%）。
#
# 勾配チェックポイント（--grad-checkpointing）で層ごとの活性を捨てて再計算すると、
# 逆伝播が約1.24倍になる代わりにVRAMが減り、batch を上げられる。
#
# ただし batch だけでは更新回数を揃えきれない。RTX3090(23.6GB) での実測
# （bf16 + ckpt、Adam の状態と方策ヘッドを含む、プロセスを分けて測定）:
#
#   構成                batch   予約VRAM   占有率
#   d128 h4 L2 ff256     8192    13.20G     56%
#   d192 h8 L4 ff768     8192      OOM       -
#   d192 h8 L4 ff768     5120    18.16G     77%
#   d192 h8 L4 ff768     4096    14.54G     62%
#   d256 h8 L6 ff1024    4096    20.31G     86%   ← 相手モデルぶんの余裕がない
#   d256 h8 L6 ff1024    3200    15.92G     68%
#
# OOM の判定は「確保」ではなく「予約」で見ること。PyTorch のアロケータは
# 確保量の 1.4〜1.5倍を予約する。さらに自己対戦では相手モデルの推論も
# 同じGPUに載るので、8割を超える設定は避ける。
#
# 届かないぶんは n_epochs で調整し、全ワーカーの更新回数を160回に揃える。
#   更新回数 = ceil(rollout / batch) * n_epochs
#
set -euo pipefail

# 以降のパス（models/ logs/ train.py）はリポジトリルート基準なので、
# どこから起動しても同じになるよう移動しておく。
cd "$(dirname "$0")/.."

# 観測のレイアウトか特徴抽出器を変えたら、必ず新しいプールに切り替えること。
# 古いプールを指すと SelfPlayCallback が読み込みに失敗して落ちる（黙って人手の
# 方策とだけ戦い続けるより、止まったほうが良いのでそうしてある）。
#   v2 … 観測に手札枚数・公開状態を追加する前。もう読めない。
#   v3 … カード属性と閾値符号を入れる前。層が増えたので、もう読めない。
POOL_DIR="${POOL_DIR:-models/league_v4}"
# 学習し終えた最終モデルの置き場。--save-path を渡さないと全ワーカーが既定の
# godfield_agent.zip に書くため、先に終わったワーカーの結果が後から終わった
# ワーカーに黙って上書きされる。プールとは別のディレクトリにする
# （プールは *.zip をグロブして対戦相手に読み込むので、混ぜると最終モデルまで
# 対戦相手として拾われる）。
#
# 既定は POOL_DIR から導く。固定値にすると POOL_DIR だけ切り替えたときに
# 最終モデルが前回の場所へ書かれ、観測レイアウトの違うモデルが同じ名前で
# 上書きされてしまう（どちらのものか判別できなくなる）。
FINAL_DIR="${FINAL_DIR:-${POOL_DIR}_final}"
TIMESTEPS="${TIMESTEPS:-50000000}"
NUM_ENVS="${NUM_ENVS:-500}"

# 手書き方策と当たる割合。
#
# 以前は「手書き方策1体 + 過去の自分5体」を一様に選んでいたため約17%だった。
# 過去の自分は自分と同じ弱点を持つので、その弱点が一度も罰されない。実測では
# 37M ステップ学習したモデルが、学習相手には 71%/93% と強いのに、一度も戦って
# いない相手には 45% しか勝てなかった。
ANCHOR_RATIO="${ANCHOR_RATIO:-0.5}"

# worker: seed  ent_coef  d_model nhead layers ff    batch  epochs ckpt
#
# rollout = NUM_ENVS(500) x n_steps(256) = 128,000 サンプル。
#   d128 @ 8192 x 10周 =  16 x 10 = 160更新
#   d192 @ 4096 x  5周 =  32 x  5 = 160更新
#   d256 @ 3200 x  4周 =  40 x  4 = 160更新
WORKERS=(
  "42  0.003  128  4  2   256  8192  10  0"
  "43  0.010  192  8  4   768  4096   5  1"
  "44  0.010  192  8  4   768  4096   5  1"
  "45  0.030  256  8  6  1024  3200   4  1"
)

# FINAL_DIR は SB3 の save が自動で作るが、保存は数十時間後なので先に作っておく
# （起動直後に置き場所を確認できるようにする）
mkdir -p logs "$POOL_DIR" "$FINAL_DIR"
rm -f logs/league_worker_*.log

# 実際に使うパスは、環境変数を変えたときに取り違えやすいので必ず出す
echo "リーグ学習を開始します"
echo "  観測          : $(uv run python -c 'import godfield_core as g; print(g.OBSERVATION_FEATURE_SIZE)') 次元"
echo "  共有プール    : $POOL_DIR"
echo "  手書き方策と当たる割合: $ANCHOR_RATIO"
echo "  最終モデル    : $FINAL_DIR/worker_<i>.zip"
echo "  評価の最良    : $POOL_DIR/best_worker_<i>/best_model.zip"
echo "  総ステップ    : $TIMESTEPS / 並列環境 $NUM_ENVS"
echo
for i in "${!WORKERS[@]}"; do
    read -r seed ent d_model nhead layers ff batch epochs ckpt <<< "${WORKERS[$i]}"
    ckpt_flag=()
    [ "$ckpt" = "1" ] && ckpt_flag=(--grad-checkpointing)
    echo "  worker $i (GPU $i): seed=$seed ent=$ent d${d_model} h${nhead} L${layers}" \
         "ff${ff} batch=${batch} x${epochs}周" \
         "更新$(( (NUM_ENVS * 256 + batch - 1) / batch * epochs ))回/rollout" \
         "$([ "$ckpt" = "1" ] && echo "ckpt")"
    CUDA_VISIBLE_DEVICES=$i uv run python train.py \
        "${ckpt_flag[@]}" \
        --n-epochs "$epochs" \
        --self-play \
        --opponent strategic \
        --anchor-ratio "$ANCHOR_RATIO" \
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
    PIDS[$i]=$!
done

# 起動直後の失敗（VRAM不足、設定の誤り、プールが読めない）は、数十時間たって
# から気づいても手遅れになる。ここで一度だけ生存を確認する。
echo "起動を確認しています..."
sleep "${STARTUP_CHECK_SEC:-150}"
dead=()
for i in "${!PIDS[@]}"; do
    kill -0 "${PIDS[$i]}" 2>/dev/null || dead+=("$i")
done
if [ ${#dead[@]} -gt 0 ]; then
    echo
    echo "起動に失敗したワーカーがあります: ${dead[*]}"
    for i in "${dead[@]}"; do
        echo "--- worker $i の最後の20行 ---"
        tail -20 "logs/league_worker_$i.log"
    done
    echo
    echo "残りのワーカーも停止します。"
    for pid in "${PIDS[@]}"; do kill "$pid" 2>/dev/null || true; done
    exit 1
fi
echo "4ワーカーとも起動しました。"

echo
echo "  ログ:       tail -f logs/league_worker_0.log"
echo "  進捗:       tensorboard --logdir logs/league_tb"
echo "  更新量:     grep approx_kl logs/league_worker_3.log | tail -1   （0.03前後なら健全）"
echo "  方策の診断: uv run python tools/diagnose_policy.py $POOL_DIR/best_worker_0/best_model.zip"
echo

# 引数なしの wait は、ワーカーが異常終了しても 0 を返す。それでは途中で死んだ
# ワーカーに気づけないので、PID ごとに待って結果を出す。
status=0
for i in "${!PIDS[@]}"; do
    if wait "${PIDS[$i]}"; then
        echo "worker $i: 完了"
    else
        echo "worker $i: 異常終了（exit $?）— logs/league_worker_$i.log を確認してください"
        status=1
    fi
done
exit $status
