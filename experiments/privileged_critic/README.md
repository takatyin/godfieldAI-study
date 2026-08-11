# Baseline PPO vs Privileged Critic PPO

## 目的と仮説

GodField は部分観測環境なので、通常 Critic の `V(o_t)` は同じ観測に見える hidden state の違いを
区別できず、価値推定が難しいと考えられます。Critic だけに相手の真の手札を渡して
`V(o_t, h_t)` とすれば、Actor の入力と推論条件を変えずに価値推定を改善できる、という仮説を
検証します。勝率に加え、特に explained variance と value loss を主要評価対象にします。

## 実験定義

- [`common.toml`](./common.toml): 両条件で固定する学習・ネットワーク・相手・評価条件
- [`baseline/variant.toml`](./baseline/variant.toml): 通常 Critic の差分
- [`privileged/variant.toml`](./privileged/variant.toml): Privileged Critic の差分
- [`results/`](./results/README.md): Git 管理する小さな run meta と集約結果

TOML は既存の `TrainingConfig`/CLI に対応するレビュー用の実験定義であり、直接読み込む設定ファイル
ではありません。新しいローダーは導入せず、実行時には下記の明示的な CLI を使います。

## 条件差

| 項目 | baseline | privileged |
| --- | --- | --- |
| algorithm | `MaskablePPO` | `PrivilegedMaskablePPO` |
| Actor 入力 | 通常観測 `o_t` | 通常観測 `o_t` のみ |
| Critic 入力 | 通常観測 `o_t` | `o_t` + 相手 true hand `h_t` |
| feature extractor | Actor/Critic で共有（通常 policy の既定） | Actor/Critic で必ず非共有 |
| 固有 CLI | なし | `--privileged-critic` |

seed、環境数、学習ステップ、PPO hyperparameters、報酬シェーピング、相手、Transformer の
クラスと寸法、AMP、評価条件は `common.toml` の値を両方に適用します。同じ seed の2 run を
pair とし、片方だけ失敗した pair は集計に使いません。

### 実行前の確認事項

現在の作業ツリーでは `godfield_rl/training.py::build_model()` が `cfg.privileged_critic` を参照し、
通常時は `MaskablePPO` と `policy_class()`、有効時は `PrivilegedMaskablePPO` と
`privileged_policy_class()` を選択します。今回の実験管理整備ではこの学習ロジックを変更していません。
誤って両方を baseline として走らせないよう、公式実行に使う commit でも次の配線が残っていることを
事前確認します。

```bash
rg -n 'cfg\.privileged_critic|PrivilegedMaskablePPO|privileged_policy_class' godfield_rl/training.py
```

privileged policy の Actor/Critic feature extractor 非共有は意図した必須条件です。共有すると、
privileged 情報を使った value loss の勾配が Actor も利用する extractor を更新し、Actor を通常観測だけの
経路に隔離できません。この実験では extractor 分離を Privileged Critic 方式の一部として扱い、通常の
MaskablePPO と完全な Privileged Critic 実装を比較します。将来「true hand 自体の効果」だけを追加で
分解したくなった場合は、通常 Critic かつ extractor 非共有の第3条件を別の ablation として定義します。

## 固定条件

`common.toml` が正本です。初期の full run は seed 42、将来の複数 seed 比較は
`42, 43, 44, 45, 46` を同じ順で両 variant に適用します。主な固定値は次のとおりです。

- `num_envs=1000`, `total_timesteps=5,000,000`
- `lr=5.845e-5`, `n_steps=256`, `batch_size=2048`, `n_epochs=10`
- `target_kl=0.03`, `ent_coef=0.01`, `clip_range=0.3`, `gamma=0.995`
- CLI 非公開の PPO 値も同じ lockfile から継承: `gae_lambda=0.95`, `vf_coef=0.5`,
  advantage normalization 有効、max grad norm `0.5`、policy/value MLP とも `[64, 64]`
- reward shaping: HP `0.2`, MP `0.0`, money `0.0`
- opponent: `strategic`、self-play 無効
- Transformer: d192 / 8 heads / 4 layers / FF 768 / features 256
- AMP 有効、gradient checkpointing 無効

## 評価指標

TensorBoard（W&B を有効にした場合はその同期先）で次を比較します。

- 勝率: `win_rate/recent_win`, `win_rate/overall` と固定条件での最終評価勝率
- 価値推定: `train/explained_variance`, `train/value_loss`
- 方策更新: `train/policy_gradient_loss`, `train/entropy_loss`, `train/approx_kl`,
  `train/clip_fraction`
- 効率（任意）: `time/fps`, wall-clock time, peak VRAM

最終勝率は `tools/evaluate.py` を使い、`strategic` 相手に席を入れ替えて各席3000局、同じ評価 seed、
deterministic policy、AMP 有効で測ります。学習中の win rate は報酬シェーピング込みの学習環境で
集計されますが、勝敗判定自体は `game_outcome` を使います。最終評価には報酬シェーピングは入りません。

## 実行方法

以下は既存 CLI を明示的に呼ぶ手順です。公式比較では先に working tree を clean にし、同じ commit、
同じマシン/GPU、同じ seed で baseline と privileged を1組ずつ実行します。`variant` だけを変更し、
出力ディレクトリは共有しません。

```bash
seed=42
variant=baseline
started_at=$(date -u +%Y%m%dT%H%M%SZ)
run_id="pc_${variant}_s${seed}_${started_at}"
run_dir="runs/privileged_critic/${run_id}"
mkdir -p "$run_dir/checkpoints" "$run_dir/logs" "$run_dir/wandb"

common_args=(
  --seed "$seed"
  --num-envs 1000
  --total-timesteps 5000000
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
  --tensorboard-log "$run_dir/tensorboard"
  --save-path "$run_dir/checkpoints/final_model"
)

WANDB_DIR="$run_dir/wandb" uv run python train.py "${common_args[@]}" \
  2>&1 | tee "$run_dir/logs/train.log"
```

`use_transformer=true` と `amp=true` は既定値なので、それらを無効化するフラグを渡しません。
W&B も両 variant で使う場合は両方のコマンドに次を同じように追加します。

```bash
--wandb --wandb-project godfield-rl-privileged-critic --wandb-name "$run_id"
```

privileged は前述の配線確認後、同じ `common_args` に唯一の CLI 条件差を足して実行します。

```bash
variant=privileged
# run_id/run_dir/common_args は新しい variant 用に上と同じ手順で作り直す。
WANDB_DIR="$run_dir/wandb" uv run python train.py "${common_args[@]}" --privileged-critic \
  2>&1 | tee "$run_dir/logs/train.log"
```

複数 seed は一括投入する前に seed 42 の pair を完走・評価し、その後同じ手順を各 seed に対して
繰り返します。同じ run directory の再利用や上書きはしません。

## 評価方法

学習 seed に 10000 を足した値を評価 seed にします。baseline/privileged の同じ seed pair では
同じ評価 seed を使います。

```bash
eval_seed=$((seed + 10000))
uv run python tools/evaluate.py "$run_dir/checkpoints/final_model.zip" \
  --vs strategic --games 3000 --num-envs 512 --seed "$eval_seed" --amp \
  2>&1 | tee "$run_dir/logs/eval.log"
```

TensorBoard は experiment root を指定すれば両 run を同じ画面で比較できます。

```bash
tensorboard --logdir runs/privileged_critic
```

## 出力先と Git 管理

実行生成物は次のように分離します。

```text
runs/privileged_critic/<run_id>/
├── checkpoints/final_model.zip
├── tensorboard/<SB3 run>/events.out.tfevents.*
├── logs/train.log
├── logs/eval.log
└── wandb/
```

`runs/`, 既存の `logs/` と `models/`, W&B ローカルディレクトリは `.gitignore` 対象です。
実験定義、README、`results/summary.csv`、run ごとの小さな TOML meta は Git 管理対象です。
既存の `WandbCallback` は `--wandb` 有効時に追加のモデルを `models/<wandb_run_id>/` に保存します。
これも既存の ignore 対象であり、W&B を使ったかどうかと run URL/ID は meta に記録します。

## 再現手順と run meta

1. `run_meta.template.toml` を `results/<run_id>.toml` にコピーする。
2. 実行直前に UTC 日時、`git rev-parse HEAD`, `git branch --show-current`,
   `git status --porcelain` が空か、seed、variant、評価 seed、artifact path を記録する。
3. `common.toml` と対応する `variant.toml` を見ながら解決済み値を確認する。
4. 学習ログ冒頭の設定表示と CLI が一致することを確認してから完走させる。
5. 固定評価を実行し、`summary.csv` と run meta に結果・集約方法・任意の速度/VRAMを追記する。

commit SHA だけでは dirty な差分を再現できないため、公式比較は clean worktree を必須とします。
予備実験を dirty な状態で行った場合は `working_tree_dirty=true` として公式集計から除外します。
