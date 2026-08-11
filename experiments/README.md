# Experiments

このディレクトリには、再現に必要な実験定義と小さな結果サマリーだけを置きます。
学習済みモデル、checkpoint、TensorBoard event、標準出力ログ、W&B のローカル生成物などは
リポジトリ直下の `runs/` に出力し、Git では管理しません。

## 方針

- 学習設定の実装上の唯一の情報源は `godfield_rl.config.TrainingConfig` と `train.py` の CLI です。
- 実験定義の TOML は CLI の値を固定してレビュー可能にするための記録です。TOML を直接読み込む
  新しい設定ローダーや実験管理ライブラリは追加しません。
- 比較実験では共通条件を1ファイルに置き、各 variant のファイルには意図した差分だけを置きます。
- 実行ごとの日時、Git 情報、seed、解決済み条件、評価結果は小さな meta/summary としてここに残せます。
- 実行時生成物のパスは `runs/<experiment>/<run_id>/` とし、run 間で共有しません。

## 実験一覧

- [`privileged_critic/`](./privileged_critic/README.md): 通常の MaskablePPO と Privileged Critic PPO の比較

新しい比較を追加するときは、実験ごとに README、共通条件、variant 差分、結果サマリーをまとめ、
既存の CLI・TensorBoard・W&B・評価ツールを再利用してください。
