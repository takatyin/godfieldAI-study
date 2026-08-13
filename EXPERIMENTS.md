# 実験ディレクトリ設計

GodFieldAI の強化学習実験は、Git で管理する「実験定義・小さい結果」と、
Git 管理外の「学習中に生成される大きな artifact」を分離します。
共通の運用手順とチェックリストは
[`experiments/experiment_plan.md`](./experiments/experiment_plan.md) を参照してください。

## ディレクトリ境界

```text
experiments/<experiment>/                   # Git管理
├── README.md                               # 目的、仮説、条件差、評価方法
├── common.toml                             # variant間で固定する条件
├── <variant>/
│   └── variant.toml                        # 意図した条件差だけ
└── results/
    ├── summary.csv                         # 比較に使う最終値
    ├── run_meta.template.toml              # run metadataのスキーマ例
    └── <run_id>.toml                       # 小さい実行記録

runs/<experiment>/<run_id>/                 # Git管理外
├── checkpoints/
│   └── final_model.zip
├── tensorboard/
├── logs/
│   ├── command.log
│   ├── train.log
│   └── eval.log
├── definitions/                            # 実行時点の実験定義コピー
│   ├── common.toml
│   └── variant.toml
└── run_meta.toml                           # artifactと同居するmetadataコピー
```

`experiments/` にはレビュー・再現・集計に必要な小さいファイルだけを置きます。
モデル、checkpoint、TensorBoard event、標準出力などは `runs/` に置き、
既存runや既存の `logs/` を削除・上書きしません。

## run ID

run ID は実験名、variant、seed、UTC開始日時から作ります。

```text
<experiment>_<variant>_s<seed>_<YYYYMMDDTHHMMSSZ>
```

例:

```text
privileged_critic_baseline_s42_20260813T120000Z
privileged_critic_privileged_s42_20260813T120000Z
```

同じseedと開始日時を持つvariantをpaired comparisonとして扱います。一方だけ失敗したpairは
公式集計へ含めません。runの状態は `running`, `completed`, `failed`, `interrupted`,
`smoke_test` のいずれかで記録します。

## 設定の責務

- `TrainingConfig` と `train.py` CLIが、学習コードで利用可能な設定の正本です。
- `common.toml` は比較時に固定する値、`variant.toml` は意図した差分の正本です。
- ランナーはTOMLを読み取ってもよいですが、解決した値を明示的なCLIへ変換し、
  実行コマンドとresolved metadataをrunごとに保存します。
- baselineとvariantでは、検証対象以外のseed・学習条件・評価条件を一致させます。

## Git管理

| 対象 | Git | 備考 |
| --- | --- | --- |
| `experiments/<experiment>/README.md` | 管理する | 仮説と評価方法 |
| `common.toml`, `variant.toml` | 管理する | 比較条件 |
| `results/summary.csv`, `<run_id>.toml` | 管理する | 小さい結果・metadata |
| `runs/<experiment>/<run_id>/` | 管理しない | モデル、ログ、TensorBoard |
| 既存の `logs/`, `models/` | 変更しない | legacy artifactを保持 |

公式runは原則としてclean working treeから開始し、Git commit、branch、dirty状態、
lockfile、Python/PyTorch/CUDA/GPU情報をmetadataへ記録します。

## 現在の実験

- [`experiments/privileged_critic/`](./experiments/privileged_critic/README.md):
  baseline PPOとPrivileged Critic PPOの比較
- 実験一覧: [`experiments/README.md`](./experiments/README.md)

Privileged Critic比較の起動例:

```bash
RUN_KIND=smoke_test TIMESTEPS=10000 GPU_IDS=0,1 \
  ./scripts/run_privileged_experiment.sh
```

TensorBoard:

```bash
.venv/bin/tensorboard --logdir runs/privileged_critic
```
