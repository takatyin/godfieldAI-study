#pragma once
#include "types.h"
#include <algorithm>
#include <cstdint>
#include <random>
#include <vector>

// ============================================================================
// 乱数消費点のラベル付けと、テストからの値注入 / Labelled RNG with test injection
// ============================================================================
//
// 【なぜこの層があるのか】
// ゲームロジックには「50%で弾く」「5%で病気が悪化する」のように確率で分岐する箇所が
// 30個以上あります。これらをテストするために、以前はシード値を総当たりして目的の
// 結果になる seed を探していました（最大 100,000 回の探索）。この方式には
//   1. 探索が遅い
//   2. seed_rng(42) がどの分岐を意図しているのかコードから読めない
//   3. C++ 側の乱数消費順を1つ変えると、無関係なテストが一斉に落ちる
//   4. 探索が空振りしたテストが「seed が見つかった」だけを検証する空のテストに退化する
// という致命的な問題がありました。
//
// そこで、乱数を消費する箇所すべてに RollKind というラベルを付け、テストから
// 「この判定はこの値を返せ」と宣言的に指示できるようにしています。
//
// 【本番（学習時）のコスト】
// スクリプトは thread_local ポインタで保持し、本番では常に nullptr です。
// EnvPool::step_all は OpenMP で並列化されているため、ワーカースレッドからは
// 必ず nullptr に見えます（テストがメインスレッドで仕込んだ値が漏れることはなく、
// データレースにもなりません）。追加コストは TLS ポインタ1つの比較のみで、
// 実測 0.096 ns/draw でした。
//
// 【注意】
// テストがスクリプトを仕込んだまま EnvPool.step_all を呼ぶと、OpenMP のマスター
// スレッド（= メインスレッド）が処理する環境だけがスクリプトを見ます。環境間で
// 挙動が揃わないため、この組み合わせは避けてください。conftest.py の autouse
// フィクスチャが各テストの終わりにスクリプトを破棄するので、テスト間の漏れは
// 構造的に防がれています。

enum class RollKind : uint8_t {
    // --- 命中・反射・反撃の判定 ---
    ACCURACY = 0,          // 武器・守護神攻撃の命中率判定 (0..99, roll >= accuracy でミス)
    BOUNCE,                // ＜弾く＞の成功判定 (0..99, roll < BOUNCE_SUCCESS_RATE で成功)
    MARS_RING,             // 火星の指輪の反撃発動 (0..99, roll < MARS_RING_RATE で発動)

    // --- ターン終了処理の判定 ---
    GUARDIAN_LEAVE,        // 被ダメージ時の守護神離脱 (0..99, roll < GUARDIAN_LEAVE_RATE で離脱)
    ASCENSION_BOW_HIT,     // 昇天弓の命中 (0..99, roll < ASCENSION_BOW_HIT_RATE で命中)
    SICKNESS_WORSEN,       // 病気の悪化 (0..99, roll < SICKNESS_WORSEN_RATE で悪化)
    GUARDIAN_ACT,          // 守護神が行動するか (0..99, roll < GUARDIAN_ACT_RATE で行動)
    GUARDIAN_ACT_CHOICE,   // 5種の行動のどれを選ぶか (0..99, GUARDIAN_ACTION_PERCENT で分割)
    MOON_MIRACLE,          // 月神が発動する奇跡の選択 (0..MOON_MIRACLE_COUNT-1)

    // --- 超常現象（運命のひも） ---
    PHENOMENON,                // 10種の現象の抽選 (0..9, PhenomenonType と同じ値)
    PHENOMENON_TUB_TARGET,     // 巨大なタライの対象 (0..1, プレイヤーID)
    PHENOMENON_GOLD_MINE,      // 金山でお金を集める側 (0..1, プレイヤーID)
    PHENOMENON_ECLIPSE_G0,     // 日食でP0に就く守護神 (1..10)
    PHENOMENON_ECLIPSE_G1,     // 日食でP1に就く守護神 (1..9, G0 と重複しないよう補正される)
    PHENOMENON_MAGNETIC_STORM, // 磁気嵐の手札シャッフル（順序系）

    // --- 雑貨・悪魔カードの効果 ---
    GUARDIAN_POT,          // 守護神の壺で降臨する守護神 (1..10)
    THUMP_THUMP_TEAR,      // どきどきのなみだ (0..1, 0 で +10 / 1 で -10)
    DEVIL_FAIRY,           // 慈善の妖精 (0..2, 0=HP / 1=MP / 2=お金)
    DEVIL_PRANKSTER,       // いたずら妖精が捨てる2枚（2回連続で消費される）

    // --- 山札とドロー ---
    DECK_DRAW,             // 山札からの抽選（スクリプト値はカードIDそのもの）
    APOCALYPSE_DRAW,       // 終末の時の悪魔抽選 (0..99, APOCALYPSE_DEVILS の出現率で分割)
    DREAM_DISGUISE,        // 夢状態で偽装されるか (0..99, 50未満で偽装される)
    DREAM_FAKE_CARD,       // 夢状態で表示される偽装カード（スクリプト値はカードID）

    // --- その他 ---
    MUSHROOM_ACTION,       // ご乱心中のランダム行動（スクリプト値は ActionType）
    MORTAR_VICTIM,         // あぶないウス所持者のうち99被弾する側
    PESTLE_TARGET,         // あぶないキネの対象（生存プレイヤーから抽選）

    // --- 手札スロットの選択（順序系: 先頭に来るスロットを指定する） ---
    DISCARD_RANDOM_ORDER,  // 夜のほうき・女神の石けん等のランダム破棄
    DISCARD_ONE_SLOT,      // 手札満杯で祈った際に捨てる1枚
    REVEAL_SLOT,           // 相手に公開されるスロット
    HAND_REPLACE_SLOT,     // 手札満杯時に上書きされるスロット

    // --- 地球神の行動 ---
    EARTH_DISCARD_SLOT,    // 地球神のドローで手札満杯時に上書きされるスロット
    EARTH_EXCHANGE_HP,     // 地球神の両替で決まるHP
    EARTH_EXCHANGE_MP,     // 地球神の両替で決まるMP
    EARTH_SELL_SLOT,       // 地球神が出品するスロット

    COUNT
};

constexpr int NUM_ROLL_KINDS = static_cast<int>(RollKind::COUNT);

// テスト側が「範囲の下限／上限」を指示するためのセンチネル。
// 閾値の向き（roll < RATE で成功か、roll >= accuracy で失敗か）を
// 個々のテストコードに書かせないために使う。
constexpr int ROLL_MIN = INT32_MIN;
constexpr int ROLL_MAX = INT32_MAX;

/**
 * @brief テストが仕込む乱数の指示表。本番では生成されない。
 *
 * 値系（roll_range）と順序系（shuffle_by_*）でセマンティクスが異なる:
 *  - 値系: queue。force() は最後の値を繰り返す sticky、script() はちょうどその回数だけ。
 *  - 順序系: 優先リスト。そのラベルのシャッフルすべてに適用され、消費されない。
 */
struct RollScript {
    // --- 値系 ---
    std::vector<int> values[NUM_ROLL_KINDS];
    int cursor[NUM_ROLL_KINDS] = {};
    bool sticky[NUM_ROLL_KINDS] = {};

    // --- 順序系 ---
    std::vector<int> order[NUM_ROLL_KINDS];
    bool order_set[NUM_ROLL_KINDS] = {};

    // --- 診断用 ---
    int consumed[NUM_ROLL_KINDS] = {}; // そのラベルが実際に何回転がったか
    // 「検証対象ではなく、局面を決定的にするための背景固定」であることの印。
    // 手札補充のドローのように、起きるかどうかがテストの主題でない指示に付ける。
    // 未消費検査（rng_unconsumed_kinds）の対象外になる。
    bool optional[NUM_ROLL_KINDS] = {};
    bool forbid_unscripted = false;    // 指示のない乱数消費を例外にする（運に依存しないことの証明用）
};

// 本番は常に nullptr。テストのみメインスレッドで設定される。
extern thread_local RollScript *g_roll_script;

const char *roll_kind_name(RollKind kind);

// 実体は rng.cpp。ホットパスからは追い出してインライン展開を小さく保つ。
int roll_range_scripted(InternalState &state, RollKind kind, int lo, int hi);
int scripted_card_id(RollKind kind, bool &found);
bool scripted_order(RollKind kind, const std::vector<int> **out);
void note_unscripted(RollKind kind);

// テスト側のコントローラ（bindings.cpp から使用）。本番コードからは呼ばれない。
RollScript &install_test_script();
void reset_test_script();

/**
 * @brief [lo, hi] の一様整数を引きます。テストがそのラベルを指示していればその値を返します。
 */
inline int roll_range(InternalState &state, RollKind kind, int lo, int hi) {
    if (g_roll_script != nullptr) {
        return roll_range_scripted(state, kind, lo, hi);
    }
    return std::uniform_int_distribution<int>(lo, hi)(state.rng);
}

/**
 * @brief 候補リストをシャッフルします。呼び出し側は結果の先頭から順に使うことを想定しています。
 *
 * テストが pick_order() でスロット番号を指示している場合、その順に先頭へ並べ、
 * 残りは候補の元の順序（昇順）を保ちます。残りを実シャッフルしないのは、
 * 指示済みテストを完全に決定的にするためです。
 *
 * @param candidates 手札スロット番号などの候補リスト。値そのもので指示する。
 */
inline void shuffle_by_value(InternalState &state, RollKind kind, std::vector<int> &candidates) {
    if (g_roll_script != nullptr) {
        const std::vector<int> *wanted = nullptr;
        if (scripted_order(kind, &wanted)) {
            size_t front = 0;
            for (int val : *wanted) {
                if (front >= candidates.size()) break;
                auto it = std::find(candidates.begin() + front, candidates.end(), val);
                // 指示された値が候補に無いのは、前回の解決で既に消えた等の正常なケースもあるため
                // エラーにはせず読み飛ばす。1度も転がらなかった指示は teardown 側で検出する。
                if (it == candidates.end()) continue;
                std::iter_swap(candidates.begin() + front, it);
                ++front;
            }
            return;
        }
        note_unscripted(kind);
    }
    std::shuffle(candidates.begin(), candidates.end(), state.rng);
}

/**
 * @brief 任意要素の配列をシャッフルします。値で指示できないため元インデックスの順列で指示します。
 *
 * 磁気嵐（手札の相互交換）だけが使用します。
 */
template <class T>
inline void shuffle_by_index(InternalState &state, RollKind kind, std::vector<T> &items) {
    if (g_roll_script != nullptr) {
        const std::vector<int> *perm = nullptr;
        if (scripted_order(kind, &perm)) {
            std::vector<T> reordered;
            reordered.reserve(items.size());
            std::vector<bool> taken(items.size(), false);
            for (int idx : *perm) {
                if (idx < 0 || idx >= static_cast<int>(items.size()) || taken[idx]) continue;
                reordered.push_back(items[idx]);
                taken[idx] = true;
            }
            for (size_t i = 0; i < items.size(); ++i) {
                if (!taken[i]) reordered.push_back(items[i]);
            }
            items.swap(reordered);
            return;
        }
        note_unscripted(kind);
    }
    std::shuffle(items.begin(), items.end(), state.rng);
}
