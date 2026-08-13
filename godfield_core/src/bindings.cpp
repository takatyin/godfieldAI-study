#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/numpy.h>
#include <cstddef>
#include <stdexcept>
#include <string>
#include <vector>
#include "env_pool.h"
#include "game_logic.h"
#include "game_logic_internal.h"
#include "ismcts.h"
#include "rng.h"
#include "types.h"

namespace py = pybind11;

template <typename T, size_t N>
py::list get_array_as_list(const T(&arr)[N]) {
    py::list res;
    for (size_t i = 0; i < N; ++i) {
        res.append(arr[i]);
    }
    return res;
}

PYBIND11_MODULE(godfield_core, m) {
    m.doc() = "GodField core engine and RL environment pool";

    m.attr("OBSERVATION_SIZE") = sizeof(Observation) / sizeof(float);
    // InternalState は環境の数だけ並ぶ（学習時は1024環境）ので、大きさがそのまま
    // キャッシュ効率に効く。意図せず膨らんでいないかテストから確認できるように公開する。
    m.attr("INTERNAL_STATE_SIZE") = static_cast<int>(sizeof(InternalState));
    m.attr("OBSERVATION_FEATURE_SIZE") = (offsetof(Observation, action_mask) + sizeof(decltype(Observation::action_mask))) / sizeof(float);
    // 観測配列のどこから合法手マスクが始まるかを決めるため、Python 側はこの値を参照すること。
    // 定数をコピーすると行動空間の拡張時に黙ってズレる。
    m.attr("ACTION_SPACE_SIZE") = ACTION_SPACE_SIZE;
    m.attr("MAX_HAND_SIZE") = MAX_HAND_SIZE;
    m.attr("HISTORY_LENGTH") = HISTORY_LENGTH;

    // 観測ベクトルの各ブロックの長さ。Python 側（feature_config.py）は
    // オフセット表をこれらから組み立てる。値をコピーすると、種別が1つ増えた
    // だけで以降のスライス位置が全部ズレ、例外も出ずに学習だけが壊れる。
    m.attr("NUM_SICKNESS_TYPES") = NUM_SICKNESS_TYPES;
    m.attr("NUM_CURSE_TYPES") = NUM_CURSE_TYPES;
    m.attr("NUM_GUARDIAN_TYPES") = NUM_GUARDIAN_TYPES;
    m.attr("NUM_PHASES") = NUM_PHASES;
    // GameEvent 1件が観測上で占める float 数。
    m.attr("EVENT_SIZE") = static_cast<int>(sizeof(GameEvent) / sizeof(float));

    // Bind initialization function
    m.def("init_game_logic", &init_game_logic, "Initialize the global card registry from JSON");
    m.def("get_registry_size", &get_registry_size, "Get number of cards in registry");
    m.def("draw_card", &draw_card, py::arg("state"),
          "山札から1枚抽選してカードIDを返します。抽選分布そのものを検証するために公開しています"
          "（テストが next_draws() で指示している場合はその値が返ります）。");
    m.def("get_draw_table_size", []() { return g_draw_table.size(); },
          "抽選テーブルの要素数（drop_rate の重みの総和）。");
    m.def("get_card_name", &get_card_name, "Get card name by ID");

    // Bind enums
    py::enum_<Element>(m, "Element")
        .value("ELEM_NONE", ELEM_NONE)
        .value("ELEM_FIRE", ELEM_FIRE)
        .value("ELEM_WATER", ELEM_WATER)
        .value("ELEM_WOOD", ELEM_WOOD)
        .value("ELEM_STONE", ELEM_STONE)
        .value("ELEM_LIGHT", ELEM_LIGHT)
        .value("ELEM_DARKNESS", ELEM_DARKNESS)
        .export_values();

    py::enum_<ReactionType>(m, "ReactionType")
        .value("REACTION_NONE", REACTION_NONE)
        .value("REACTION_BOUNCE", REACTION_BOUNCE)
        .value("REACTION_REFLECT", REACTION_REFLECT)
        .value("REACTION_BLOCK", REACTION_BLOCK)
        .export_values();

    py::enum_<HitCurse>(m, "HitCurse")
        .value("CURSE_NONE", CURSE_NONE)
        .value("CURSE_FOG", CURSE_FOG)
        .value("CURSE_FLASH", CURSE_FLASH)
        .value("CURSE_DARK_CLOUD", CURSE_DARK_CLOUD)
        .value("CURSE_DREAM", CURSE_DREAM)
        .value("CURSE_COLD", CURSE_COLD)
        .value("CURSE_FEVER", CURSE_FEVER)
        .value("CURSE_HELL", CURSE_HELL)
        .value("CURSE_HEAVEN", CURSE_HEAVEN)
        .export_values();

    py::enum_<SicknessType>(m, "SicknessType")
        .value("SICKNESS_NONE", SicknessType::SICKNESS_NONE)
        .value("SICKNESS_COLD", SicknessType::SICKNESS_COLD)
        .value("SICKNESS_FEVER", SicknessType::SICKNESS_FEVER)
        .value("SICKNESS_HELL", SicknessType::SICKNESS_HELL)
        .value("SICKNESS_HEAVEN", SicknessType::SICKNESS_HEAVEN)
        .export_values();

    py::enum_<CurseType>(m, "CurseType")
        .value("CURSE_FOG", CurseType::CURSE_TYPE_FOG)
        .value("CURSE_FLASH", CurseType::CURSE_TYPE_FLASH)
        .value("CURSE_DARK_CLOUD", CurseType::CURSE_TYPE_DARK_CLOUD)
        .value("CURSE_DREAM", CurseType::CURSE_TYPE_DREAM)
        .export_values();

    py::enum_<GuardianType>(m, "GuardianType")
        .value("NONE", GUARDIAN_NONE)
        .value("MARS", GUARDIAN_MARS)
        .value("MERCURY", GUARDIAN_MERCURY)
        .value("JUPITER", GUARDIAN_JUPITER)
        .value("SATURN", GUARDIAN_SATURN)
        .value("URANUS", GUARDIAN_URANUS)
        .value("PLUTO", GUARDIAN_PLUTO)
        .value("NEPTUNE", GUARDIAN_NEPTUNE)
        .value("VENUS", GUARDIAN_VENUS)
        .value("EARTH", GUARDIAN_EARTH)
        .value("MOON", GUARDIAN_MOON)
        .export_values();

    py::enum_<PhenomenonType>(m, "PhenomenonType")
        .value("SUNSET", PHENOMENON_SUNSET)
        .value("DENSE_FOG", PHENOMENON_DENSE_FOG)
        .value("MUSHROOM", PHENOMENON_MUSHROOM)
        .value("TORNADO", PHENOMENON_TORNADO)
        .value("GIGANTIC_TUB", PHENOMENON_GIGANTIC_TUB)
        .value("BLACK_HOLE", PHENOMENON_BLACK_HOLE)
        .value("WARM_CURRENT", PHENOMENON_WARM_CURRENT)
        .value("GOLD_MINE", PHENOMENON_GOLD_MINE)
        .value("MAGNETIC_STORM", PHENOMENON_MAGNETIC_STORM)
        .value("ECLIPSE", PHENOMENON_ECLIPSE)
        .export_values();


    // Export Timing bitmasks
    m.attr("TIMING_MAIN_ATK") = TIMING_MAIN_ATK;
    m.attr("TIMING_MAIN_MIRACLE") = TIMING_MAIN_MIRACLE;
    m.attr("TIMING_MAIN_SUNDRY") = TIMING_MAIN_SUNDRY;
    m.attr("TIMING_MAIN_DEAL") = TIMING_MAIN_DEAL;
    m.attr("TIMING_ATK_PLUS") = TIMING_ATK_PLUS;
    m.attr("TIMING_MIRACLE_PLUS") = TIMING_MIRACLE_PLUS;
    m.attr("TIMING_ATK_DEFENCE") = TIMING_ATK_DEFENCE;
    m.attr("TIMING_MIRACLE_DEFENCE") = TIMING_MIRACLE_DEFENCE;

    py::enum_<GamePhase>(m, "GamePhase")
        .value("PHASE_GUARDIAN", GamePhase::PHASE_GUARDIAN)
        .value("PHASE_MAIN", GamePhase::PHASE_MAIN)
        .value("PHASE_MAIN_TARGET_SELECT", GamePhase::PHASE_MAIN_TARGET_SELECT)
        .value("PHASE_ATTACK_PLUS", GamePhase::PHASE_ATTACK_PLUS)
        .value("PHASE_GROUP_WEAPON", GamePhase::PHASE_GROUP_WEAPON)
        .value("PHASE_MIRACLE_PLUS", GamePhase::PHASE_MIRACLE_PLUS)
        .value("PHASE_GROUP_MIRACLE_PLUS", GamePhase::PHASE_GROUP_MIRACLE_PLUS)
        .value("PHASE_DEFENSE", GamePhase::PHASE_DEFENSE)
        .value("PHASE_MIRACLE_DEFENSE", GamePhase::PHASE_MIRACLE_DEFENSE)
        .value("PHASE_SELL_SELECT", GamePhase::PHASE_SELL_SELECT)
        .value("PHASE_SELL_SELECT_MIRROR", GamePhase::PHASE_SELL_SELECT_MIRROR)
        .value("PHASE_BUY_SELECT_MIRROR", GamePhase::PHASE_BUY_SELECT_MIRROR)
        .value("PHASE_SUNDRY_SELECT_MIRROR", GamePhase::PHASE_SUNDRY_SELECT_MIRROR)
        .value("PHASE_BUY", GamePhase::PHASE_BUY)
        .value("PHASE_EXCHANGE_HP", GamePhase::PHASE_EXCHANGE_HP)
        .value("PHASE_EXCHANGE_MP", GamePhase::PHASE_EXCHANGE_MP)
        .value("PHASE_DISCARD", GamePhase::PHASE_DISCARD)
        .value("PHASE_END", GamePhase::PHASE_END)
        .export_values();

    py::enum_<TurnEndSubstep>(m, "TurnEndSubstep")
        .value("DEATH_CHECK_START", TurnEndSubstep::DEATH_CHECK_START)
        .value("SICKNESS_WORSEN", TurnEndSubstep::SICKNESS_WORSEN)
        .value("SICKNESS_DAMAGE", TurnEndSubstep::SICKNESS_DAMAGE)
        .value("FINAL_DEATH_CHECK", TurnEndSubstep::FINAL_DEATH_CHECK)
        .value("GUARDIAN_ACT", TurnEndSubstep::GUARDIAN_ACT)
        .value("CLEANUP_DEATH_CHECK", TurnEndSubstep::CLEANUP_DEATH_CHECK)
        .value("CLEANUP", TurnEndSubstep::CLEANUP)
        .value("TURN_TRANSITION", TurnEndSubstep::TURN_TRANSITION)
        .export_values();

    auto action_enum = py::enum_<ActionType>(m, "ActionType")
        .value("ACTION_SELECT_HAND_0", ActionType::ACTION_SELECT_HAND_0)
        .value("ACTION_SELECT_HAND_1", ActionType::ACTION_SELECT_HAND_1)
        .value("ACTION_SELECT_HAND_2", ActionType::ACTION_SELECT_HAND_2)
        .value("ACTION_SELECT_HAND_3", ActionType::ACTION_SELECT_HAND_3)
        .value("ACTION_SELECT_HAND_4", ActionType::ACTION_SELECT_HAND_4)
        .value("ACTION_SELECT_HAND_5", ActionType::ACTION_SELECT_HAND_5)
        .value("ACTION_SELECT_HAND_6", ActionType::ACTION_SELECT_HAND_6)
        .value("ACTION_SELECT_HAND_7", ActionType::ACTION_SELECT_HAND_7)
        .value("ACTION_SELECT_HAND_8", ActionType::ACTION_SELECT_HAND_8)
        .value("ACTION_SELECT_HAND_9", ActionType::ACTION_SELECT_HAND_9)
        .value("ACTION_SELECT_HAND_10", ActionType::ACTION_SELECT_HAND_10)
        .value("ACTION_SELECT_HAND_11", ActionType::ACTION_SELECT_HAND_11)
        .value("ACTION_SELECT_HAND_12", ActionType::ACTION_SELECT_HAND_12)
        .value("ACTION_SELECT_HAND_13", ActionType::ACTION_SELECT_HAND_13)
        .value("ACTION_SELECT_HAND_14", ActionType::ACTION_SELECT_HAND_14)
        .value("ACTION_SELECT_HAND_15", ActionType::ACTION_SELECT_HAND_15)
        .value("ACTION_SELECT_HAND_16", ActionType::ACTION_SELECT_HAND_16)
        .value("ACTION_SELECT_HAND_17", ActionType::ACTION_SELECT_HAND_17)
        .value("ACTION_TARGET_OPP", ActionType::ACTION_TARGET_OPP)
        .value("ACTION_DEAL_YES", ActionType::ACTION_DEAL_YES)
        .value("ACTION_TARGET_SELF", ActionType::ACTION_TARGET_SELF)
        .value("ACTION_DEAL_NO", ActionType::ACTION_DEAL_NO)
        .value("ACTION_CONFIRM", ActionType::ACTION_CONFIRM)
        .value("ACTION_PRAY", ActionType::ACTION_PRAY)
        .value("ACTION_DISCARD", ActionType::ACTION_DISCARD);

    for (int i = 0; i <= 99; ++i) {
        std::string name = "ACTION_NUM_" + std::to_string(i);
        action_enum.value(name.c_str(), static_cast<ActionType>(static_cast<int>(ActionType::ACTION_NUM_0) + i));
    }
    action_enum.export_values();

    m.attr("CARD_EMPTY") = CARD_EMPTY;

    // ========================================================================
    // 乱数注入（テスト専用） / Deterministic RNG injection for tests
    // ========================================================================
    // 確率で分岐するロジックを「シード総当たり探索」ではなく宣言的にテストするための API。
    // 本番（学習時）はこれらを一切呼ばないため、g_roll_script は nullptr のままになる。
    // 直接叩くのではなく tests/core/dsl.py の RngController 経由で使うこと。

    py::enum_<RollKind>(m, "RollKind", "乱数消費点のラベル。どの確率判定を指示するかを表す。")
        .value("ACCURACY", RollKind::ACCURACY)
        .value("BOUNCE", RollKind::BOUNCE)
        .value("MARS_RING", RollKind::MARS_RING)
        .value("GUARDIAN_LEAVE", RollKind::GUARDIAN_LEAVE)
        .value("ASCENSION_BOW_HIT", RollKind::ASCENSION_BOW_HIT)
        .value("SICKNESS_WORSEN", RollKind::SICKNESS_WORSEN)
        .value("GUARDIAN_ACT", RollKind::GUARDIAN_ACT)
        .value("GUARDIAN_ACT_CHOICE", RollKind::GUARDIAN_ACT_CHOICE)
        .value("MOON_MIRACLE", RollKind::MOON_MIRACLE)
        .value("PHENOMENON", RollKind::PHENOMENON)
        .value("PHENOMENON_TUB_TARGET", RollKind::PHENOMENON_TUB_TARGET)
        .value("PHENOMENON_GOLD_MINE", RollKind::PHENOMENON_GOLD_MINE)
        .value("PHENOMENON_ECLIPSE_G0", RollKind::PHENOMENON_ECLIPSE_G0)
        .value("PHENOMENON_ECLIPSE_G1", RollKind::PHENOMENON_ECLIPSE_G1)
        .value("PHENOMENON_MAGNETIC_STORM", RollKind::PHENOMENON_MAGNETIC_STORM)
        .value("GUARDIAN_POT", RollKind::GUARDIAN_POT)
        .value("THUMP_THUMP_TEAR", RollKind::THUMP_THUMP_TEAR)
        .value("DEVIL_FAIRY", RollKind::DEVIL_FAIRY)
        .value("DEVIL_PRANKSTER", RollKind::DEVIL_PRANKSTER)
        .value("DECK_DRAW", RollKind::DECK_DRAW)
        .value("APOCALYPSE_DRAW", RollKind::APOCALYPSE_DRAW)
        .value("DREAM_DISGUISE", RollKind::DREAM_DISGUISE)
        .value("DREAM_FAKE_CARD", RollKind::DREAM_FAKE_CARD)
        .value("MUSHROOM_ACTION", RollKind::MUSHROOM_ACTION)
        .value("MORTAR_VICTIM", RollKind::MORTAR_VICTIM)
        .value("PESTLE_TARGET", RollKind::PESTLE_TARGET)
        .value("DISCARD_RANDOM_ORDER", RollKind::DISCARD_RANDOM_ORDER)
        .value("DISCARD_ONE_SLOT", RollKind::DISCARD_ONE_SLOT)
        .value("REVEAL_SLOT", RollKind::REVEAL_SLOT)
        .value("HAND_REPLACE_SLOT", RollKind::HAND_REPLACE_SLOT)
        .value("EARTH_DISCARD_SLOT", RollKind::EARTH_DISCARD_SLOT)
        .value("EARTH_EXCHANGE_HP", RollKind::EARTH_EXCHANGE_HP)
        .value("EARTH_EXCHANGE_MP", RollKind::EARTH_EXCHANGE_MP)
        .value("EARTH_SELL_SLOT", RollKind::EARTH_SELL_SLOT);

    // 「範囲の下限／上限」を指示するセンチネル。閾値の向きをテストに書かせないために使う。
    m.attr("ROLL_MIN") = ROLL_MIN;
    m.attr("ROLL_MAX") = ROLL_MAX;
    // 守護神の行動選択の累積閾値。テスト側が「行動Nを狙う代表値」を導出するのに使う。
    m.def("get_guardian_action_percents", &get_guardian_action_percents,
          "守護神の5行動それぞれが選ばれる確率（%）。並びは get_guardian_action_cards() と対応する。"
          "テストはこの表から「行動 N を狙う代表値」を導出するため、確率をここ以外に書かないこと。");

    m.def(
        "rng_clear_script", &reset_test_script,
        "仕込んだ指示をすべて破棄し、本番と同じ挙動に戻します（各テストの終わりに必ず呼ぶ）。");

    m.def(
        "rng_force", [](RollKind kind, int value, bool optional) {
            RollScript &s = install_test_script();
            int idx = static_cast<int>(kind);
            s.values[idx] = {value};
            s.cursor[idx] = 0;
            s.sticky[idx] = true;
            s.optional[idx] = optional;
        },
        py::arg("kind"), py::arg("value"), py::arg("optional") = false,
        "以後その判定が常に value を返すようにします（回数は問わない）。"
        "optional=True にすると未消費検査の対象外になります"
        "（手札補充のように、起きるかどうかがテストの主題でない背景固定に使う）。");

    m.def(
        "rng_script", [](RollKind kind, const std::vector<int> &values, bool repeat_last) {
            if (values.empty()) throw std::invalid_argument("rng_script: 値が空です");
            RollScript &s = install_test_script();
            int idx = static_cast<int>(kind);
            s.values[idx] = values;
            s.cursor[idx] = 0;
            s.sticky[idx] = repeat_last;
        },
        py::arg("kind"), py::arg("values"), py::arg("repeat_last") = false,
        "その判定がちょうどこの順で values 回だけ行われることを指示します。"
        "回数を超えて判定されると例外になります。"
        "repeat_last=True にすると、使い切った後は最後の値を繰り返します"
        "（先頭数回だけ意味を持たせ、残りは無害な値で埋めたい場合に使う）。");

    m.def("get_guardian_action_cards", &get_guardian_action_cards, py::arg("guardian"),
          "指定した守護神の5行動に対応するカードID一覧（攻撃系6神と海王神のみ。他は空）。"
          "テストは行動カード名からこの並びのインデックスを逆引きして "
          "RollKind::GUARDIAN_ACT_CHOICE に指示します。");

    m.attr("APOCALYPSE_TURN") = APOCALYPSE_TURN;
    m.def("get_apocalypse_devils", &get_apocalypse_devils,
          "終末の時のドローで出る悪魔カードID一覧。"
          "テストは悪魔名からこの並びのインデックスを逆引きして"
          "RollKind::APOCALYPSE_DRAW に指示します。");

    m.def("get_apocalypse_devil_percents", &get_apocalypse_devil_percents,
          "各悪魔カードの出現率（%）。並びは get_apocalypse_devils() と対応する。"
          "合計に満たない残りは通常の山札抽選になる。");

    m.def("get_absorption_sources", &get_absorption_sources,
          "HP吸収（与えたダメージ分だけ攻撃側が回復する）を持つカードID一覧。"
          "テストが全種を網羅するために公開しています。");

    m.def("get_spiritual_zero_mp_cards", &get_spiritual_zero_mp_cards,
          "精霊系（直前の奇跡の消費MPを0にする）カードID一覧。"
          "テストが全種を網羅するために公開しています。");

    m.attr("DREAM_DISGUISE_RATE") = DREAM_DISGUISE_RATE;
    m.attr("SAW_BOOM_BOOM_ATTACK_COUNT") = SAW_BOOM_BOOM_ATTACK_COUNT;
    m.attr("SUN_AMULET_REVIVE_HP") = SUN_AMULET_REVIVE_HP;
    m.attr("ASCENSION_BOW_TRIGGERED_POWER") = ASCENSION_BOW_TRIGGERED_POWER;
    m.def("get_dream_candidates", &get_dream_candidates, py::arg("card_id"),
          "夢状態でそのカードが偽装されうる相手のカードID一覧（自分自身は含まない）。"
          "テストは偽装先のカード名からこの並びのインデックスを逆引きして "
          "RollKind::DREAM_FAKE_CARD に指示します。");

    m.def("get_moon_miracles", &get_moon_miracles,
          "月神が発動しうる奇跡のカードID一覧。テストは奇跡名からこの並びの"
          "インデックスを逆引きして RollKind::MOON_MIRACLE に指示します。");

    m.def(
        "rng_pick_order", [](RollKind kind, const std::vector<int> &preferred) {
            RollScript &s = install_test_script();
            int idx = static_cast<int>(kind);
            s.order[idx] = preferred;
            s.order_set[idx] = true;
        },
        py::arg("kind"), py::arg("preferred"),
        "シャッフル系の判定で、指定した値（手札スロット番号など）を先頭から順に並べます。"
        "残りは候補の元の順序を保つため、指示済みテストは完全に決定的になります。");

    m.def(
        "rng_forbid_unscripted", [](bool forbid) {
            install_test_script().forbid_unscripted = forbid;
        },
        py::arg("forbid") = true,
        "指示のない乱数消費が起きた時点で例外にします。"
        "そのテストが運に一切依存しないことを機械的に証明できます。");

    m.def(
        "rng_consumed", [](RollKind kind) {
            return g_roll_script == nullptr ? 0 : g_roll_script->consumed[static_cast<int>(kind)];
        },
        py::arg("kind"), "その判定が実際に何回行われたかを返します。");

    m.def(
        "rng_unconsumed_kinds", []() -> py::list {
            py::list result;
            if (g_roll_script == nullptr) return result;
            const RollScript &s = *g_roll_script;
            for (int i = 0; i < NUM_ROLL_KINDS; ++i) {
                // 背景固定として指示されたものは、使われなくても問題にしない
                if (s.optional[i]) continue;
                // 値系の判定基準は sticky かどうかで変わる。
                //  - sticky（force / repeat_last=True）: 末尾は繰り返し用なので使い残して当然。
                //    「1度も使われなかった」ときだけ指示が空振りしたと見なす。
                //  - 非sticky（script）: 宣言した回数ぶん必ず使われるべきなので、使い残しは異常。
                bool value_left =
                    !s.values[i].empty() &&
                    (s.sticky[i] ? s.cursor[i] == 0
                                 : s.cursor[i] < static_cast<int>(s.values[i].size()));
                // 順序系: 指示したのに1度もシャッフルされなかった
                bool order_unused = s.order_set[i] && s.consumed[i] == 0;
                if (value_left || order_unused) {
                    result.append(std::string(roll_kind_name(static_cast<RollKind>(i))));
                }
            }
            return result;
        },
        "指示したのに使われなかった判定の名前一覧を返します。"
        "空でなければ、テストが意図したコードパスが実行されていません。");

    // Bind InternalState
    py::class_<InternalState>(m, "InternalState")
        .def(py::init<>())
        .def("seed_rng", [](InternalState &s, unsigned int seed) { s.rng.seed(seed); }, py::arg("seed"))
        .def_readwrite("current_actor_id", &InternalState::current_actor_id)
        .def_readwrite("current_turn", &InternalState::current_turn)
        .def_readwrite("mushroom_turns", &InternalState::mushroom_turns)
        .def_readwrite("current_phase", &InternalState::current_phase)
        .def_readwrite("is_done", &InternalState::is_done)
        .def_readwrite("p0_reward", &InternalState::p0_reward)
        .def_readwrite("p1_reward", &InternalState::p1_reward)
        .def_readwrite("history_count", &InternalState::history_count)
        .def_readwrite("attacker_id", &InternalState::attacker_id)
        .def_readwrite("defender_id", &InternalState::defender_id)
        .def_readwrite("pending_attack_power", &InternalState::pending_attack_power)
        .def_readwrite("pending_attack_element", &InternalState::pending_attack_element)
        .def_readwrite("pending_defense_power", &InternalState::pending_defense_power)
        .def_readwrite("pending_absorption", &InternalState::pending_absorption)
        .def_readwrite("pending_deal_same_damage", &InternalState::pending_deal_same_damage)
        .def_readwrite("pending_is_group_attack", &InternalState::pending_is_group_attack)
        .def_readwrite("pending_initiator", &InternalState::pending_initiator)
        .def_readwrite("pending_attack_source_id", &InternalState::pending_attack_source_id)
        .def_readwrite("turn_end_state", &InternalState::turn_end_state)
        .def_readwrite("remaining_attacks", &InternalState::remaining_attacks)
        .def_readwrite("base_attack_power", &InternalState::base_attack_power)
        .def_readwrite("base_attack_element", &InternalState::base_attack_element)
        .def_readwrite("base_absorption", &InternalState::base_absorption)
        .def_readwrite("base_deal_same_damage", &InternalState::base_deal_same_damage)
        .def("get_pending_ascension_bows", [](InternalState &s, int p) { return s.pending_ascension_bows[p]; }, py::arg("player_id"))
        .def("set_pending_ascension_bows", [](InternalState &s, int p, int v) { s.pending_ascension_bows[p] = v; }, py::arg("player_id"), py::arg("val"))
        // For array members, pybind11 requires special handling to access by index from python.
        // For now, we will add helper methods to InternalState bindings to get/set these arrays.
        .def(
            "get_hp", [](InternalState &s, int p) {
                if (p < 0 || p >= 2) throw std::out_of_range("player_id must be 0 or 1");
                return s.hp[p];
            }, py::arg("player_id"))
        .def(
            "set_hp", [](InternalState &s, int p, int v) {
                if (p < 0 || p >= 2) throw std::out_of_range("player_id must be 0 or 1");
                s.hp[p] = v;
            }, py::arg("player_id"), py::arg("hp"))
        .def(
            "get_mp", [](InternalState &s, int p) {
                if (p < 0 || p >= 2) throw std::out_of_range("player_id must be 0 or 1");
                return s.mp[p];
            }, py::arg("player_id"))
        .def(
            "set_mp", [](InternalState &s, int p, int v) {
                if (p < 0 || p >= 2) throw std::out_of_range("player_id must be 0 or 1");
                s.mp[p] = v;
            }, py::arg("player_id"), py::arg("mp"))
        .def(
            "get_money", [](InternalState &s, int p) {
                if (p < 0 || p >= 2) throw std::out_of_range("player_id must be 0 or 1");
                return s.money[p];
            }, py::arg("player_id"))
        .def(
            "set_money", [](InternalState &s, int p, int v) {
                if (p < 0 || p >= 2) throw std::out_of_range("player_id must be 0 or 1");
                s.money[p] = v;
            }, py::arg("player_id"), py::arg("money"))
        .def(
            "get_true_hand", [](InternalState &s, int p, int idx) {
                if (p < 0 || p >= 2) throw std::out_of_range("player_id must be 0 or 1");
                if (idx < 0 || idx >= MAX_HAND_SIZE) throw std::out_of_range("hand index must be in [0, 17]");
                return s.true_hand[p][idx];
            }, py::arg("player_id"), py::arg("hand_idx"))
        .def(
            "set_true_hand", [](InternalState &s, int p, int idx, int v) {
                if (p < 0 || p >= 2) throw std::out_of_range("player_id must be 0 or 1");
                if (idx < 0 || idx >= MAX_HAND_SIZE) throw std::out_of_range("hand index must be in [0, 17]");
                s.true_hand[p][idx] = v;
                s.apparent_hand[p][idx] = v;
                s.is_confirmed[p][idx] = true;
            }, py::arg("player_id"), py::arg("hand_idx"), py::arg("card_id"))
        .def(
            "add_card_to_hand_slot", [](InternalState &s, int p, int idx, int card_id, bool is_drawn) {
                if (p < 0 || p >= 2) throw std::out_of_range("player_id must be 0 or 1");
                if (idx < 0 || idx >= MAX_HAND_SIZE) throw std::out_of_range("hand index must be in [0, 17]");
                add_card_to_hand_slot(s, p, idx, card_id, is_drawn);
            }, py::arg("player_id"), py::arg("hand_idx"), py::arg("card_id"), py::arg("is_drawn"))
        .def(
            "get_apparent_hand", [](InternalState &s, int p, int idx) {
                if (p < 0 || p >= 2) throw std::out_of_range("player_id must be 0 or 1");
                if (idx < 0 || idx >= MAX_HAND_SIZE) throw std::out_of_range("hand index must be in [0, 17]");
                return s.apparent_hand[p][idx];
            }, py::arg("player_id"), py::arg("hand_idx"))
        .def(
            "set_apparent_hand", [](InternalState &s, int p, int idx, int v) {
                if (p < 0 || p >= 2) throw std::out_of_range("player_id must be 0 or 1");
                if (idx < 0 || idx >= MAX_HAND_SIZE) throw std::out_of_range("hand index must be in [0, 17]");
                s.apparent_hand[p][idx] = v;
            }, py::arg("player_id"), py::arg("hand_idx"), py::arg("card_id"))
        .def(
            "get_is_confirmed", [](InternalState &s, int p, int idx) {
                if (p < 0 || p >= 2) throw std::out_of_range("player_id must be 0 or 1");
                if (idx < 0 || idx >= MAX_HAND_SIZE) throw std::out_of_range("hand index must be in [0, 17]");
                return s.is_confirmed[p][idx];
            }, py::arg("player_id"), py::arg("hand_idx"))
        .def(
            "set_is_confirmed", [](InternalState &s, int p, int idx, bool v) {
                if (p < 0 || p >= 2) throw std::out_of_range("player_id must be 0 or 1");
                if (idx < 0 || idx >= MAX_HAND_SIZE) throw std::out_of_range("hand index must be in [0, 17]");
                s.is_confirmed[p][idx] = v;
            }, py::arg("player_id"), py::arg("hand_idx"), py::arg("is_confirmed"))
        .def(
            "get_is_known_to_opp", [](InternalState &s, int p, int idx) {
                if (p < 0 || p >= 2) throw std::out_of_range("player_id must be 0 or 1");
                if (idx < 0 || idx >= MAX_HAND_SIZE) throw std::out_of_range("hand index must be in [0, 17]");
                return s.is_known_to_opp[p][idx];
            }, py::arg("player_id"), py::arg("hand_idx"))
        .def(
            "set_is_known_to_opp", [](InternalState &s, int p, int idx, bool v) {
                if (p < 0 || p >= 2) throw std::out_of_range("player_id must be 0 or 1");
                if (idx < 0 || idx >= MAX_HAND_SIZE) throw std::out_of_range("hand index must be in [0, 17]");
                s.is_known_to_opp[p][idx] = v;
            }, py::arg("player_id"), py::arg("hand_idx"), py::arg("is_known"))
        .def(
            "get_is_used", [](InternalState &s, int p, int idx) {
                if (p < 0 || p >= 2) throw std::out_of_range("player_id must be 0 or 1");
                if (idx < 0 || idx >= MAX_HAND_SIZE) throw std::out_of_range("hand index must be in [0, 17]");
                return s.is_used[p][idx];
            }, py::arg("player_id"), py::arg("hand_idx"))
        .def(
            "set_is_used", [](InternalState &s, int p, int idx, bool v) {
                if (p < 0 || p >= 2) throw std::out_of_range("player_id must be 0 or 1");
                if (idx < 0 || idx >= MAX_HAND_SIZE) throw std::out_of_range("hand index must be in [0, 17]");
                s.is_used[p][idx] = v;
            }, py::arg("player_id"), py::arg("hand_idx"), py::arg("is_used"))
        .def(
            "get_num_staged_cards", [](InternalState &s, int p) {
                if (p < 0 || p >= 2) throw std::out_of_range("player_id must be 0 or 1");
                return s.num_staged_cards[p];
            }, py::arg("player_id"))
        .def(
            "set_num_staged_cards", [](InternalState &s, int p, int v) {
                if (p < 0 || p >= 2) throw std::out_of_range("player_id must be 0 or 1");
                s.num_staged_cards[p] = v;
            }, py::arg("player_id"), py::arg("num"))
        .def(
            "get_staged_card", [](InternalState &s, int p, int idx) {
                if (p < 0 || p >= 2) throw std::out_of_range("player_id must be 0 or 1");
                if (idx < 0 || idx >= MAX_HAND_SIZE) throw std::out_of_range("staged index must be in [0, 17]");
                return s.staged_cards[p][idx].slot;
            }, py::arg("player_id"), py::arg("staged_idx"),
            "仮置きの i 番目が指す手札スロット。守護神由来の仮想カードなら -1。")
        .def(
            "get_staged_card_id", [](const InternalState &s, int p, int i) {
                if (p < 0 || p >= 2) throw std::out_of_range("player_id must be 0 or 1");
                return staged_card_id(s, p, i);
            }, py::arg("player_id"), py::arg("staged_idx"),
            "仮置きの i 番目が指すカードID。手札由来なら手札から解決し、仮想カードならそのID。")
        .def(
            "set_staged_card", [](InternalState &s, int p, int idx, int v) {
                if (p < 0 || p >= 2) throw std::out_of_range("player_id must be 0 or 1");
                if (idx < 0 || idx >= MAX_HAND_SIZE) throw std::out_of_range("staged index must be in [0, 17]");
                s.staged_cards[p][idx] = StagedEntry::from_hand(v);
            }, py::arg("player_id"), py::arg("staged_idx"), py::arg("val"))
        .def(
            "set_staged_virtual_card", [](InternalState &s, int p, int idx, int card_id) {
                if (p < 0 || p >= 2) throw std::out_of_range("player_id must be 0 or 1");
                if (idx < 0 || idx >= MAX_HAND_SIZE) throw std::out_of_range("staged index must be in [0, 17]");
                s.staged_cards[p][idx] = StagedEntry::virtual_of(card_id);
            }, py::arg("player_id"), py::arg("staged_idx"), py::arg("card_id"),
            "手札に無いカード（守護神由来）を仮置きに置きます。")
        .def(
            "get_is_deployed", [](InternalState &s, int p, int idx) {
                if (p < 0 || p >= 2) throw std::out_of_range("player_id must be 0 or 1");
                if (idx < 0 || idx >= MAX_HAND_SIZE) throw std::out_of_range("hand index must be in [0, 17]");
                return s.is_deployed[p][idx];
            }, py::arg("player_id"), py::arg("hand_idx"))
        .def(
            "set_is_deployed", [](InternalState &s, int p, int idx, bool v) {
                if (p < 0 || p >= 2) throw std::out_of_range("player_id must be 0 or 1");
                if (idx < 0 || idx >= MAX_HAND_SIZE) throw std::out_of_range("hand index must be in [0, 17]");
                if (v) deploy_miracle(s, p, idx);
                else undeploy_miracle(s, p, idx);
            }, py::arg("player_id"), py::arg("hand_idx"), py::arg("val"))
        .def(
            "get_sickness", [](InternalState &s, int p) {
                if (p < 0 || p >= 2) throw std::out_of_range("player_id must be 0 or 1");
                return s.sickness[p];
            }, py::arg("player_id"))
        .def(
            "set_sickness", [](InternalState &s, int p, SicknessType v) {
                if (p < 0 || p >= 2) throw std::out_of_range("player_id must be 0 or 1");
                s.sickness[p] = v;
            }, py::arg("player_id"), py::arg("val"))
        .def(
            "get_curses", [](InternalState &s, int p, CurseType idx) {
                if (p < 0 || p >= 2) throw std::out_of_range("player_id must be 0 or 1");
                if (static_cast<int>(idx) < 0 || static_cast<int>(idx) >= 4) throw std::out_of_range("curse index must be in [0, 3]");
                return s.curses[p][idx];
            }, py::arg("player_id"), py::arg("curse_idx"))
        .def(
            "set_curses", [](InternalState &s, int p, CurseType idx, bool v) {
                if (p < 0 || p >= 2) throw std::out_of_range("player_id must be 0 or 1");
                if (static_cast<int>(idx) < 0 || static_cast<int>(idx) >= 4) throw std::out_of_range("curse index must be in [0, 3]");
                s.curses[p][idx] = v;
            }, py::arg("player_id"), py::arg("curse_idx"), py::arg("val"))
        .def(
            "get_guardian", [](InternalState &s, int p) {
                if (p < 0 || p >= 2) throw std::out_of_range("player_id must be 0 or 1");
                return static_cast<int>(s.guardian[p]);
            }, py::arg("player_id"))
        .def(
            "set_guardian", [](InternalState &s, int p, int v) {
                if (p < 0 || p >= 2) throw std::out_of_range("player_id must be 0 or 1");
                s.guardian[p] = static_cast<GuardianType>(v);
            }, py::arg("player_id"), py::arg("val"));

    m.def("step_game", &step_game, "Step a single InternalState");
    m.def("describe_state", &describe_state, py::arg("state"),
          "Dump the state as human-readable text (for crash reports and debugging)");
    m.def(
        "get_legal_actions",
        [](const InternalState &s) {
            bool legal_actions[ACTION_SPACE_SIZE];
            get_legal_actions(s, legal_actions);
            pybind11::list result;
            for (int i = 0; i < ACTION_SPACE_SIZE; ++i) {
                result.append(legal_actions[i]);
            }
            return result;
        },
        "Get a boolean list of legal actions");
    m.def("get_single_legal_action", &get_single_legal_action, "Get single legal action ID if only one is available, else -1");
    m.def(
        "clear_state", [](InternalState &s) {
            auto saved_rng = s.rng;
            // memset ではなく値初期化を使う。ゼロ埋めすると StagedEntry::slot が
            // 0（= 有効な手札スロット）になってしまい、NO_HAND_SLOT にならない。
            // 値初期化ならメンバの既定値がそのまま入る（gcc も非トリビアルな型への
            // memset を -Wclass-memaccess で警告する）。
            s = InternalState();
            s.rng = saved_rng;
            // 番兵は既定値ではなく init_new_game() と同じ値に揃える。ゼロのままだと
            // pending_initiator が 0（= プレイヤー0）になり、テストの盤面が本番より
            // 甘くなる。
            reset_pending_resolution(s);
        },
        "Reset the state to a blank board, preserving RNG");

    m.def(
        "get_opponent_staged_cards_for_obs", [](const InternalState &state, int me) -> py::list {
            int opp = 1 - me;
            py::list result;
            if (state.num_staged_cards[opp] > 0) {
                for (int i = 0; i < state.num_staged_cards[opp]; ++i) {
                    int card_id = staged_card_id(state, opp, i);
                    if (card_id == CARD_EMPTY) continue;
                    result.append(card_id);
                }
            } else if (state.pending_attack_source_id != CARD_EMPTY) {
                result.append(state.pending_attack_source_id);
            }
            return result;
        },
        "Get opponent staged cards for observation integration validation");

    m.def("get_observation", &get_observation, "Get Observation from InternalState for player_id");

    py::enum_<EventType>(m, "EventType")
        .value("NONE", EventType::NONE)
        .value("STAGE_CARD", EventType::STAGE_CARD)
        .value("UNSTAGE_CARD", EventType::UNSTAGE_CARD)
        .value("CONFIRM_ATTACK", EventType::CONFIRM_ATTACK)
        .value("CONFIRM_DEFENSE", EventType::CONFIRM_DEFENSE)
        .value("PASS_DEFENSE", EventType::PASS_DEFENSE)
        .value("ATTACK_HIT", EventType::ATTACK_HIT)
        .value("ATTACK_MISS", EventType::ATTACK_MISS)
        .value("EFFECT_SICKNESS", EventType::EFFECT_SICKNESS)
        .value("EFFECT_GUARDIAN", EventType::EFFECT_GUARDIAN)
        .value("REFLECT_DAMAGE", EventType::REFLECT_DAMAGE)
        .value("TAKE_DAMAGE", EventType::TAKE_DAMAGE)
        .value("HEAL_HP", EventType::HEAL_HP)
        .value("HEAL_MP", EventType::HEAL_MP)
        .value("BUY_CARD", EventType::BUY_CARD)
        .value("SELL_CARD", EventType::SELL_CARD)
        .value("EXCHANGE", EventType::EXCHANGE)
        .value("DRAW_CARD", EventType::DRAW_CARD)
        .value("DISCARD_CARD", EventType::DISCARD_CARD)
        .value("REFUSE_DEAL", EventType::REFUSE_DEAL)
        .value("BLOCK_ATTACK", EventType::BLOCK_ATTACK)
        .value("BOUNCE_ATTACK", EventType::BOUNCE_ATTACK)
        .value("TRIGGER_PHENOMENON", EventType::TRIGGER_PHENOMENON)
        .value("REFLECT_MIRROR", EventType::REFLECT_MIRROR)
        .value("RING_EFFECT", EventType::RING_EFFECT)
        .value("GUARDIAN_ENTER", EventType::GUARDIAN_ENTER)
        .value("GUARDIAN_LEAVE", EventType::GUARDIAN_LEAVE)
        .value("EFFECT_CURSE", EventType::EFFECT_CURSE)
        .value("INSTANT_DEATH", EventType::INSTANT_DEATH)
        .value("REVIVE", EventType::REVIVE)
        .export_values();

    py::module_ se = m.def_submodule("SicknessEvent", "Sickness Event Bitmask Constants");
    se.attr("MASK_TYPE") = SicknessEvent::MASK_TYPE;
    se.attr("TYPE_NONE") = SicknessEvent::TYPE_NONE;
    se.attr("TYPE_COLD") = SicknessEvent::TYPE_COLD;
    se.attr("TYPE_FEVER") = SicknessEvent::TYPE_FEVER;
    se.attr("TYPE_HELL") = SicknessEvent::TYPE_HELL;
    se.attr("TYPE_HEAVEN") = SicknessEvent::TYPE_HEAVEN;
    se.attr("FLAG_DAMAGE") = SicknessEvent::FLAG_DAMAGE;
    se.attr("FLAG_HEAL") = SicknessEvent::FLAG_HEAL;
    se.attr("FLAG_WORSENED") = SicknessEvent::FLAG_WORSENED;
    se.attr("FLAG_SEIZURE") = SicknessEvent::FLAG_SEIZURE;
    se.attr("FLAG_CURED") = SicknessEvent::FLAG_CURED;

    py::module_ ce = m.def_submodule("CurseEvent", "Curse Event Bitmask Constants");
    ce.attr("MASK_TYPE") = CurseEvent::MASK_TYPE;
    ce.attr("TYPE_FOG") = CurseEvent::TYPE_FOG;
    ce.attr("TYPE_FLASH") = CurseEvent::TYPE_FLASH;
    ce.attr("TYPE_DARK_CLOUD") = CurseEvent::TYPE_DARK_CLOUD;
    ce.attr("TYPE_DREAM") = CurseEvent::TYPE_DREAM;
    ce.attr("FLAG_APPLIED") = CurseEvent::FLAG_APPLIED;
    ce.attr("FLAG_CLEARED") = CurseEvent::FLAG_CLEARED;

    py::class_<GameEvent>(m, "GameEvent")
        .def(py::init<>())
        .def_readwrite("actor", &GameEvent::actor)
        .def_readwrite("event_type", &GameEvent::event_type)
        .def_readwrite("card_id", &GameEvent::card_id)
        .def_readwrite("target_id", &GameEvent::target_id)
        .def_readwrite("value", &GameEvent::value);

    py::class_<Observation>(m, "Observation")
        .def(py::init<>())
        .def_readwrite("hp_me", &Observation::hp_me)
        .def_readwrite("hp_opp", &Observation::hp_opp)
        .def_readwrite("mp_me", &Observation::mp_me)
        .def_readwrite("mp_opp", &Observation::mp_opp)
        .def_readwrite("money_me", &Observation::money_me)
        .def_readwrite("money_opp", &Observation::money_opp)
        .def_readwrite("incoming_damage", &Observation::incoming_damage)
        .def_readwrite("current_staged_defense", &Observation::current_staged_defense)
        .def_readwrite("is_apocalypse", &Observation::is_apocalypse)
        .def_readwrite("turn_progress", &Observation::turn_progress)
        .def_readwrite("turns_to_apocalypse", &Observation::turns_to_apocalypse)
        .def_readwrite("hand_count_me", &Observation::hand_count_me)
        .def_readwrite("hand_count_opp", &Observation::hand_count_opp)
        .def_readwrite("history_head", &Observation::history_head)
        .def("get_history", [](const Observation& obs) { return get_array_as_list(obs.history); })
        .def("get_sickness_me", [](const Observation& obs) { return get_array_as_list(obs.sickness_me); })
        .def("get_sickness_opp", [](const Observation& obs) { return get_array_as_list(obs.sickness_opp); })
        .def("get_curses_me", [](const Observation& obs) { return get_array_as_list(obs.curses_me); })
        .def("get_curses_opp", [](const Observation& obs) { return get_array_as_list(obs.curses_opp); })
        .def("get_guardian_me", [](const Observation& obs) { return get_array_as_list(obs.guardian_me); })
        .def("get_guardian_opp", [](const Observation& obs) { return get_array_as_list(obs.guardian_opp); })
        .def("get_phase_one_hot", [](const Observation& obs) { return get_array_as_list(obs.phase_one_hot); })
        .def("get_hand_cards", [](const Observation& obs) { return get_array_as_list(obs.hand_cards); })
        .def("get_staged_cards", [](const Observation& obs) { return get_array_as_list(obs.staged_cards); })
        .def("get_opponent_hand_cards", [](const Observation& obs) { return get_array_as_list(obs.opponent_hand_cards); })
        .def("get_opponent_staged_cards", [](const Observation& obs) { return get_array_as_list(obs.opponent_staged_cards); })
        .def("get_hand_known_to_opp", [](const Observation& obs) { return get_array_as_list(obs.hand_known_to_opp); })
        .def("get_opponent_deployed", [](const Observation& obs) { return get_array_as_list(obs.opponent_deployed); })
        .def("get_action_mask", [](const Observation& obs) { return get_array_as_list(obs.action_mask); })
        .def("to_numpy", [](const Observation& obs) {
            size_t total_floats = sizeof(Observation) / sizeof(float);
            return py::array_t<float>(
                total_floats,
                reinterpret_cast<const float*>(&obs)
            );
        })
        .def("__copy__", [](const Observation& self) { return Observation(self); })
        .def("__deepcopy__", [](const Observation& self, py::dict memo) { return Observation(self); });

    py::class_<EnvPool>(m, "EnvPool")
        .def(py::init<int>(), py::arg("num_envs") = NUM_ENVS)
        .def("reset", &EnvPool::reset, py::arg("seed"))
        .def("step_all", &EnvPool::step_all, py::arg("actions"))
        .def("get_observations", &EnvPool::get_observations)
        .def("step_subset", &EnvPool::step_subset, py::arg("env_ids"), py::arg("actions"))
        .def("get_current_actors", &EnvPool::get_current_actors)
        .def("get_player_stats", &EnvPool::get_player_stats,
             "全環境の HP / MP / お金を真の値で返します。形は (環境数, 6) で、"
             "並びは [p0_hp, p0_mp, p0_money, p1_hp, p1_mp, p1_money]。"
             "観測は霧がかかると相手の値が0に潰れるため、報酬シェーピングには"
             "こちらを使ってください。")
        .def("get_true_hands", &EnvPool::get_true_hands, 
            py::arg("player_id"),
            "指定プレイヤーの真の手札を返します。形は"
            " (環境数, MAX_HAND_SIZE)。観測上の公開情報ではなく内部状態の"
            " true_hand を返すため、報酬シェーピングや Privileged Critic など"
            " 学習時の特権情報用途を想定しています。"
                    )
        .def("get_opponent_true_hands", &EnvPool::get_opponent_true_hands,
             py::arg("player_id"),
             "指定プレイヤーから見た相手の真の手札を返します。形は"
             " (環境数, MAX_HAND_SIZE)。Privileged Critic の学習専用で、"
             "Actor の通常観測には含まれません。")
        .def("get_rewards_for", &EnvPool::get_rewards_for, py::arg("player_id"))
        .def("get_terminal_observations_for", &EnvPool::get_terminal_observations_for, py::arg("player_id"))
        .def("get_rewards", &EnvPool::get_rewards)
        .def("get_dones", &EnvPool::get_dones)
        .def("get_state", &EnvPool::get_state, py::arg("env_id"))
        .def("set_state", &EnvPool::set_state, py::arg("env_id"), py::arg("state"));

    // ------------------------------------------------------------------
    // ISMCTS
    // ------------------------------------------------------------------
    py::class_<ismcts::Config>(m, "IsmctsConfig")
        .def(py::init<>())
        .def_readwrite("num_simulations", &ismcts::Config::num_simulations)
        .def_readwrite("c_puct", &ismcts::Config::c_puct)
        .def_readwrite("prior_floor", &ismcts::Config::prior_floor)
        .def_readwrite("fpu_reduction", &ismcts::Config::fpu_reduction)
        .def_readwrite("expand_root_fully", &ismcts::Config::expand_root_fully)
        .def_readwrite("root_noise_frac", &ismcts::Config::root_noise_frac)
        .def_readwrite("root_noise_alpha", &ismcts::Config::root_noise_alpha)
        .def_readwrite("rollout_max_steps", &ismcts::Config::rollout_max_steps)
        .def_readwrite("seed", &ismcts::Config::seed);

    py::class_<ismcts::Result>(m, "IsmctsResult")
        .def_readonly("best_action", &ismcts::Result::best_action)
        .def_readonly("simulations", &ismcts::Result::simulations)
        .def_readonly("actions", &ismcts::Result::actions)
        .def_readonly("visits", &ismcts::Result::visits)
        .def_readonly("values", &ismcts::Result::values)
        .def_readonly("priors", &ismcts::Result::priors);

    py::class_<ismcts::Stats>(m, "IsmctsStats")
        .def_readonly("nodes", &ismcts::Stats::nodes)
        .def_readonly("edges", &ismcts::Stats::edges)
        .def_readonly("simulations", &ismcts::Stats::simulations)
        .def_readonly("game_steps", &ismcts::Stats::game_steps)
        .def_readonly("evaluations", &ismcts::Stats::evaluations)
        .def_readonly("max_depth", &ismcts::Stats::max_depth)
        .def_readonly("edge_relocations", &ismcts::Stats::edge_relocations);

    m.def(
        "ismcts_search",
        [](const InternalState& state, int searching_player, const ismcts::Config& config) {
            // 探索はC++に閉じているのでGILを離す。可視化サーバーが探索中も
            // 応答できるようにするため。
            py::gil_scoped_release release;
            return ismcts::search(state, searching_player, config, nullptr);
        },
        py::arg("state"), py::arg("searching_player"), py::arg("config"),
        "情報集合ごとに1本の木でISMCTSを行い、各合法手の訪問回数と価値を返します。");

    m.def("ismcts_last_stats", &ismcts::last_search_stats,
          "直前の探索の統計（ノード数・step_game呼び出し回数など）。");

    m.def(
        "ismcts_determinize",
        [](InternalState& state, int searching_player, uint32_t seed) {
            Xoshiro128PP rng;
            rng.seed(seed);
            ismcts::determinize(state, searching_player, rng);
        },
        py::arg("state"), py::arg("searching_player"), py::arg("seed"),
        "隠れ情報（相手の手札・夢で未確定の自分の手札）をサンプリングし直します。");
}
