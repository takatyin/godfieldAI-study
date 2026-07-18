#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/numpy.h>
#include "env_pool.h"
#include "game_logic.h"
#include "game_logic_internal.h"
#include "types.h"

namespace py = pybind11;

PYBIND11_MODULE(godfield_core, m) {
    m.doc() = "GodField core engine and RL environment pool";

    // Bind initialization function
    m.def("init_game_logic", &init_game_logic, "Initialize the global card registry from JSON");
    m.def("get_registry_size", &get_registry_size, "Get number of cards in registry");
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
        .value("PHASE_GROUP_MIRACLE", GamePhase::PHASE_GROUP_MIRACLE)
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
        .def_readwrite("attacker_id", &InternalState::attacker_id)
        .def_readwrite("defender_id", &InternalState::defender_id)
        .def_readwrite("pending_attack_power", &InternalState::pending_attack_power)
        .def_readwrite("pending_attack_element", &InternalState::pending_attack_element)
        .def_readwrite("pending_absorption", &InternalState::pending_absorption)
        .def_readwrite("pending_deal_same_damage", &InternalState::pending_deal_same_damage)
        .def_readwrite("pending_is_group_attack", &InternalState::pending_is_group_attack)
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
            "get_hp", [](InternalState &s, int p) { return s.hp[p]; }, py::arg("player_id"))
        .def(
            "set_hp", [](InternalState &s, int p, int v) { s.hp[p] = v; }, py::arg("player_id"), py::arg("hp"))
        .def(
            "get_mp", [](InternalState &s, int p) { return s.mp[p]; }, py::arg("player_id"))
        .def(
            "set_mp", [](InternalState &s, int p, int v) { s.mp[p] = v; }, py::arg("player_id"), py::arg("mp"))
        .def(
            "get_money", [](InternalState &s, int p) { return s.money[p]; }, py::arg("player_id"))
        .def(
            "set_money", [](InternalState &s, int p, int v) { s.money[p] = v; }, py::arg("player_id"), py::arg("money"))
        .def(
            "get_true_hand", [](InternalState &s, int p, int idx) { return s.true_hand[p][idx]; }, py::arg("player_id"),
            py::arg("hand_idx"))
        .def(
            "set_true_hand", [](InternalState &s, int p, int idx, int v) { s.true_hand[p][idx] = v; s.apparent_hand[p][idx] = v; s.is_confirmed[p][idx] = true; },
            py::arg("player_id"), py::arg("hand_idx"), py::arg("card_id"))
        .def(
            "add_card_to_hand_slot", [](InternalState &s, int p, int idx, int card_id, bool is_drawn) { add_card_to_hand_slot(s, p, idx, card_id, is_drawn); },
            py::arg("player_id"), py::arg("hand_idx"), py::arg("card_id"), py::arg("is_drawn"))
        .def(
            "get_apparent_hand", [](InternalState &s, int p, int idx) { return s.apparent_hand[p][idx]; }, py::arg("player_id"),
            py::arg("hand_idx"))
        .def(
            "set_apparent_hand", [](InternalState &s, int p, int idx, int v) { s.apparent_hand[p][idx] = v; },
            py::arg("player_id"), py::arg("hand_idx"), py::arg("card_id"))
        .def(
            "get_is_confirmed", [](InternalState &s, int p, int idx) { return s.is_confirmed[p][idx]; }, py::arg("player_id"),
            py::arg("hand_idx"))
        .def(
            "set_is_confirmed", [](InternalState &s, int p, int idx, bool v) { s.is_confirmed[p][idx] = v; },
            py::arg("player_id"), py::arg("hand_idx"), py::arg("is_confirmed"))
        .def(
            "get_is_known_to_opp", [](InternalState &s, int p, int idx) { return s.is_known_to_opp[p][idx]; },
            py::arg("player_id"), py::arg("hand_idx"))
        .def(
            "set_is_known_to_opp", [](InternalState &s, int p, int idx, bool v) { s.is_known_to_opp[p][idx] = v; },
            py::arg("player_id"), py::arg("hand_idx"), py::arg("is_known"))
        .def(
            "get_is_used", [](InternalState &s, int p, int idx) { return s.is_used[p][idx]; }, py::arg("player_id"),
            py::arg("hand_idx"))
        .def(
            "set_is_used", [](InternalState &s, int p, int idx, bool v) { s.is_used[p][idx] = v; },
            py::arg("player_id"), py::arg("hand_idx"), py::arg("is_used"))
        .def(
            "get_num_staged_cards", [](InternalState &s, int p) { return s.num_staged_cards[p]; }, py::arg("player_id"))
        .def(
            "set_num_staged_cards", [](InternalState &s, int p, int v) { s.num_staged_cards[p] = v; },
            py::arg("player_id"), py::arg("num"))
        .def(
            "get_staged_card", [](InternalState &s, int p, int idx) { return s.staged_cards[p][idx]; },
            py::arg("player_id"), py::arg("staged_idx"))
        .def(
            "set_staged_card", [](InternalState &s, int p, int idx, int v) { s.staged_cards[p][idx] = v; },
            py::arg("player_id"), py::arg("staged_idx"), py::arg("val"))
        .def(
            "get_is_deployed", [](InternalState &s, int p, int idx) { return s.is_deployed[p][idx]; },
            py::arg("player_id"), py::arg("hand_idx"))
        .def(
            "set_is_deployed", [](InternalState &s, int p, int idx, bool v) { 
                if (v) deploy_miracle(s, p, idx);
                else undeploy_miracle(s, p, idx);
            },
            py::arg("player_id"), py::arg("hand_idx"), py::arg("val"))
        .def(
            "get_miracle_used_this_turn", [](InternalState &s, int p, int idx) { return s.miracle_used_this_turn[p][idx]; },
            py::arg("player_id"), py::arg("hand_idx"))
        .def(
            "set_miracle_used_this_turn", [](InternalState &s, int p, int idx, bool v) { s.miracle_used_this_turn[p][idx] = v; },
            py::arg("player_id"), py::arg("hand_idx"), py::arg("val"))
        .def(
            "get_sickness", [](InternalState &s, int p) { return s.sickness[p]; }, py::arg("player_id"))
        .def(
            "set_sickness", [](InternalState &s, int p, SicknessType v) { s.sickness[p] = v; }, py::arg("player_id"), py::arg("val"))
        .def(
            "get_curses", [](InternalState &s, int p, CurseType idx) { return s.curses[p][idx]; }, py::arg("player_id"), py::arg("curse_idx"))
        .def(
            "set_curses", [](InternalState &s, int p, CurseType idx, bool v) { s.curses[p][idx] = v; }, py::arg("player_id"), py::arg("curse_idx"), py::arg("val"))
        .def(
            "get_guardian", [](InternalState &s, int p) { return static_cast<int>(s.guardian[p]); }, py::arg("player_id"))
        .def(
            "set_guardian", [](InternalState &s, int p, int v) { s.guardian[p] = static_cast<GuardianType>(v); }, py::arg("player_id"), py::arg("val"));

    m.def("step_game", &step_game, "Step a single InternalState");
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
    m.def(
        "clear_state", [](InternalState &s) {
            auto saved_rng = s.rng;
            std::memset(&s, 0, sizeof(InternalState));
            s.rng = saved_rng;
        },
        "Zero out the state memory preserving RNG");

    m.def(
        "get_opponent_staged_cards_for_obs", [](const InternalState &state, int me) -> py::list {
            int opp = 1 - me;
            py::list result;
            if (state.num_staged_cards[opp] > 0) {
                for (int i = 0; i < state.num_staged_cards[opp]; ++i) {
                    int h_idx = state.staged_cards[opp][i];
                    result.append(state.true_hand[opp][h_idx]);
                }
            } else if (state.pending_attack_source_id != CARD_EMPTY) {
                result.append(state.pending_attack_source_id);
            }
            return result;
        },
        "Get opponent staged cards for observation integration validation");

    py::class_<EnvPool>(m, "EnvPool")
        .def(py::init<int>(), py::arg("num_envs") = NUM_ENVS)
        .def("reset", &EnvPool::reset, py::arg("seed"))
        .def("step_all", &EnvPool::step_all, py::arg("actions"))
        .def("get_observations", &EnvPool::get_observations)
        .def("get_ready_env_ids", &EnvPool::get_ready_env_ids)
        .def("get_state", &EnvPool::get_state, py::arg("env_id"))
        .def("set_state", &EnvPool::set_state, py::arg("env_id"), py::arg("state"));
}
