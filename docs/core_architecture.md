# C++コア（godfield_core）の構造

`InternalState` の構造と、責務の分割、そして「なぜその形になっているか」をまとめます。
個々のゲーム仕様は `rules.md` / `phase_specifications.md` / `dream_curse.md` を参照してください。

---

## 1. ファイルの責務

| ファイル | 責務 |
|---|---|
| `types.h` | `InternalState` / `Observation` / `CardFeatures` などの型 |
| `constants.h` | 確率・初期値・配列次元などの定数（**値をここ以外に書かない**） |
| `game_logic.cpp` | `step_game`（1ステップ進める）/ `get_legal_actions` / `make_observation` / `init_new_game` |
| `phase_handlers.cpp` | フェイズごとの `step_phase_*`（状態を書き換える） |
| `legal_actions.cpp` | フェイズごとの `legal_phase_*`（**状態を読むだけ**） |
| `combat_resolution.cpp` | ダメージ解決・取引・守護神・超常現象・ターン終了処理 |
| `card_registry.cpp` | カードマスタの読み込みと抽選テーブルの構築 |
| `rng.cpp` / `rng.h` | 乱数消費点のラベル付けとテストからの値注入 |
| `env_pool.cpp` | 環境の並列実行（**ゲームのルールを持たない**） |
| `bindings.cpp` | pybind11 の公開層 |

`env_pool` がゲーム詳細を持たないのは意図的です。初期HP・初期手札の配り方などは
`init_new_game()`（`game_logic.cpp`）が持ちます。

---

## 2. InternalState（2,240バイト）

環境の数だけ並ぶ構造体なので、サイズがそのままキャッシュ効率になります。

### 乱数エンジン

`std::mt19937` は内部状態が5,000バイトあり、この構造体の**69%**を占めていました。
ゲームシミュレータに必要なのは長周期ではなく「偏りのない乱数を大量に速く」なので、
**xoshiro128++**（内部状態16バイト、周期 2^128-1、BigCrush 通過）に置き換えています。

| | Before | After |
|---|---|---|
| `InternalState` | 7,232 B | **2,240 B** |
| EnvPool reset | 189.7 K/s | **747.2 K/s** |

`UniformRandomBitGenerator` の要件を満たすので `std::uniform_int_distribution` /
`std::shuffle` にそのまま渡せます。詳細は `xoshiro.h`。

**注意**: 乱数列は mt19937 と異なります。同じシードでも以前と同じ試合にはなりません。
これが問題にならないのは、テストが特定のシードの結果に依存しなくなっているためです
（`testing_guide.md` を参照）。

### 手札の3層表現

```cpp
int  true_hand[2][18];       // 真の手札
int  apparent_hand[2][18];   // 見えている手札（夢による偽装を含む）
bool is_confirmed[2][18];    // 中身が確定しているか
```

夢状態では `apparent_hand` に偽の姿が入り、確定時に `true_hand` の値へ同期します。
**カードIDをどこかにキャッシュしてはいけません。** 確定後に古い値が残ります。

読み出しは `card_id_in_hand(state, player, slot)` に集約しています。
以前は「apparent を見て負なら true を見る」という同じ2行が11箇所に散っており、
一部だけ範囲検査があるという不統一でした。

### 仮置き場（StagedEntry）

```cpp
struct StagedEntry {
    int slot;          // 手札スロット。手札に無いカードなら NO_HAND_SLOT
    int virtual_card;  // slot == NO_HAND_SLOT のときだけ有効
};
StagedEntry staged_cards[2][18];
```

守護神が仕掛ける「売る」「買う」は、そのカード自体を手札に持ちません。
以前はこれを番兵 `-1` で表現していましたが、**3度バグの原因になりました**。

1. 売り手の取り違え（`staged_cards[p][1]` を `ID_SELL(=1)` と比較していた）
2. 観測への範囲外読み出し（`true_hand[1][-1]` が相手の手札スロット17を読んでいた）
3. 合法手計算の潜在的な範囲外参照

読み出しは必ず以下を通します。**直接 `staged_cards[p][i]` を手札の添字にしないこと。**

| 関数 | 返すもの |
|---|---|
| `staged_card_id(state, p, i)` | カードID（手札由来なら手札から解決、仮想カードならそのID） |
| `staged_hand_slot(state, p, i)` | 手札スロット。手札由来でなければ `NO_HAND_SLOT` |
| `get_staged_card_ids(state, p)` | 解決済みIDの一覧 |

手札由来のカードがIDを持たないのは、上記の夢の理由です。仮想カードは確定という
概念がなく変化しないため、値で持って問題ありません。

### pending_initiator

```cpp
int pending_initiator;  // この解決を仕掛けた側（-1 は該当なし）
```

スーパーミラーで反射すると `attacker_id` / `defender_id` が入れ替わるため、
**「今の攻撃側 = 仕掛けた人」は成り立ちません。** 以前はこれを仮置き場から逆算して
探しており、見つからなければ黙って推測していました（売り手を取り違える原因）。

仕掛けた時点で記録し、`execute_sell_resolution` と `step_phase_sundry_select_mirror`
はこれを読みます。記録が無い場合は例外を投げます（黙って誤った相手に決済するより
落ちたほうがよい種類の異常です）。

`cleanup_phase_end` でターンごとにクリアされます。

---

## 3. Observation（2,368バイト）

行動する側についてのみ、毎ステップ構築されます（`make_observation`）。

- 数値は 1/100 に正規化（HP 40 → 0.4）
- カードIDはそのまま入れて Embedding 層へ渡す
- **相手の公開手札と仮置きは左詰め**（スロット位置から手札構成が漏れるのを防ぐため）
- 末尾に合法手マスク

`is_known_to_opp` / `is_deployed` が立っているカードだけが相手から見えます。
仮置きは確定（`TARGET_*` / `CONFIRM`）した時点で公開されます。

観測の各区間の内訳と、学習側がそれをどう使うかは `rl_architecture.md` を参照。

---

## 4. EnvPool（並列実行）

`step_all` のループに `#pragma omp parallel for` を掛けて、複数スレッドで各環境を
進めます。`InternalState` と `Observation` は事前に一括確保し、False Sharing を
避けるため `alignas(64)` を付けています。

乱数は環境ごとの `InternalState::rng` に持たせてあり、完全にスレッドローカルです。
山札の抽選も**重みを展開したフラットテーブルからの一様抽選**なので、共有状態を
書き換えません（以前は `std::discrete_distribution` を使っており、`operator()` が
内部状態を書き換えるため mutex で排他していました。フラットテーブル化で排他が
不要になり、同時に 42.33 ns/draw → 5.12 ns/draw になっています）。

### シードの衝突回避

初期シードは `seed_ + env_id`。自動リセット時は
`seed_ + num_envs_ * (1 + reset_counts_[env_id]++) + env_id` を使います。
リセット回数や環境IDが違えば同じシードにならないので、並列実行のどこかで
同じゲーム展開が重複することがありません。

### 終端観測のキャッシュ

`EnvPool` は決着した環境をそのステップ内で自動リセットします。何もしないと
「リセット後の初期状態」しか返らず、価値関数のブートストラップに必要な
**終端時点の観測が消えます**。

`step_env` は `is_done` を検出したら `reset_env` を呼ぶ**直前**に
`make_observation` を実行し、`terminal_obs_buffers_[2]` に保存します。

**プレイヤーごとに1本ずつ持つ点が重要です。** 決着は学習者の手番だけでなく
相手の手番でも起こるため、行動者視点の終端観測をそのまま使うと、相手の攻撃で
負けたときに「相手視点の盤面」でブートストラップしてしまいます。報酬も同じ理由で
`get_rewards_for(player_id)` を使います（行動者視点の `get_rewards()` は
相手が勝ったときに符号が逆になります）。

### ターン数による打ち切りはしない

上級者同士では膠着して150ターンの「終末の時」に入ることがあり、その展開も
学習させたいので、**人為的なエピソード打ち切りは行いません**。決着は
`run_death_check` だけが決めます。

打ち切りを安全弁に使えない以上、**進行不能な状態を作らないこと自体が要件**です。
合法手が0件になる状態は `tests/rl/test_rl_pipeline.py` が検出します。

なお `TURN_PROGRESS_SCALE_TURNS`（300）は観測 `turn_progress` の正規化基準で、
打ち切りには使いません。`current_turn` はこの値を超えうるので、`turn_progress`
側で 1.0 に飽和させています。

---

## 5. ターン終了処理はステートマシン

`resolve_turn_end_steps` は `TurnEndSubstep` で状態を持ちます。途中で防御フェイズが
立ち上がる（昇天弓の発射、守護神の攻撃）とプレイヤーの入力が必要になるため、
1関数で回し切ることができないからです。

```
DEATH_CHECK_START → SICKNESS_WORSEN → SICKNESS_DAMAGE → FINAL_DEATH_CHECK
  → GUARDIAN_ACT → CLEANUP_DEATH_CHECK → CLEANUP → TURN_TRANSITION
```

戻り値 `true` は「入力待ちのため中断した」を意味し、再開時は `turn_end_state` から
続きが実行されます。

守護神の行動は守護神ごとの関数（`resolve_neptune_action` など）に分かれています。
戻り値は「防御フェイズなどを開いて処理を中断したか」で統一しています。

---

## 6. 触るときの注意

- **カードマスタを直接編集しない**。`assets/cards/*.yaml` を編集して
  `tools/build_cards.py` で再生成します（`assets/godfield_cards.json` は生成物）
- **確率・初期値は `constants.h` に書く**。テストもそこから読むので、
  値を変えてもテストの書き換えが不要になります
- **同じカードの組み合わせが2箇所以上に現れたら述語にする**
  （`is_non_damage_ring_counter` / `is_element_overriding_wand` など）。
  片方だけ直す事故を防ぐためです
- C++を変更したら**型スタブを再生成**します（`.agents/AGENTS.md`）
