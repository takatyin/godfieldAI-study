#include "rng.h"
#include <stdexcept>
#include <string>

// 本番（学習時）は常に nullptr。テストのみメインスレッドで設定される。
thread_local RollScript *g_roll_script = nullptr;

// ============================================================================
// ラベル名テーブル / Roll kind names
// ============================================================================
// エラーメッセージで「どの判定が枯渇したのか」「どの判定が指示されていないのか」を
// そのまま出せるようにする。enum を増やして名前を足し忘れるとコンパイルエラーになる。

static const char *const kRollKindNames[] = {
    "ACCURACY",
    "BOUNCE",
    "MARS_RING",
    "GUARDIAN_LEAVE",
    "ASCENSION_BOW_HIT",
    "SICKNESS_WORSEN",
    "GUARDIAN_ACT",
    "GUARDIAN_ACT_CHOICE",
    "MOON_MIRACLE",
    "PHENOMENON",
    "PHENOMENON_TUB_TARGET",
    "PHENOMENON_GOLD_MINE",
    "PHENOMENON_ECLIPSE_G0",
    "PHENOMENON_ECLIPSE_G1",
    "PHENOMENON_MAGNETIC_STORM",
    "GUARDIAN_POT",
    "THUMP_THUMP_TEAR",
    "DEVIL_FAIRY",
    "DEVIL_PRANKSTER",
    "DECK_DRAW",
    "APOCALYPSE_DRAW",
    "DREAM_DISGUISE",
    "DREAM_FAKE_CARD",
    "MUSHROOM_ACTION",
    "MORTAR_VICTIM",
    "PESTLE_TARGET",
    "DISCARD_RANDOM_ORDER",
    "DISCARD_ONE_SLOT",
    "REVEAL_SLOT",
    "HAND_REPLACE_SLOT",
    "EARTH_DISCARD_SLOT",
    "EARTH_EXCHANGE_HP",
    "EARTH_EXCHANGE_MP",
    "EARTH_SELL_SLOT",
};

static_assert(sizeof(kRollKindNames) / sizeof(kRollKindNames[0]) == NUM_ROLL_KINDS,
              "RollKind の要素数と kRollKindNames の要素数が一致していません");

const char *roll_kind_name(RollKind kind) {
    int idx = static_cast<int>(kind);
    if (idx < 0 || idx >= NUM_ROLL_KINDS) return "<unknown>";
    return kRollKindNames[idx];
}

// ============================================================================
// 値系スクリプトの取り出し / Scripted value queue
// ============================================================================

/**
 * @brief そのラベルに指示された次の値を取り出します。
 * @return 指示があれば true。指示が無ければ false（呼び出し側が実際の乱数へ委譲する）。
 * @throw std::runtime_error script() で与えた回数を超えて転がされた場合。
 */
static bool next_scripted_value(RollKind kind, int &out) {
    RollScript &s = *g_roll_script;
    int idx = static_cast<int>(kind);
    const std::vector<int> &vals = s.values[idx];
    if (vals.empty()) return false;

    if (s.cursor[idx] < static_cast<int>(vals.size())) {
        out = vals[s.cursor[idx]++];
        return true;
    }
    if (s.sticky[idx]) {
        out = vals.back();
        return true;
    }
    throw std::runtime_error(
        std::string("RollKind::") + roll_kind_name(kind) + " のスクリプトが枯渇しました: " +
        std::to_string(vals.size()) + " 個を指定しましたが、それより多く判定が行われました。" +
        "回数が想定と異なる場合は script() の要素数を見直すか、force() で固定してください。");
}

void note_unscripted(RollKind kind) {
    RollScript &s = *g_roll_script;
    s.consumed[static_cast<int>(kind)]++;
    if (s.forbid_unscripted) {
        throw std::runtime_error(
            std::string("RollKind::") + roll_kind_name(kind) +
            " が指示なしで転がされました。forbid_unscripted() を指定したテストは"
            "すべての乱数を明示しなければなりません。");
    }
}

/**
 * @brief センチネル（ROLL_MIN / ROLL_MAX）を実際の範囲へ解決し、範囲外指定を弾きます。
 */
static int resolve_sentinel(RollKind kind, int value, int lo, int hi) {
    if (value == ROLL_MIN) return lo;
    if (value == ROLL_MAX) return hi;
    if (value < lo || value > hi) {
        throw std::runtime_error(
            std::string("RollKind::") + roll_kind_name(kind) + " に範囲外の値 " +
            std::to_string(value) + " が指定されました（有効範囲は " + std::to_string(lo) +
            "..." + std::to_string(hi) + "）。実装側の範囲が変わった可能性があります。");
    }
    return value;
}

int roll_range_scripted(InternalState &state, RollKind kind, int lo, int hi) {
    int value = 0;
    if (next_scripted_value(kind, value)) {
        g_roll_script->consumed[static_cast<int>(kind)]++;
        return resolve_sentinel(kind, value, lo, hi);
    }
    note_unscripted(kind);
    return std::uniform_int_distribution<int>(lo, hi)(state.rng);
}

int scripted_card_id(RollKind kind, bool &found) {
    int value = 0;
    if (next_scripted_value(kind, value)) {
        g_roll_script->consumed[static_cast<int>(kind)]++;
        found = true;
        return value;
    }
    note_unscripted(kind);
    found = false;
    return CARD_EMPTY;
}

bool scripted_order(RollKind kind, const std::vector<int> **out) {
    RollScript &s = *g_roll_script;
    int idx = static_cast<int>(kind);
    if (!s.order_set[idx]) return false;
    s.consumed[idx]++;
    *out = &s.order[idx];
    return true;
}

// ============================================================================
// テスト側のコントローラ / Test-side controller
// ============================================================================
// pybind11 から叩くための単一インスタンス。テストはメインスレッドから操作する。

static RollScript g_test_script;

RollScript &install_test_script() {
    g_roll_script = &g_test_script;
    return g_test_script;
}

void reset_test_script() {
    g_test_script = RollScript();
    g_roll_script = nullptr;
}
