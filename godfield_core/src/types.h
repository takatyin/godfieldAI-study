#pragma once
#include "constants.h"
#include <random>

enum Element {
    ELEM_NONE = 0, ELEM_FIRE, ELEM_WATER, ELEM_WOOD, ELEM_EARTH, ELEM_LIGHT, ELEM_DARK
};
enum ReactionType {
    REACTION_NONE = 0, REACTION_BOUNCE, REACTION_REFLECT, REACTION_BLOCK
};
enum HitCurse {
    CURSE_NONE = 0, CURSE_FOG, CURSE_FLASH, CURSE_DARK_CLOUD, CURSE_DREAM, CURSE_COLD, CURSE_FEVER, CURSE_HELL, CURSE_HEAVEN
};

// usage_timing flags mask
constexpr uint32_t TIMING_MAIN_ATK = 1 << 0;
constexpr uint32_t TIMING_MAIN_MIRACLE = 1 << 1;
constexpr uint32_t TIMING_MAIN_SUNDRY = 1 << 2;
constexpr uint32_t TIMING_MAIN_DEAL = 1 << 3;
constexpr uint32_t TIMING_ATK_PLUS = 1 << 4;
constexpr uint32_t TIMING_MIRACLE_PLUS = 1 << 5;
constexpr uint32_t TIMING_ATK_DEFENCE = 1 << 6;
constexpr uint32_t TIMING_MIRACLE_DEFENCE = 1 << 7;

struct alignas(64) CardFeatures {
    bool is_weapon;
    bool is_defense;
    bool is_miracle;
    bool is_sundry;
    bool is_deal;
    uint32_t usage_timing;
    int price;
    int drop_rate;
    int attack_power;
    int defense_power;
    int accuracy;
    int mp_cost;
    Element element;
    ReactionType reaction_type;
    HitCurse hit_curse;
};

enum class GamePhase {
    STATE_0_GUARDIAN,
    STATE_1_MAIN,
    STATE_2_ATK_PLUS,
    STATE_3_MIRACLE_PLUS,
    STATE_M_SUPER_MIRROR,
    STATE_4_ATK_DEF,
    STATE_5_MIRACLE_DEF,
    STATE_6_END
};

struct GameEvent {
    int actor;         // 0: 自分(観測者), 1: 相手 (視点正規化時に XOR で反転する)
    int phase;         // フェイズID
    int action_type;   // 攻撃, 防御, スルー, 買う, 等
    int card_id;       // 使用されたカードID (非公開情報は 0 にマスキング)
    float damage;      // 確定したダメージ量などのスカラー値
};

struct alignas(64) Observation {
    // 数値ステータス (0.0 ~ 1.0 に正規化して渡す)
    float hp_me, hp_opp;
    float mp_me, mp_opp;
    float money_me, money_opp;
    
    // 状態異常・病・守護神 (排他要素は独立したOne-hot次元として表現)
    float sickness_me[5];         // 病 (なし, 風邪, 熱病, 地獄病, 天国病)
    float sickness_opp[5];
    float status_ailments_me[4];  // 霧, 閃光, 暗雲, 夢 (Multi-hot)
    float status_ailments_opp[4];
    float guardian_me[11];        // 守護神 (なし=0, 火星神=1, ..., 月神=10)
    float guardian_opp[11];
    
    // 計算済みサポート数値と特殊状態
    float incoming_damage;        // 飛んできている総ダメージ
    float current_staged_defense; // 現在仮置きしている防具の合計
    float is_apocalypse;          // 終末の時フラグ (通常=0.0, 150ターン以降=1.0)
    
    // フェイズ情報
    float phase_one_hot[7];       // 現在のフェイズ (State1 ~ State6, StateM)

    // カードID群 (Embedding層へ入力)
    int hand_cards[MAX_HAND_SIZE];           // 自分の手札（夢状態ならC++で偽装済みIDを入れる）
    int staged_cards[MAX_HAND_SIZE];         // 現在の仮置き場
    int opponent_hand_cards[MAX_HAND_SIZE];  // 相手の手札（非公開=0, 既知のカード・使用済み奇跡=実ID）
    int pending_card;                        // 注目カード（飛んできた攻撃や買う対象など。なし=0）

    // イベント履歴（リングバッファ）
    GameEvent history[HISTORY_LENGTH];
    int history_head;                        // 次に書き込むインデックス

    // 合法手マスク
    float action_mask[ACTION_SPACE_SIZE];    // 1.0 = 選択可能, 0.0 = 選択不可
};

struct Transition {
    Observation state;  // その瞬間の観測
    int action;         // 選んだ行動
    float reward;       // そのターンの報酬
};

/**
 * @brief ゲーム状態の完全な規定（ソース・オブ・トゥルース）
 *
 * プレイヤーから見えない非公開情報（相手の手札や山札の乱数シード等）を含め、
 * ゲームのあらゆるタイミングと状態を完全に保持する構造体。
 * 
 * TODO: 現状では仮置きカード等を使ったバウンスチェーンなどの
 * 複雑なマイクロステップに対応しきれていない部分があるため、今後の実装で拡張予定。
 */
struct alignas(64) InternalState {
    std::mt19937 rng;                     // ゲーム固有の乱数生成器
    int current_actor_id;                 // 現在行動権を持つプレイヤー (0 or 1)
    int current_turn;                     // 現在の実際のターン数 (終末の時判定用)
    
    // 基本ステータス群 (C++内では正規化前の生の値で管理)
    int hp[2], mp[2], money[2];
    int sickness[2];                      // 0:なし, 1:風邪, 2:熱病, 3:地獄病, 4:天国病
    int status_ailments[2];               // 状態異常のビットフラグ
    int guardian[2];                      // 守護神ID (0~10)
    
    // 手札情報と「既知のカード」の管理
    int true_hand[2][MAX_HAND_SIZE];      // 両プレイヤーの真の手札
    bool is_known_to_opp[2][MAX_HAND_SIZE]; // 相手に中身がバレているか (買うで見られた、売るで渡された等)
    
    // 状態遷移用変数
    GamePhase current_phase;
    int attacker_id;                      // 現在の攻撃（アクション）の主体
    int defender_id;                      // 現在の攻撃（アクション）の対象
    int staged_cards[2][MAX_HAND_SIZE];   // 現在のフェイズで場に出ている（仮置き中の）カードID配列
    int num_staged_cards[2];              // 仮置き枚数

    // 確定済み攻撃のパラメータ等（防衛側が参照する）
    int pending_attack_power;
    Element pending_element;
    HitCurse pending_hit_curse;
    int pending_accuracy;

    // n-step学習用ローカルキュー
    Transition n_step_queue_p0[N_STEP];
    Transition n_step_queue_p1[N_STEP];
    int queue_size_p0;
    int queue_size_p1;

    bool is_done;
    float p0_reward;
    float p1_reward;
};
