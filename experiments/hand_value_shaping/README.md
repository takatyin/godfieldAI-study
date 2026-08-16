# Hand Value Reward Shaping比較

HP差だけのPBRSを使う`baseline`と、最新の学習済み`HandValueModel`によるpotentialを
追加した`hand_value`を、同一seed・同一PPO条件で比較します。

## 条件差

| variant | `shape_hp` | `shape_hand` |
| --- | ---: | ---: |
| baseline | 0.2 | 0.0 |
| hand_value | 0.2 | 0.2 |

`hand_value`は`runs/hand_value_model/hand_value_model_<最大番号>/best_model.pt`を読み込み、
予測を`[-1, 1]`へclipしてから、validation差分回帰の傾き`BETA`を使って
HP差と線形に重複する成分を除いたpotentialを加えます。選択されたcheckpointとSHA-256は
各runの`run_meta.toml`へ保存されます。評価環境にはreward shapingを入れません。

## 実行

```bash
# 定義、checkpoint、生成コマンドだけ確認
DRY_RUN=1 ./scripts/run_experiment.sh hand_value_shaping

# 短い動作確認（GPU 1枚なら2 variantを直列実行）
RUN_KIND=smoke_test TIMESTEPS=10000 GPU_IDS=0 \
  ./scripts/run_experiment.sh hand_value_shaping

# 2 GPUで本実験
RUN_KIND=full GPU_IDS=0,1 \
  ./scripts/run_experiment.sh hand_value_shaping
```

## 実行ログ

実行ごとにUTC開始時刻を含む別のディレクトリへ保存されるため、過去の実験は
上書きされません。

```text
runs/hand_value_shaping/<run_id>/
├── checkpoints/final_model.zip
├── tensorboard/
├── logs/
│   ├── command.log
│   └── train.log
└── run_meta.toml
```

学習中の標準出力はターミナルに表示されると同時に`train.log`へ保存されます。
TensorBoardは次のコマンドでbaselineとhand_valueの両方をまとめて確認できます。

```bash
.venv/bin/tensorboard --logdir runs/hand_value_shaping
```

環境変数`HAND_VALUE_WEIGHT`で共通値を上書きできますが、variant側の明示値が最後に
適用されます。通常の比較ではTOMLを正本として変更してください。
