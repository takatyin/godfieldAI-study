# Experiment Plan

この文書を GodFieldAI における実験管理の共通ルールとします。
実験固有の目的、仮説、条件差、評価指標は各実験ディレクトリの README と TOML に定義し、
この文書には全実験で共通する運用方法をまとめます。

## 基本原則

- 1 run につき一意な `run_id` と専用ディレクトリを作り、既存 run を上書きしない。
- 学習条件だけでなく、Git commit、dirty 状態、seed、評価条件まで記録する。
- 完了した run だけでなく、smoke test、中断、失敗もステータス付きで残す。
- 比較実験では、比較対象以外の条件を固定する。
- モデルやログなどの大きな生成物と、再現に必要な小さな定義・集約結果を分ける。

## ディレクトリ構成

実験定義と小さな結果は Git で管理します。

```text
experiments/<experiment>/
├── README.md
├── common.toml
├── <variant>/variant.toml
└── results/
    ├── summary.csv
    ├── run_meta.template.toml
    └── <run_id>.toml
```

学習時に生成される大きなファイルは Git 管理外の `runs/` に保存します。

```text
runs/<experiment>/<run_id>/
├── checkpoints/
│   └── final_model.zip
├── tensorboard/
├── logs/
│   ├── command.log
│   ├── train.log
│   └── eval.log
└── wandb/
```

`run_id` は実験、variant、seed、UTC 開始日時から作ります。

```text
<experiment>_<variant>_s<seed>_<YYYYMMDDTHHMMSSZ>
```

## 実行前

1. 実験の目的と検証可能な仮説を README に書く。
2. 共通条件を `common.toml`、意図した条件差だけを `variant.toml` に書く。
3. 評価指標、評価相手、試合数、評価 seed、集約方法を学習前に固定する。
4. 比較する variant には同じ seed を割り当て、paired comparison とする。
5. まず短い smoke test を行い、配線、ログ、保存、評価コマンドを確認する。
6. 公式 run は原則として clean な working tree と同一 commit から実行する。
7. `run_meta.template.toml` から `<run_id>.toml` を作り、次を記録する。

   - Git commitとbranch
   - working treeのdirty状態
   - 開始日時
   - variantとseed
   - 解決済みの全学習条件
   - 評価条件
   - artifactの保存先
   - W&Bを使う場合はrun IDまたはURL

## 実行中

- 実際に実行したコマンドを `logs/command.log` に保存する。
- 標準出力と標準エラーを `logs/train.log` に保存する。
- TensorBoard には少なくとも勝率、value loss、explained variance、policy loss、
  entropy、KL、clip fraction、FPSを記録する。
- 必要に応じてwall-clock timeとpeak VRAMも記録する。
- 途中経過だけで成功と判断せず、モデル保存と固定評価の完了まで確認する。

## 実行後

1. run の状態を `completed`、`failed`、`interrupted`、`smoke_test` のいずれかで記録する。
2. 固定済みの条件で最終モデルを評価し、出力を `logs/eval.log` に保存する。
3. `<run_id>.toml` に終了日時、状態、評価結果、所要時間、備考を追記する。
4. `results/summary.csv` に1 run 1行で、比較に使う最終値または事前定義した集約値を追記する。
5. モデルのSHA256を記録する。外部ストレージやW&B Artifactへ保存した場合はURLも記録する。
6. 片方が失敗したseed pairは公式比較に含めない。
7. dirtyな状態で行ったrunは予備実験として残し、公式集計から除外する。

## 比較と再現性

- 初期確認は1 seedで行い、本比較は最低3 seed、可能なら5 seedで実施する。
- 単一runの最高値ではなく、seed間の平均、標準偏差、各paired差を報告する。
- 学習中の勝率と、固定条件による最終評価勝率を区別する。
- 設定ファイルだけでなく、使用したcommitとlockfileを再現条件に含める。
- TensorBoardはローカルの時系列確認に使い、W&Bは複数runの比較とartifact保管に利用できる。

## 現在確認できる既存run

2026-08-12 時点で、次のartifactを確認しています。ただし3回分の完全な実験記録は揃っていません。

| artifact | 内容 | 扱い |
| --- | --- | --- |
| `assets/models/league_v5_50M.zip` | 50,048,000 steps、seed 42のモデル | 完了モデル。ただし対応ログとrun metaなし |
| `godfield_agent.zip` | 8 steps、seed 42のbaselineモデル | smoke test |
| `logs/tb/MaskablePPO_1/` | `time/fps`が1点 | smoke testのログ |
| `logs/tb/MaskablePPO_2/` | 4 steps時点の`time/fps`が1点 | 中断または失敗。モデルなし |

これらは後から推測で公式結果にせず、`legacy` または `smoke_test` として扱います。
今後のrunはこの計画に従い、実行時点でメタデータと結果を記録します。

## 実験チェックリスト

### 実行前

- [ ] 目的と仮説を記述した
- [ ] 共通条件とvariant差分を固定した
- [ ] 評価条件を固定した
- [ ] run IDとrun directoryを新規作成した
- [ ] Git commit、branch、dirty状態を記録した
- [ ] seedと解決済み設定を記録した
- [ ] smoke testが成功した

### 実行後

- [ ] モデルが保存された
- [ ] TensorBoardと学習ログが保存された
- [ ] 固定評価が完了した
- [ ] run statusと終了日時を記録した
- [ ] modelのSHA256を記録した
- [ ] run metaを更新した
- [ ] `summary.csv`へ追記した
- [ ] paired runが両方揃っていることを確認した
