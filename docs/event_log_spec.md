# GodField Event Log & History Specification

強化学習AIエージェントの Observation 入力およびビジュアライザ・リプレイ用のイベントログ構造に関する仕様書です。

## 概要
GodFieldのゲーム進行中に発生するすべてのプレイヤー行動（カード仮置き、攻撃確定、ガード等）および自動ゲームイベント（病発作、全体攻撃の命中失敗、守護神効果、昇天弓発射、ダメージ適用等）を構造化された `GameEvent` オブジェクトとして記録します。

`InternalState` 内にリングバッファとして保持され、観測時 (`get_observation`) に観測プレイヤーの視点に合わせた正規化（プレイヤーIDのXOR変換および非公開手札/山札カードIDのマスキング `0`）が適用されます。

---

## 1. データ構造

### EventType (イベント種別)
```cpp
enum class EventType : uint8_t {
    NONE = 0,
    STAGE_CARD = 1,       // カード仮置き (武器/防具/奇跡/雑貨等)
    UNSTAGE_CARD = 2,     // 仮置き解除
    CONFIRM_ATTACK = 3,   // 攻撃確定
    CONFIRM_DEFENSE = 4,  // 防御確定 (ガード)
    PASS_DEFENSE = 5,     // 防御スルー (ダメージ直接受領)
    ATTACK_HIT = 6,       // 攻撃ヒット
    ATTACK_MISS = 7,      // 攻撃ミス / 命中失敗 (全体攻撃等)
    EFFECT_SICKNESS = 8,  // 病気効果発動 (天国病の発作, 地獄病等)
    EFFECT_GUARDIAN = 9,  // 守護神効果発動
    REFLECT_DAMAGE = 10,  // 反射 / バウンス発動
    TAKE_DAMAGE = 11,     // ダメージ適用
    HEAL_HP = 12,         // HP回復
    HEAL_MP = 13,         // MP回復
    BUY_CARD = 14,        // カード購入
    SELL_CARD = 15,       // カード売却
    EXCHANGE = 16,        // 両替
    DRAW_CARD = 17,       // カードドロー
    DISCARD_CARD = 18     // カード廃棄
};
```

### GameEvent (構造体)
```cpp
struct GameEvent {
    uint8_t actor;       // 発生主体 (観測時: 0=自分, 1=相手)
    uint8_t event_type;  // EventType
    int16_t card_id;     // 関連カードID (非公開情報は 0 にマスキング, なしは -1)
    int16_t target_id;   // 対象プレイヤーID (観測時: 0=自分, 1=相手, なしは -1)
    float value;         // ダメージ量 / 回復量 / 成功フラグなどの値
    int16_t extra_info;  // 補足情報 (属性, 病気種別, 守護神種別等)
};
```

---

## 2. 視点正規化と非公開情報マスキング

Observation 生成時 (`get_observation(state, observer_id)`):
1. **Actor / Target の正規化**:
   - `observer_id` を基準として、`actor == observer_id` の場合は `0` (自分)、それ以外は `1` (相手) に反転。
   - `target_id` も同様に反転。
2. **非公開カードのマスキング**:
   - 相手が手札から仮置きした段階で、まだ確定（`confirm_card`）していないカードや公開されていないカードIDは `card_id = 0` (裏向き/非公開) に置き換えて出力。
   - 確定（攻撃確定、防御確定、使用）した時点で、実際の `card_id` が記録されたイベントが出力されます。

---

## 3. ビジュアライザでの利用

`visualize_server.py` は C++ から取得した `Observation.history` を日本語テキストおよび JSON イベントオブジェクトに変換してフロントエンドに提供します。
フロントエンドは連続したイベントをキューイングし、一定間隔で順次再生することで、細切れ・スキップの発生を防ぎます。
