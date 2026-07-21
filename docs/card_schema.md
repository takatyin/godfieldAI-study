# ゴッドフィールド カード（神器）YAMLスキーマ定義

カードの持つあらゆる情報を一元管理し、強化学習環境（C++）やゲームロジックで利用するためのYAMLスキーマを定義します。
YAMLファイル上では**不必要なプロパティは記述せず**、パース時（あるいはC++ロード時）にデフォルト値（数値なら `0`、文字列なら `""`、ブーリアンなら `false`）として補完される想定です。

---

## 1. 共通プロパティ (全てのカードが持つ)

| プロパティ名 | 型 | デフォルト値 | 説明 |
| :--- | :--- | :--- | :--- |
| `id` | int | - | ビルド時（JSON出力時）に自動的に割り振られる連続した一意の非負整数（0始まり）。YAML側には記述しません。 |
| `name` | string | `""` | 神器の名前 |
| `id_str` | string | `""` | C++用コンパイル時定数やアセット指定のための英字ID。サブディレクトリによる階層化が含まれます (例: `"armor/super-mirror"`, `"phenomena/magnetic-storm"`) |
| `description` | string | `""` | 特殊効果などの説明テキスト。 |
| `type` | string | `""` | カードの種類。以下の「許可されるカードタイプ」を参照。 |
| `usage_timing` | list[string] | `[]` | カードを使用可能なフェイズの集合。以下の「許可されるフェイズ」を参照。 |
| `price` | int | `0` | 売値。仮想的なカード（悪魔、守護神行動など）は `0`。 |
| `drop_rate` | int | `1` | ドロー確率（分子 / 500）。例: 0.6%なら `3`。仮想カードは `0`。 |

### `type` に許可されるカードタイプ一覧
*   `"weapon"`: 武器。メインフェイズで攻撃に使用できるカード。
*   `"defense"`: 防具。相手の物理・属性・奇跡攻撃を防ぐカード（指輪含む）。
*   `"miracle"`: 奇跡。MPを消費して発動するカード（攻撃・防御・追加効果など）。
*   `"sundry"`: 雑貨。さまざまな即時効果や回復、補助効果を持つカード。
*   `"deal"`: 取引。売る・買う・両替などの金銭取引カード。
*   `"devil"`: 悪魔。終末の時（Apocalypse）にドローした際、即時効果を発動するカード。
*   `"phenomena"`: 超常現象。守護神フェイズにおいて自動的に発動し、攻撃などを伴う現象カード。
*   `"guardian"`: 守護神行動。守護神が召喚されている場合に、守護神フェイズで自動的に発動する行動カード（仮想カード）。

### `usage_timing` に許可されるフェイズ一覧

`docs/game_flow.md` に基づき、以下の文字列の配列として定義します。空配列 `[]` の場合は受動発動などの特殊カードとなります。スーパーミラーのような例外はシステム側で個別対応します。

*   `"main_atk_phase"`: メインフェイズの「攻撃」の始点として使える
*   `"main_miracle_phase"`: メインフェイズの「奇跡」の始点として使える
*   `"main_sundry_phase"`: メインフェイズの「雑貨」として使える
*   `"main_deal_phase"`: メインフェイズの「取引（売る・買う等）」の対象として使える
*   `"atk_plus_phase"`: 攻撃追加フェイズ（攻撃のプラス）に使える
*   `"miracle_plus_phase"`: 奇跡追加フェイズ（奇跡のコストを0にする等）に使える
*   `"atk_defence_phase"`: 相手からの物理/属性攻撃に対する防御フェイズに使える
*   `"miracle_defence_phase"`: 相手からの奇跡に対する防御フェイズに使える
*   `"guardian_phase"`: 守護神フェイズ中に自動発動または処理されるカードに使える

---

## 2. 条件付きプロパティ（キーのホワイトリスト）

カードの `type` に応じて記述が許可されるプロパティが制限されます。記述されていないプロパティはデフォルト値が適用されます。

| カードタイプ | 許容キー一覧 |
| :--- | :--- |
| `weapon` | `name`, `id_str`, `description`, `type`, `usage_timing`, `price`, `drop_rate`, `element`, `attack_power`, `defense_power`, `accuracy`, `is_group_attack`, `reaction_type`, `hit_curse` |
| `defense` | `name`, `id_str`, `description`, `type`, `usage_timing`, `price`, `drop_rate`, `element`, `defense_power`, `attack_power`, `accuracy`, `reaction_type` |
| `miracle` | `name`, `id_str`, `description`, `type`, `usage_timing`, `price`, `drop_rate`, `element`, `attack_power`, `accuracy`, `is_group_attack`, `hit_curse`, `mp_cost`, `reaction_type` |
| `sundry` | `name`, `id_str`, `description`, `type`, `usage_timing`, `price`, `drop_rate`, `attack_power`, `hit_curse` |
| `deal` | `name`, `id_str`, `description`, `type`, `usage_timing`, `price`, `drop_rate` |
| `devil` | `name`, `id_str`, `description`, `type`, `usage_timing`, `price`, `drop_rate` |
| `phenomena` | `name`, `id_str`, `description`, `type`, `usage_timing`, `price`, `drop_rate`, `element`, `attack_power`, `accuracy`, `is_group_attack` |
| `guardian` | `name`, `id_str`, `description`, `type`, `usage_timing`, `price`, `drop_rate`, `element`, `attack_power`, `accuracy`, `is_group_attack`, `hit_curse` |

---

## 3. 各プロパティの詳細な制約

### 属性 (`element`)
*   **型**: string
*   **デフォルト値**: `""`
*   **値の制限**: `"火"`, `"水"`, `"木"`, `"土"`, `"光"`, `"闇"`, `""`(無属性) のいずれか。

### 攻撃力 (`attack_power`)
*   **型**: int
*   **デフォルト値**: `0`
*   **値の制限**: 非負整数 (\( \ge 0 \))。
*   **注意**: 防具（鬼シリーズなど）における反撃ダメージや、雑貨（ちからの粉）の追加ダメージ、超常現象のダメージ、守護神行動のダメージにも適用されます。

### 防御力 (`defense_power`)
*   **型**: int
*   **デフォルト値**: `0`
*   **値の制限**: 非負整数 (\( \ge 0 \))。
*   **注意**: 武器（ソードシールドなど）における防御効果にも適用されます。

### 命中率 (`accuracy`)
*   **型**: int
*   **デフォルト値**: `100`
*   **値の制限**: 0以上100以下の整数 (\( 0 \le \text{accuracy} \le 100 \))。
*   **注意**: 全体攻撃の命中率や、防御カード（火星の指輪）における守護神発動確率に適用されます。

### 全体攻撃フラグ (`is_group_attack`)
*   **型**: bool
*   **デフォルト値**: `false`
*   **値の制限**: `true` または `false`。
*   **論理制約**: 真の場合、命中率 `accuracy` は必ず100未満（0より大きく100未満）に設定されます（ただし、守護神行動 `guardian` は除く）。

### ステータス異常 (`hit_curse`)
*   **型**: string
*   **デフォルト値**: `""`
*   **値の制限**: `"fog"` (霧), `"flash"` (閃光), `"dark cloud"` (暗雲), `"dream"` (夢), `"cold"` (風邪), `"fever"` (熱), `"hell"` (地獄), `"heaven"` (天国) のいずれか。

### 反射・無効化関連（`reaction_type`）
*   **型**: string
*   **デフォルト値**: `""`
*   **値の制限**: `"bounce"` (50%反射/50%自傷), `"reflect"` (100%反射), `"block"` (阻止・無効化), `""` (なし) のいずれか。
*   **論理制約**: このキーが存在する場合、`usage_timing` に必ず `"atk_defence_phase"` または `"miracle_defence_phase"` が含まれていなければなりません。

### 消費MP (`mp_cost`)
*   **型**: int
*   **デフォルト値**: `0`
*   **値の制限**: 非負整数 (\( \ge 0 \))。
