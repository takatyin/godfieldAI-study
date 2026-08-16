# Hand Value NN

## 目的

`HandValueModel` は、対局途中の状態から学習者視点の最終結果を推定する教師あり学習
モデルです。名前は Hand Value ですが、手札だけでなく通常観測、両者の真の
HP/MP/所持金、両者の真の手札を入力するため、実際には状態の outcome value
estimator です。

予測対象は次の3値です。

| 最終結果 | label |
| --- | ---: |
| 学習者の勝ち | `+1` |
| 引き分け | `0` |
| 学習者の負け | `-1` |

この推定値は方策やcriticの入力には加えません。Potential-Based Reward Shaping
（PBRS）のポテンシャル `Φ(s)` としてのみ使い、疎な終端報酬を途中状態へ伝えます。

## 処理の流れ

```text
strategic 対 strategic の自己対戦
        │
        ├─ 10 decisionごとに状態を保存
        └─ 対局終了後、各状態へ最終勝敗を付与
                    │
                    ▼
              dataset.npz
                    │ episode単位で80/20分割
                    ▼
             HandValueModel
                    │ validation MSE最小
                    ▼
              best_model.pt
                    │
                    ▼
       HandValuePotentialShaper ──► PotentialShaper ──► 環境報酬
```

## データ収集

収集処理は `scripts/collect_hand_value_data.py` と
`godfield_rl/hand_value_data.py` にあります。現在の既定設定は以下です。

- seed: `42`
- 対戦: strategic同士
- 対局数: `100,000`
- 並列環境数: `128`
- learner seat: `0`
- sampling interval: `10 decisions`

実行方法:

```bash
uv run python scripts/collect_hand_value_data.py
```

出力先:

```text
runs/hand_value_data/hand_value_data_s<seed>_<UTC timestamp>/dataset.npz
```

NPZには次の配列を保存します。

| key | 内容 |
| --- | --- |
| `obs` | learner視点の通常観測 |
| `stats` | `[p0_hp, p0_mp, p0_money, p1_hp, p1_mp, p1_money]` の真値 |
| `my_hands` | learnerの真の手札 |
| `opp_hands` | 相手の真の手札 |
| `labels` | learner視点の最終勝敗 `-1 / 0 / +1` |
| `episode_ids` | 状態が属するepisode ID |

収集終了時点で未完了だったepisodeのサンプルは除外します。また、同じepisodeの状態が
trainとvalidationへ混ざるリークを防ぐため、`split_by_episode()`でepisode単位に
80/20分割します。

## モデル

実装は `godfield_rl/hand_value_model.py` の`HandValueModel`です。

```text
obs (820)
  └─ Linear(820, 128) → ReLU → Linear(128, 64) → ReLU

my_hands / opp_hands
  └─ 共通Embedding(295, 16) → paddingを除くmean pooling

[obs feature 64, stats 6, my hand 16, opp hand 16]
  └─ concat(102)
  └─ Linear(102, 64) → ReLU
  └─ Linear(64, 32) → ReLU
  └─ Linear(32, 1)
  └─ value (B,)
```

手札の`-1`はpaddingです。モデル内部でIDへ1を加え、embedding index `0`をpaddingに
割り当てます。両手札には同じembeddingを使います。

最終層に`tanh`や`clamp`はありません。教師あり学習時に出力をclipすると、範囲外で
勾配が消えるためです。そのためraw predictionは理論上`[-1, 1]`を外れることが
あります。clipはreward shapingで利用するときだけ行います。

## 学習とartifact

学習処理は`scripts/train_hand_value_model.py`です。

```bash
# 自動選択されたdatasetを使用
uv run python scripts/train_hand_value_model.py

# datasetを明示
uv run python scripts/train_hand_value_model.py \
  --dataset runs/hand_value_data/<run>/dataset.npz
```

datasetを省略した場合は、更新日時が新しい2つのNPZを調べ、その2つのうち
`labels`の件数が多い方を採用します。現在の学習設定は30 epochs、batch size 256、
Adam、learning rate `1e-3`、MSE lossです。

出力先は最大の既存連番に1を加えたrunです。

```text
runs/hand_value_model/hand_value_model_<number>/
├── best_model.pt   # 全epoch中、validation MSEが最小のcheckpoint
├── final_model.pt  # 最終epochのcheckpoint
├── metrics.json    # 全epochのtrain/validation metrics
└── config.json     # dataset、分割、学習条件、モデル構成
```

checkpointには`model_state_dict`、`optimizer_state_dict`、epoch、metrics、
`model_config`が含まれます。推論・shapingには原則として`best_model.pt`を使います。

### 現在の保存済み30 epoch run

`hand_value_model_2`では520,073状態を含むdatasetをepisode単位に分割し、train
416,672件、validation 103,401件で学習しました。

| checkpoint | epoch | train MSE | validation MSE |
| --- | ---: | ---: | ---: |
| best | 4 | 0.297720 | **0.297906** |
| final | 30 | **0.259255** | 0.319797 |

train lossだけが下がりvalidation lossが悪化したため、epoch 4以降には過学習傾向が
あります。validationに対して訓練ラベル平均を常に返すbaselineのMSEは約`0.340923`
で、best modelはこれを約12.6%改善しています。

## Reward Shapingへの接続

実装は`godfield_rl/shaping.py`と`godfield_rl/env_wrapper.py`にあります。
`shape_hand != 0`で`make_shaper()`を呼ぶと、次の処理が自動で行われます。

1. `runs/hand_value_model/hand_value_model_<number>`の最大番号を選ぶ
2. そのrunの`best_model.pt`を読み込む
3. checkpointの`model_config`でモデルを再構築する
4. モデルを指定deviceへ移し、`eval()`モードにする
5. `shape_hand`をhand valueの係数`alpha`として`PotentialShaper`へ組み込む

最新runに`best_model.pt`がなければ、古いrunへ黙って戻らず`FileNotFoundError`を
送出します。`shape_hand == 0`ならモデルの探索も読み込みも行いません。

合成されるポテンシャルは次のとおりです。

```text
Φ_stats(s) = HP/MP/所持金の重み付き差
Φ_NN(s)    = clip(HandValueModel(s), -clip_value, +clip_value)
Φ_HP(s)    = (learner_hp - opponent_hp) / 99
Φ_hand(s)  = Φ_NN(s) - BETA * Φ_HP(s)
Φ_total(s) = Φ_stats(s) + shape_hand * Φ_hand(s)

r_shape = gamma * Φ_total(s_next) - Φ_total(s)
```

`BETA = 0.524088152132`は、`hand_value_model_2/best_model.pt`の学習に使った
datasetのepisode単位validation splitで、clip後の`ΔΦ_NN`を`ΔΦ_HP`へ
最小二乗回帰した傾きです。NN potentialからHP差と線形に重複する変化を除き、
`shape_hp`と`shape_hand`によるHP報酬の二重計上を抑えます。回帰の切片はHPと
共変する成分ではないため、potentialからは引きません。

既定の`clip_value`は`1.0`で、`Φ_NN`を`[-1, 1]`へ制限した後にHP成分を
差し引きます。`HandValueModel.forward()`のraw出力には影響しません。終端遷移では
`Φ_total(s_next) = 0`として、自動reset後の新episodeのpotentialが混ざるのを防ぎます。

実験設定では`shape_hand`を指定します。

```toml
[reward_shaping]
shape_hp = 0.2
shape_mp = 0.0
shape_money = 0.0
shape_hand = 0.2
```

内部ではこの値が`TrainingConfig.shape_hand`から`make_shaper(..., hand=...)`へ渡ります。
`gamma`はPPOと`PotentialShaper`で同じ値を使います。

モデルの探索先とclip幅も実験TOMLまたはCLIから変更できます。

```toml
[reward_shaping]
shape_hand = 0.2
hand_value_model_dir = "runs/hand_value_model"
hand_value_clip_value = 1.0
```

実験runnerは選択した`best_model.pt`のパス、SHA-256、重み、clip幅を
`run_meta.toml`の`[hand_value_model]`へ記録します。Hand Value推論はPPOと同じdeviceで
実行されます。

## 特権情報に関する注意

hand value estimatorは両者の真の手札とstatsを使います。したがって、これは通常の
対戦時に単独で利用できるpolicy componentではなく、シミュレータが完全な状態を持つ
学習時のreward shaping専用機能です。Actorへ相手の真の手札を渡しているわけでは
ありません。

また、PBRSが保証するのは正しいgammaと状態ポテンシャルを使ったときに最適方策を
変えないことです。推定器の品質が低い場合、有限時間での学習を改善するとは限りません。
`shape_hand`、clip範囲、学習速度への効果はbaselineとの比較実験で確認してください。

## 関連ファイル

- `scripts/collect_hand_value_data.py`: データ収集の設定とNPZ保存
- `godfield_rl/hand_value_data.py`: 並列対戦、状態収集、勝敗ラベル付与
- `godfield_rl/hand_value_dataset.py`: dtype変換とepisode単位分割
- `godfield_rl/hand_value_model.py`: NN本体
- `scripts/train_hand_value_model.py`: 学習、best/final checkpoint保存
- `godfield_rl/shaping.py`: モデル読込とpotential合成
- `godfield_rl/env_wrapper.py`: 各遷移の状態をshaperへ提供
- `tests/rl/test_hand_value_potential_shaper.py`: clip、合成、読込、環境統合テスト
