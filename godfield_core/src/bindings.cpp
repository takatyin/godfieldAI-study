#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/numpy.h>
#include "env_pool.h"
#include "game_logic.h"
#include "types.h"

namespace py = pybind11;

PYBIND11_MODULE(godfield_core, m) {
    m.doc() = "GodField core engine and RL environment pool";

    // Bind initialization function
    m.def("init_game_logic", &init_game_logic, "Initialize the global card registry from JSON");

    // Bind enums
    py::enum_<Element>(m, "Element")
        .value("ELEM_NONE", ELEM_NONE)
        .value("ELEM_FIRE", ELEM_FIRE)
        .value("ELEM_WATER", ELEM_WATER)
        .value("ELEM_WOOD", ELEM_WOOD)
        .value("ELEM_EARTH", ELEM_EARTH)
        .value("ELEM_LIGHT", ELEM_LIGHT)
        .value("ELEM_DARK", ELEM_DARK)
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
        .value("STATE_0_GUARDIAN", GamePhase::STATE_0_GUARDIAN)
        .value("STATE_1_MAIN", GamePhase::STATE_1_MAIN)
        .value("STATE_2_ATK_PLUS", GamePhase::STATE_2_ATK_PLUS)
        .value("STATE_3_MIRACLE_PLUS", GamePhase::STATE_3_MIRACLE_PLUS)
        .value("STATE_M_SUPER_MIRROR", GamePhase::STATE_M_SUPER_MIRROR)
        .value("STATE_4_ATK_DEF", GamePhase::STATE_4_ATK_DEF)
        .value("STATE_5_MIRACLE_DEF", GamePhase::STATE_5_MIRACLE_DEF)
        .value("STATE_6_END", GamePhase::STATE_6_END)
        .export_values();

    // Bind InternalState
    py::class_<InternalState>(m, "InternalState")
        .def(py::init<>())
        .def_readwrite("current_actor_id", &InternalState::current_actor_id)
        .def_readwrite("current_turn", &InternalState::current_turn)
        .def_readwrite("current_phase", &InternalState::current_phase)
        .def_readwrite("attacker_id", &InternalState::attacker_id)
        .def_readwrite("defender_id", &InternalState::defender_id)
        .def_readwrite("pending_attack_power", &InternalState::pending_attack_power)
        .def_readwrite("is_done", &InternalState::is_done)
        // For array members, pybind11 requires special handling to access by index from python.
        // For now, we will add helper methods to InternalState bindings to get/set these arrays.
        .def("get_hp", [](InternalState &s, int p) { return s.hp[p]; })
        .def("set_hp", [](InternalState &s, int p, int v) { s.hp[p] = v; })
        .def("get_mp", [](InternalState &s, int p) { return s.mp[p]; })
        .def("set_mp", [](InternalState &s, int p, int v) { s.mp[p] = v; })
        .def("get_money", [](InternalState &s, int p) { return s.money[p]; })
        .def("set_money", [](InternalState &s, int p, int v) { s.money[p] = v; })
        .def("get_status_ailments", [](InternalState &s, int p) { return s.status_ailments[p]; })
        .def("set_status_ailments", [](InternalState &s, int p, int v) { s.status_ailments[p] = v; })
        .def("get_true_hand", [](InternalState &s, int p, int idx) { return s.true_hand[p][idx]; })
        .def("set_true_hand", [](InternalState &s, int p, int idx, int v) { s.true_hand[p][idx] = v; })
        .def("get_is_known_to_opp", [](InternalState &s, int p, int idx) { return s.is_known_to_opp[p][idx]; })
        .def("set_is_known_to_opp", [](InternalState &s, int p, int idx, bool v) { s.is_known_to_opp[p][idx] = v; });

    m.def("step_game", &step_game, "Step a single InternalState");

    py::class_<EnvPool>(m, "EnvPool")
        .def(py::init<int>(), py::arg("num_envs") = NUM_ENVS)
        .def("reset", &EnvPool::reset, py::arg("seed"))
        .def("step_all", &EnvPool::step_all, py::arg("actions"))
        .def("get_observations", &EnvPool::get_observations)
        .def("get_ready_env_ids", &EnvPool::get_ready_env_ids);
}
