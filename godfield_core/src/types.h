#pragma once
#include "constants.h"
#include <random>

enum Element { ELEM_NONE = 0, ELEM_FIRE, ELEM_WATER, ELEM_WOOD, ELEM_STONE, ELEM_LIGHT, ELEM_DARKNESS };
enum ReactionType { REACTION_NONE = 0, REACTION_BOUNCE, REACTION_REFLECT, REACTION_BLOCK };
enum HitCurse {
    CURSE_NONE = 0,
    CURSE_FOG,
    CURSE_FLASH,
    CURSE_DARK_CLOUD,
    CURSE_DREAM,
    CURSE_COLD,
    CURSE_FEVER,
    CURSE_HELL,
    CURSE_HEAVEN
};

enum SicknessType {
    SICKNESS_NONE = 0,
    SICKNESS_COLD = 1,
    SICKNESS_FEVER = 2,
    SICKNESS_HELL = 3,
    SICKNESS_HEAVEN = 4
};

enum CurseType { 
    CURSE_TYPE_FOG = 0, 
    CURSE_TYPE_FLASH = 1, 
    CURSE_TYPE_DARK_CLOUD = 2, 
    CURSE_TYPE_DREAM = 3 
};

enum GuardianType {
    GUARDIAN_NONE = 0,
    GUARDIAN_MARS = 1,
    GUARDIAN_MERCURY = 2,
    GUARDIAN_JUPITER = 3,
    GUARDIAN_SATURN = 4,
    GUARDIAN_URANUS = 5,
    GUARDIAN_PLUTO = 6,
    GUARDIAN_NEPTUNE = 7,
    GUARDIAN_VENUS = 8,
    GUARDIAN_EARTH = 9,
    GUARDIAN_MOON = 10
};


enum class DreamGroup {
    NONE = 0,                       // 常に確定するグループ（夢の影響を受けない）
    SUNDRY_NORMAL,                  // 通常雑貨（15種）
    SUNDRY_PASSIVE,                 // 受動系雑貨（2種: 太陽のお守り, あぶないウス）
    DEF_MIRACLE_COUNTER,            // 奇跡対策防具（10種）
    DEF_SPIRITUAL,                  // 精霊系防具（3種）
    DEF_PLUS_ATK,                   // +攻撃防具（4種）
    DEF_NONE,                       // 無属性防具（18種、冥王の指輪含む）
    DEF_FIRE,                       // 火属性防具（10種）
    DEF_WATER,                      // 水属性防具（9種）
    DEF_WOOD,                       // 木属性防具（10種）
    DEF_EARTH,                      // 土属性防具（9種）
    DEF_LIGHT,                      // 光属性防具（3種）
    WPN_NORMAL,                     // 通常武器（54種）
    WPN_GROUP,                      // 全体攻撃武器（17種）
    WPN_PLUS,                       // プラス武器（19種）
    WPN_MIRACLE_COUNTER_PLUS,       // 奇跡対策プラス武器（2種）
    WPN_MIRACLE_COUNTER,            // 奇跡対策武器（4種）
    WPN_HYBRID,                     // 攻守兼用武器（6種）
    WPN_REFLECT                     // 無属性反射武器（2種: 反射剣, 乱弾武剣）
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
constexpr uint32_t TIMING_GUARDIAN = 1 << 8;

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
    bool is_group_attack;
    DreamGroup dream_group;
};

enum class GamePhase {
    PHASE_GUARDIAN,
    PHASE_MAIN,
    PHASE_MAIN_TARGET_SELECT,
    PHASE_ATTACK_PLUS,
    PHASE_GROUP_WEAPON,
    PHASE_MIRACLE_PLUS,
    PHASE_GROUP_MIRACLE,
    PHASE_DEFENSE,
    PHASE_MIRACLE_DEFENSE,
    PHASE_SELL_SELECT,
    PHASE_SELL_SELECT_MIRROR,
    PHASE_BUY,
    PHASE_BUY_SELECT_MIRROR,
    PHASE_SUNDRY_SELECT_MIRROR,
    PHASE_EXCHANGE_HP,
    PHASE_EXCHANGE_MP,
    PHASE_DISCARD,
    PHASE_END
};

struct GameEvent {
    int actor;       // 0: 自分(観測者), 1: 相手 (視点正規化時に XOR で反転する)
    int phase;       // フェイズID
    int action_type; // 攻撃, 防御, スルー, 買う, 等
    int card_id;     // 使用されたカードID (非公開情報は 0 にマスキング)
    float damage;    // 確定したダメージ量などのスカラー値
};

struct alignas(64) Observation {
    // 数値ステータス (0.0 ~ 1.0 に正規化して渡す)
    float hp_me, hp_opp;
    float mp_me, mp_opp;
    float money_me, money_opp;

    // 状態異常・病・守護神 (排他要素は独立したOne-hot次元として表現)
    float sickness_me[5]; // 病 (なし, 風邪, 熱病, 地獄病, 天国病)
    float sickness_opp[5];
    float curses_me[4]; // 霧, 閃光, 暗雲, 夢 (Multi-hot)
    float curses_opp[4];
    float guardian_me[11]; // 守護神 (なし=0, 火星神=1, ..., 月神=10)
    float guardian_opp[11];

    // 計算済みサポート数値と特殊状態
    float incoming_damage;        // 飛んできている総ダメージ
    float current_staged_defense; // 現在仮置きしている防具の合計
    float is_apocalypse;          // 終末の時フラグ (通常=0.0, 150ターン以降=1.0)

    // フェイズ情報
    float phase_one_hot[7]; // 現在のフェイズ (State1 ~ State6, StateM)

    // カードID群 (Embedding層へ入力)
    int hand_cards[MAX_HAND_SIZE];            // 自分の手札（夢状態ならC++で偽装済みIDを入れる）
    int staged_cards[MAX_HAND_SIZE];          // 現在の仮置き場
    int opponent_hand_cards[MAX_HAND_SIZE];   // 相手の手札（非公開=0, 既知のカード・使用済み奇跡=実ID）
    int opponent_staged_cards[MAX_HAND_SIZE]; // 相手が場に出しているカードID（攻撃順など）
    int pending_card;                         // 注目カード（飛んできた攻撃や買う対象など。なし=0）

    // イベント履歴（リングバッファ）
    GameEvent history[HISTORY_LENGTH];
    int history_head; // 次に書き込むインデックス

    // 合法手マスク
    float action_mask[ACTION_SPACE_SIZE]; // 1.0 = 選択可能, 0.0 = 選択不可
};

struct Transition {
    Observation state; // その瞬間の観測
    int action;        // 選んだ行動
    float reward;      // そのターンの報酬
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
    std::mt19937 rng;     // ゲーム固有の乱数生成器
    int current_actor_id; // 現在行動権を持つプレイヤー (0 or 1)
    int current_turn;     // 現在の実際のターン数 (終末の時判定用)
    int mushroom_turns;   // きのこ大発生によるご乱心残りターン数 (0なら通常)

    // 基本ステータス群 (C++内では正規化前の生の値で管理)
    int hp[2], mp[2], money[2];

    // 手札情報と「既知のカード」の管理
    int true_hand[2][MAX_HAND_SIZE];               // 両プレイヤーの真の手札
    int apparent_hand[2][MAX_HAND_SIZE];           // エージェント/プレイヤーが見る手札（夢状態の幻覚を含む）
    bool is_confirmed[2][MAX_HAND_SIZE];           // 手札の中身が確定しているか（夢状態による未確定の管理）
    bool is_known_to_opp[2][MAX_HAND_SIZE];        // 相手に中身がバレているか
    bool is_used[2][MAX_HAND_SIZE];                // 今回のターン内で使用され、補充待ちのスロット
    bool is_deployed[2][MAX_HAND_SIZE];            // 奇跡が展開されているか
    bool miracle_used_this_turn[2][MAX_HAND_SIZE]; // 展開済みの奇跡がこのターン既に使用されたか
    int deployed_miracles_order[2][MAX_HAND_SIZE]; // 奇跡の展開順序 (FIFO制御用)
    int num_deployed_miracles[2];                  // 展開されている奇跡の個数

    // 病と災い (Sickness & Curses)
    SicknessType sickness[2];   // 0:なし, 1:風邪, 2:熱病, 3:地獄病, 4:天国病
    bool curses[2][4];         // 0:霧, 1:閃光, 2:暗雲, 3:夢
    GuardianType guardian[2];   // 守護神ID (0: なし, 1..10: 守護神)

    // 状態遷移用変数
    GamePhase current_phase;

    // Phase 1で使う仮置きバッファ (自分用/相手用など、まずは単純なバッファ)
    int staged_cards[2][MAX_HAND_SIZE]; // 現在のフェイズで場に出ている（仮置き中の）手札インデックス配列
    int num_staged_cards[2];            // 仮置き枚数

    // 戦闘処理状態管理 (Phase 2 以降用)
    int attacker_id;                // 攻撃側のプレイヤーID
    int defender_id;                // 防御側のプレイヤーID (自分自身を攻撃する場合もあるため必要)
    int pending_attack_power;       // 現在保留中の攻撃力
    Element pending_attack_element; // 現在保留中の攻撃の属性
    bool pending_absorption;        // 現在保留中の攻撃がHP吸収を持つか
    bool pending_deal_same_damage;  // 現在保留中の攻撃が自傷効果（邪神の大剣）を持つか
    bool pending_is_group_attack;   // 現在保留中の攻撃が全体攻撃であるか


    // 取引 (Phase 6 両替用テンポラリ変数)
    int exchange_sum;
    int exchange_hp;

    // ターン終了時処理 (PHASE_END) のステートマシン用
    int turn_end_state;              // 0: 死亡判定/お守り/昇天弓, 1: 病気悪化, 2: 病気ダメージ, 3: 引き分け, 4: 守護神, 5: クリーンアップ
    int pending_ascension_bows[2];   // 各プレイヤーの保留中昇天弓射撃回数
    bool heaven_seizure_occurred[2]; // 各プレイヤーが天国病悪化（発作）を起こしたか

    // 複数回攻撃（のこぶんぶん・蜃気楼）用
    int remaining_attacks;
    int base_attacker_id;
    int base_defender_id;
    int base_attack_power;
    Element base_attack_element;
    bool base_absorption;
    bool base_deal_same_damage;

    // === 指輪の反撃予約用スタック ===
    int num_pending_counters;
    int pending_counter_attacker[10];
    int pending_counter_defender[10];
    int pending_counter_power[10];
    Element pending_counter_element[10];
    HitCurse pending_counter_curse[10];
    bool pending_counter_take_cp[10];
    int pending_counter_source_id[10];

    // 反撃による災い・没収適用用
    HitCurse pending_attack_curse;
    bool pending_take_cp;
    int pending_attack_source_id; // 現在の攻撃の発生源カードID (-1: なし/空)

    // === 強化学習 (RL) 用の終了シグナルと報酬 ===
    // OpenAI Gym などの標準的な強化学習インターフェースに合わせるために必要不可欠な変数群です。
    // Python側で各環境が終了したかを判定し、方策(Policy)の更新に使う報酬を取得します。
    bool is_done;    // ゲームが終了したかどうか（誰かのHPが0になった、最大ターン数を超過した等）
    float p0_reward; // Player 0 が受け取る報酬（勝利で 1.0, 敗北で -1.0, 引き分けで 0.0）
    float p1_reward; // Player 1 が受け取る報酬（勝利で 1.0, 敗北で -1.0, 引き分けで 0.0）
};
