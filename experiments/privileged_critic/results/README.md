# Results index

`summary.csv` には1 run を1行で追記します。TensorBoard の時系列全体を CSV に複製せず、
比較に使った最終値または事前に決めた集約値だけを記録してください。実行ごとの詳細は
`scripts/run_privileged_experiment.sh` が `run_meta.template.toml` と同じ構造の
`<run_id>.toml` をこのディレクトリへ生成し、実行状態と解決済みの値を更新します。

モデル、TensorBoard event、標準出力、checkpoint、W&B ローカルファイルは
`runs/privileged_critic/<run_id>/` に置き、ここへコピーしません。

公式な比較行では `working_tree_dirty=false` を原則とします。dirty な状態で予備実験をした場合は、
その事実を残し、公式集計には混ぜないでください。
