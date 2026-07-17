# ゴッドフィールド カード（神器）YAMLスキーマ定義

カードの持つあらゆる情報を一元管理し、強化学習環境（C++）やゲームロジックで利用するためのYAMLスキーマを定義します。
YAMLファイル上では**不必要なプロパティは記述せず**、パース時（あるいはC++ロード時）にデフォルト値（数値なら `0`、文字列なら `""`）として補完される想定です。

## 1. 共通プロパティ (全てのカードが持つ)

| プロパティ名 | 型 | デフォルト値 | 説明 |
| :--- | :--- | :--- | :--- |
| `name` | string | `""` | 神器の名前 |
| `id_str` | string | `""` | C++用コンパイル時定数やアセット指定のための英字ID (例: `"super_mirror"`) |
| `description` | string | `""` | 特殊効果などの説明テキスト |
| `type` | string | `""` | カードの種類。見た目やカテゴライズ上の問題。許可される値: `"weapon"` (武器), `"defense"` (防具), `"miracle"` (奇跡), `"sundry"` (雑貨), `"deal"` (取引) |
| `usage_timing` | list[string] | `[]` | カードを使用可能なフェイズの集合。下記の「許可されるフェイズ」を参照。 |
| `price` | int | `0` | 売値 |
| `drop_rate` | int | `1` | ドロー確率（分子 / 500）。例: 0.6%なら `3`。 |

### `usage_timing` に許可されるフェイズ一覧

`docs/game_flow.md` に基づき、以下の文字列の配列として定義します。空配列 `[]` の場合は受動発動などの特殊カードとなります。スーパーミラーのような例外はシステム側で個別対応します。

- `"main_atk_phase"`: メインフェイズの「攻撃」の始点として使える
- `"main_miracle_phase"`: メインフェイズの「奇跡」の始点として使える
- `"main_sundry_phase"`: メインフェイズの「雑貨」として使える
- `"main_deal_phase"`: メインフェイズの「取引（売る・買う等）」の対象として使える
- `"atk_plus_phase"`: 攻撃追加フェイズ（攻撃のプラス）に使える
- `"miracle_plus_phase"`: 奇跡追加フェイズ（奇跡のコストを0にする等）に使える
- `"atk_defence_phase"`: 相手からの物理/属性攻撃に対する防御フェイズに使える
- `"miracle_defence_phase"`: 相手からの奇跡に対する防御フェイズに使える

---

## 2. 条件付きプロパティ

カードの `type` や `usage_timing` に応じて必要になるプロパティです。該当しない場合はYAMLには記述しません（省略します）。

### 属性 (Element)
`type` が `"weapon"`, `"defense"`, `"miracle"` のいずれかである場合、または攻撃・防御フェイズで使用可能な場合に記述します。

| プロパティ名 | 型 | デフォルト値 | 説明 |
| :--- | :--- | :--- | :--- |
| `element` | string | `""` | 属性。`"火"`, `"水"`, `"木"`, `"土"`, `"光"`, `"闇"`, `""`(無属性) のいずれか。攻防兼用の場合は共通の属性となります。 |

### 攻撃関連
`type` が `"weapon"` であるか、または `usage_timing` に `"atk_plus_phase"`, `"main_atk_phase"`, `"main_miracle_phase"` のいずれかを含む場合に記述します。

| プロパティ名 | 型 | デフォルト値 | 説明 |
| :--- | :--- | :--- | :--- |
| `attack_power` | int | `0` | 攻撃力。プラスのみのカード（例：吹き矢 `+1`）も数値として `1` を持つ。 |
| `hit_curse` | string | `""` | ダメージを与えた時に相手に付与する状態異常。`"fog"`, `"flash"`, `"dark cloud"`, `"dream"`, `"cold"`, `"fever"`, `"hell"`, `"heaven"` のいずれか。 |

### 命中率・全体攻撃関連
`type` が `"weapon"` または `"miracle"` の場合に記述します。

| プロパティ名 | 型 | デフォルト値 | 説明 |
| :--- | :--- | :--- | :--- |
| `accuracy` | int | `100` | 命中率（%）。単体攻撃武器/奇跡の場合は必ず `100`。全体攻撃の場合は `0 < accuracy < 100` になります。 |
| `is_group_attack` | bool | `false` | 全体攻撃フラグ。真の場合、ターゲットは相手全体 `OPP` に制限され、自傷（自分対象）ができなくなります。また、命中率 `accuracy` は必ず 100 未満（0より大きく100未満）に設定されます。 |

### 防御関連
`type` が `"defense"` であるか、または `usage_timing` に `"atk_defence_phase"` を含む場合に記述します。

| プロパティ名 | 型 | デフォルト値 | 説明 |
| :--- | :--- | :--- | :--- |
| `defense_power` | int | `0` | 防御力。 |

### 反射・無効化関連（リアクション）
`usage_timing` に `"atk_defence_phase"` や `"miracle_defence_phase"` を持ち、かつ弾く・反射・阻止の効果を持つカードに記述します。

| プロパティ名 | 型 | デフォルト値 | 説明 |
| :--- | :--- | :--- | :--- |
| `reaction_type` | string | `""` | `"bounce"` (50%反射/50%自傷), `"reflect"` (100%反射), `"block"` (阻止・無効化) のいずれか。 |

### 奇跡関連
`type` が `"miracle"` の場合に記述します。

| プロパティ名 | 型 | デフォルト値 | 説明 |
| :--- | :--- | :--- | :--- |
| `mp_cost` | int | `0` | 消費MP。 |

---

## YAML 記述例

### 例1: 攻撃専用の武器（普通の武器）
```yaml
name: "銅のこん棒"
type: "weapon"
usage_timing:
  - "main_atk_phase"
price: 1
drop_rate: 3
attack_power: 1
accuracy: 100
```

### 例2: 攻撃・防具兼用武器（ソードシールドなど）
```yaml
name: "ソードシールド"
description: "守10"
type: "weapon"
usage_timing:
  - "main_atk_phase"
  - "atk_defence_phase"
price: 15
drop_rate: 1
attack_power: 10
defense_power: 10
accuracy: 100
```

### 例3: 攻撃プラスで攻撃もできる武器（吹き矢など）
```yaml
name: "吹き矢"
type: "weapon"
usage_timing:
  - "main_atk_phase"
  - "atk_plus_phase"
price: 1
drop_rate: 2
attack_power: 1
accuracy: 100
```

### 例4: 弾く系防具（反射剣など）
```yaml
name: "反射剣"
description: "無属性武器をはね返す"
type: "weapon"
usage_timing:
  - "main_atk_phase"
  - "atk_defence_phase"
price: 5
drop_rate: 1
attack_power: 10
accuracy: 100
reaction_type: "bounce"
```
