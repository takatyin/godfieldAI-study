# Experiments

全実験に共通する管理方法は [`experiment_plan.md`](./experiment_plan.md) にまとめています。

このディレクトリには、再現に必要な実験定義と小さな結果サマリーだけを置きます。
学習済みモデル、checkpoint、TensorBoard event、標準出力ログ、W&B のローカル生成物などは
リポジトリ直下の `runs/` に出力し、Git では管理しません。

## 方針

- 学習コードで利用可能な設定の正本は `godfield_rl.config.TrainingConfig` と `train.py` の CLI です。
- 実験定義の TOML は比較条件を固定してレビュー可能にする正本です。ランナーはTOMLを既定値として
  読み取れますが、解決した値を明示的なCLIへ変換し、実行コマンドとmetadataを保存します。
- 比較実験では共通条件を1ファイルに置き、各 variant のファイルには意図した差分だけを置きます。
- `common.toml` の `pairing.variants` がvariantの実行順を決めます。`GPU_IDS` の指定順に
  round-robinで割り当て、同じGPUに割り当てられたvariantは直列実行します。
- 実行ごとの日時、Git 情報、seed、解決済み条件、評価結果は小さな meta/summary としてここに残せます。
- 実行時生成物のパスは `runs/<experiment>/<run_id>/` とし、run 間で共有しません。

## 実験一覧

- [`privileged_critic/`](./privileged_critic/README.md): 通常の MaskablePPO と Privileged Critic PPO の比較

新しい比較を追加するときは、実験ごとに README、共通条件、variant 差分、結果サマリーをまとめ、
共通ランナーから起動します。実験ごとの実行スクリプトは不要です。

```bash
DRY_RUN=1 ./scripts/run_experiment.sh <experiment>
RUN_KIND=smoke_test GPU_IDS=0,1 ./scripts/run_experiment.sh <experiment>
```

`GPU_IDS` は1個以上の任意個数を指定できます。例えば `GPU_IDS=0` なら全variantを1枚で直列実行し、
`GPU_IDS=0,1` なら最大2本を並列実行します。各学習ログは `train.log` に保存されると同時に、
`[variant|GPU n]` 付きでターミナルにもリアルタイム表示されます。

Hand Value reward shapingの比較は次で確認・実行できます。

```bash
DRY_RUN=1 ./scripts/run_experiment.sh hand_value_shaping
RUN_KIND=smoke_test TIMESTEPS=10000 GPU_IDS=0,1 \
  ./scripts/run_experiment.sh hand_value_shaping
```

reward shapingなどの条件差は、各 `variant.toml` の同名sectionに差分だけを書きます。

```toml
[reward_shaping]
shape_hp = 0.2
shape_mp = 0.05
shape_money = 0.01
shape_hand = 0.0
```
