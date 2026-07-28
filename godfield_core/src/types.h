#pragma once
#include "constants.h"
#include "xoshiro.h"
#include <random>
#include <array>
#include <iterator>

enum Element : uint8_t { ELEM_NONE = 0, ELEM_FIRE, ELEM_WATER, ELEM_WOOD, ELEM_STONE, ELEM_LIGHT, ELEM_DARKNESS };
enum ReactionType : uint8_t { REACTION_NONE = 0, REACTION_BOUNCE, REACTION_REFLECT, REACTION_BLOCK };
enum HitCurse : uint8_t {
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

enum SicknessType : uint8_t {
    SICKNESS_NONE = 0,
    SICKNESS_COLD = 1,
    SICKNESS_FEVER = 2,
    SICKNESS_HELL = 3,
    SICKNESS_HEAVEN = 4
};

enum CurseType : uint8_t { 
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

enum PhenomenonType {
    PHENOMENON_SUNSET = 0,          // 夕焼け: 全員熱病
    PHENOMENON_DENSE_FOG = 1,       // 濃霧: 全員霧
    PHENOMENON_MUSHROOM = 2,        // きのこ大発生: ご乱心ターン増加
    PHENOMENON_TORNADO = 3,         // 竜巻: 全員HP 1
    PHENOMENON_GIGANTIC_TUB = 4,    // 巨大なタライ: 自分か相手に光属性攻50
    PHENOMENON_BLACK_HOLE = 5,      // ブラックホール: 全員に闇属性全体攻30
    PHENOMENON_WARM_CURRENT = 6,    // 暖流: 自身HP+50
    PHENOMENON_GOLD_MINE = 7,       // 金山: お金集約
    PHENOMENON_MAGNETIC_STORM = 8,  // 磁気嵐: 手札相互交換
    PHENOMENON_ECLIPSE = 9          // 日食: 守護神割り当て
};


enum class DreamGroup : uint8_t {
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

enum class CardType : uint8_t {
    WEAPON = 0,
    DEFENSE,
    MIRACLE,
    SUNDRY,
    DEAL,
    DEVIL,
    PHENOMENA,
    GUARDIAN
};

struct alignas(64) CardFeatures {
    // 4-byte fields
    uint32_t usage_timing = 0;
    int price = 0;
    int drop_rate = 0;
    int attack_power = 0;
    int defense_power = 0;
    int accuracy = 100;
    int mp_cost = 0;

    // 1-byte fields (enums)
    CardType type = CardType::SUNDRY;
    Element element = ELEM_NONE;
    ReactionType reaction_type = REACTION_NONE;
    HitCurse hit_curse = CURSE_NONE;
    DreamGroup dream_group = DreamGroup::NONE;

    // 1-byte fields (bools)
    bool is_group_attack = false;

    inline bool is_weapon() const { return type == CardType::WEAPON; }
    inline bool is_defense() const { return type == CardType::DEFENSE; }
    inline bool is_miracle() const { return type == CardType::MIRACLE; }
    inline bool is_sundry() const { return type == CardType::SUNDRY; }
    inline bool is_deal() const { return type == CardType::DEAL; }
    inline bool is_devil() const { return type == CardType::DEVIL; }
    inline bool is_phenomena() const { return type == CardType::PHENOMENA; }
    inline bool is_guardian() const { return type == CardType::GUARDIAN; }
};

enum class GamePhase {
    PHASE_GUARDIAN,
    PHASE_MAIN,
    PHASE_MAIN_TARGET_SELECT,
    PHASE_ATTACK_PLUS,
    PHASE_GROUP_WEAPON,
    PHASE_MIRACLE_PLUS,
    PHASE_GROUP_MIRACLE_PLUS,
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
    PHASE_END,
    NUM_PHASES
};

constexpr int NUM_PHASES = static_cast<int>(GamePhase::NUM_PHASES);

enum class TurnEndSubstep : int {
    DEATH_CHECK_START = 0,    // ターン開始時/終了時等の死亡・お守り・昇天弓チェック
    SICKNESS_WORSEN = 1,      // 病気悪化判定
    SICKNESS_DAMAGE = 2,      // 病気ダメージ/回復処理
    FINAL_DEATH_CHECK = 3,    // 勝敗最終確定前の死亡チェック
    GUARDIAN_ACT = 4,         // 相手の守護神の行動判定と実行
    CLEANUP_DEATH_CHECK = 5,  // クリーンアップ前の死亡チェック
    CLEANUP = 6,              // 手札補充・奇跡再配置などのクリーンアップ処理
    TURN_TRANSITION = 7       // クリーンアップ後の死亡チェックとターン交代
};

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
    DISCARD_CARD = 18,    // カード廃棄
    REFUSE_DEAL = 19,     // 取引見送り・購入拒否
    BLOCK_ATTACK = 20,    // 阻止発動 (BLOCK)
    BOUNCE_ATTACK = 21,   // 弾く発動 (BOUNCE: value=1.0で成功, 0.0で失敗)
    TRIGGER_PHENOMENON = 22, // 超常現象発動 (運命のひも等: value=phenomenon_id)
    REFLECT_MIRROR = 23,  // スーパーミラーによる対象反転発動 (売る/買う/雑貨等の跳ね返し)
    RING_EFFECT = 24,     // 指輪の効果・反撃発動
    GUARDIAN_ENTER = 25,  // 守護神降臨
    GUARDIAN_LEAVE = 26,  // 守護神退散
    EFFECT_CURSE = 27,    // 呪い状態変化
    INSTANT_DEATH = 28    // 闇属性による即死 (ダメージとは別枠でHPが0になる)
};

// ============================================================================
// イベント用ビットマスク定数 (GameEvent.value 形式)
// ============================================================================

// EventType::EFFECT_SICKNESS (8) の GameEvent.value 用ビットマスク定義
namespace SicknessEvent {
    constexpr int MASK_TYPE       = 0x0F; // 下位4ビット: 病気種別
    constexpr int TYPE_NONE       = 0;
    constexpr int TYPE_COLD       = 1;    // 風邪
    constexpr int TYPE_FEVER      = 2;    // 熱病
    constexpr int TYPE_HELL       = 3;    // 地獄病
    constexpr int TYPE_HEAVEN     = 4;    // 天国病

    constexpr int FLAG_DAMAGE     = 1 << 4; // 16 (病気ダメージ発生)
    constexpr int FLAG_HEAL       = 1 << 5; // 32 (病気回復発生)
    constexpr int FLAG_WORSENED   = 1 << 6; // 64 (病気の悪化・進行)
    constexpr int FLAG_SEIZURE    = 1 << 7; // 128 (発作・死亡)
    constexpr int FLAG_CURED      = 1 << 8; // 256 (病気の治癒。種別は治る前の病気)
}

// EventType::EFFECT_CURSE (27) の GameEvent.value 用ビットマスク定義
namespace CurseEvent {
    constexpr int MASK_TYPE       = 0x0F;
    constexpr int TYPE_FOG        = 1;    // 霧
    constexpr int TYPE_FLASH      = 2;    // 閃光
    constexpr int TYPE_DARK_CLOUD = 3;    // 暗雲
    constexpr int TYPE_DREAM      = 4;    // 夢

    constexpr int FLAG_APPLIED    = 1 << 4; // 16 (付与)
    constexpr int FLAG_CLEARED    = 1 << 5; // 32 (解除)
}

struct GameEvent {
    float actor;       // 0: 自分(観測者), 1: 相手 (視点正規化時に観測者視点に正規化される)
    float event_type;  // EventType enum
    float card_id;     // 関連カードID (非公開情報は 0 にマスキング, なしは -1)
    float target_id;   // 対象プレイヤー (0: 自分, 1: 相手, なしは -1)
    float value;     // ダメージ量 / 回復量 / 成功フラグなどの値
};

struct alignas(64) Observation {
    // 数値ステータス (0.0 ~ 1.0 に正規化して渡す)
    float hp_me, hp_opp;
    float mp_me, mp_opp;
    float money_me, money_opp;

    // 状態異常・病・守護神 (排他要素は独立したOne-hot次元として表現)
    float sickness_me[NUM_SICKNESS_TYPES]; // 病 (なし, 風邪, 熱病, 地獄病, 天国病)
    float sickness_opp[NUM_SICKNESS_TYPES];
    float curses_me[NUM_CURSE_TYPES]; // 霧, 閃光, 暗雲, 夢 (Multi-hot)
    float curses_opp[NUM_CURSE_TYPES];
    float guardian_me[NUM_GUARDIAN_TYPES]; // 守護神 (なし=0, 火星神=1, ..., 月神=10)
    float guardian_opp[NUM_GUARDIAN_TYPES];

    // 計算済みサポート数値と特殊状態
    float incoming_damage;        // 飛んできている総ダメージ
    float current_staged_defense; // 現在仮置きしている防具の合計
    float is_apocalypse;          // 終末の時フラグ (通常=0.0, 150ターン以降=1.0)
    float turn_progress;          // current_turn / TURN_PROGRESS_SCALE_TURNS (0.0 ~ 1.0 で飽和)
    float turns_to_apocalypse;    // max(0, APOCALYPSE_TURN - current_turn) / APOCALYPSE_TURN (1.0 ~ 0.0)

    // フェイズ情報
    float phase_one_hot[NUM_PHASES]; // 現在のフェイズ (State1 ~ State6, StateM)

    // カードID群 (Embedding層へ入力)
    float hand_cards[MAX_HAND_SIZE];            // 自分の手札（夢状態ならC++で偽装済みIDを入れる）
    float staged_cards[MAX_HAND_SIZE];          // 現在の仮置き場
    float opponent_hand_cards[MAX_HAND_SIZE];   // 相手の手札（非公開=0, 既知のカード・使用済み奇跡=実ID）
    float opponent_staged_cards[MAX_HAND_SIZE]; // 相手が場に出しているカードID（攻撃順など）

    // イベント履歴（リングバッファ: 64 * 5 = 320 float + 1 float head = 321 float）
    GameEvent history[HISTORY_LENGTH];
    float history_head;  // 次に書き込むインデックス

    // 合法手マスク (インデックス 450..571)
    float action_mask[ACTION_SPACE_SIZE]; // 1.0 = 選択可能, 0.0 = 選択不可
};

static_assert(sizeof(Observation) % sizeof(float) == 0, "Observation must be float-aligned");
static_assert(sizeof(GameEvent) % sizeof(float) == 0, "GameEvent must be float-aligned");

/**
 * @brief 仮置き場に置かれた1枚を表します。
 *
 * 出しているカードは通常「手札のどのスロットか」で表せますが、守護神が仕掛ける
 * 「売る」「買う」だけは、そのカード自体を手札に持ちません。以前はこれを
 * staged_cards（int の生配列）に番兵 -1 を入れて表現していましたが、
 *   - 番兵を手札の添字にすると範囲外を読む（クラッシュせず誤った値で計算が続く）
 *   - 「売る」と「買う」の区別が num_staged_cards の値という暗黙のルールだった
 * ため、過去に3度バグの原因になりました（売り手の取り違え、観測への範囲外読み出し、
 * 合法手計算の潜在的な範囲外参照）。
 *
 * slot が NO_HAND_SLOT のときだけ virtual_card が意味を持ちます。手札由来のカードは
 * IDをここに持たず、読むたびに手札から解決します（夢の確定で見た目が変わるため、
 * IDをキャッシュすると確定後に古い値が残ります）。
 */
constexpr int NO_HAND_SLOT = -1;

struct StagedEntry {
    int slot = NO_HAND_SLOT;      // 手札スロット。手札に無いカードなら NO_HAND_SLOT
    int virtual_card = CARD_EMPTY; // slot == NO_HAND_SLOT のときだけ有効

    static StagedEntry from_hand(int hand_slot) { return StagedEntry{hand_slot, CARD_EMPTY}; }
    static StagedEntry virtual_of(int card_id) { return StagedEntry{NO_HAND_SLOT, card_id}; }

    bool is_from_hand() const { return slot >= 0 && slot < MAX_HAND_SIZE; }
};

struct StagedCardIds {
    std::array<int, MAX_HAND_SIZE> ids;
    int count = 0;

    StagedCardIds() = default;
    StagedCardIds(std::initializer_list<int> list) {
        for (int val : list) {
            if (count < MAX_HAND_SIZE) {
                ids[count++] = val;
            }
        }
    }

    int* begin() { return ids.data(); }
    const int* begin() const { return ids.data(); }
    int* end() { return ids.data() + count; }
    const int* end() const { return ids.data() + count; }

    bool empty() const { return count == 0; }
    size_t size() const { return static_cast<size_t>(count); }
    int operator[](size_t idx) const { return ids[idx]; }
    int back() const { return count > 0 ? ids[count - 1] : -1; }
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
    // ゲーム固有の乱数生成器。内部状態16バイト（mt19937 は5000バイトあり、
    // この構造体の69%を占めていた）。詳細は xoshiro.h を参照。
    Xoshiro128PP rng;
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

    // 病と災い (Sickness & Curses)
    SicknessType sickness[2];   // 0:なし, 1:風邪, 2:熱病, 3:地獄病, 4:天国病
    bool curses[2][NUM_CURSE_TYPES];         // 0:霧, 1:閃光, 2:暗雲, 3:夢
    GuardianType guardian[2];   // 守護神ID (0: なし, 1..10: 守護神)

    // 状態遷移用変数
    GamePhase current_phase;

    // 仮置き場。中身の読み出しは必ず staged_card_id() を通すこと（StagedEntry のコメント参照）。
    StagedEntry staged_cards[2][MAX_HAND_SIZE];
    int num_staged_cards[2];            // 仮置き枚数

    // この解決を仕掛けた側のプレイヤーID（取引・雑貨の反射確認で使う。-1 は該当なし）。
    // スーパーミラーで反射すると attacker_id / defender_id が入れ替わるため、
    // 「今の攻撃側 = 仕掛けた人」は成り立たない。以前は仮置き場を逆算して
    // 探しており、見つからなければ黙って推測していた（売り手を取り違える原因）。
    int pending_initiator;

    // 戦闘処理状態管理 (Phase 2 以降用)
    int attacker_id;                // 攻撃側のプレイヤーID
    int defender_id;                // 防御側のプレイヤーID (自分自身を攻撃する場合もあるため必要)
    int pending_attack_power;       // 現在保留中の攻撃力
    Element pending_attack_element; // 現在保留中の攻撃の属性
    int pending_defense_power;      // 現在保留中の防御力
    bool pending_absorption;        // 現在保留中の攻撃がHP吸収を持つか
    bool pending_deal_same_damage;  // 現在保留中の攻撃が自傷効果（邪神の大剣）を持つか
    bool pending_is_group_attack;   // 現在保留中の攻撃が全体攻撃であるか


    // 取引 (Phase 6 両替用テンポラリ変数)
    int exchange_sum;
    int exchange_hp;

    // ターン終了時処理 (PHASE_END) のステートマシン用
    TurnEndSubstep turn_end_state;              // ターン終了処理のステートマシン管理用
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

    // === イベント履歴 (リングバッファ) ===
    GameEvent history[HISTORY_LENGTH];
    int history_head = 0;  // 次に書き込むインデックス
    int history_count = 0; // 通算イベント生成数
};
