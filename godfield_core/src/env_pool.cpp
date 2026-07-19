#include "env_pool.h"
#include "game_logic.h"
#include "generated_card_ids.h"
#include <cstring>
#include <stdexcept>
#include <iostream>

EnvPool::EnvPool(int num_envs) : num_envs_(num_envs) {
    states_.resize(num_envs_);
    obs_buffers_.resize(num_envs_);
    ready_env_ids_.resize(num_envs_);
    for(int i=0; i<num_envs_; ++i) {
        ready_env_ids_[i] = i;
    }
}

EnvPool::~EnvPool() {}

void EnvPool::reset(int seed) {
    for (int i = 0; i < num_envs_; ++i) {
        states_[i].rng.seed(seed + i);
        states_[i].current_actor_id = 0;
        states_[i].current_turn = 0;
        states_[i].current_phase = GamePhase::PHASE_MAIN;
        states_[i].hp[0] = 40; states_[i].hp[1] = 40;
        states_[i].mp[0] = 10; states_[i].mp[1] = 10;
        states_[i].money[0] = 20; states_[i].money[1] = 20;
        states_[i].num_staged_cards[0] = 0; states_[i].num_staged_cards[1] = 0;
        
        states_[i].attacker_id = -1;
        states_[i].defender_id = -1;
        states_[i].pending_attack_power = 0;
        states_[i].pending_attack_element = ELEM_NONE;
        states_[i].pending_absorption = false;
        states_[i].pending_deal_same_damage = false;
        states_[i].num_pending_counters = 0;
        states_[i].pending_attack_curse = CURSE_NONE;
        states_[i].pending_take_cp = false;
        states_[i].pending_attack_source_id = CARD_EMPTY;
        states_[i].sickness[0] = SICKNESS_NONE; states_[i].sickness[1] = SICKNESS_NONE;
        std::memset(states_[i].curses, 0, sizeof(states_[i].curses));
        states_[i].turn_end_state = 0;
        states_[i].pending_ascension_bows[0] = 0; states_[i].pending_ascension_bows[1] = 0;
        states_[i].heaven_seizure_occurred[0] = false; states_[i].heaven_seizure_occurred[1] = false;

        // Draw initial hands
        for (int p=0; p<2; ++p) {
            states_[i].num_deployed_miracles[p] = 0;
            for (int h=0; h<MAX_HAND_SIZE; ++h) {
                if (h < 9) {
                    states_[i].true_hand[p][h] = draw_card(states_[i].rng);
                } else {
                    states_[i].true_hand[p][h] = CARD_EMPTY; // Empty slot
                }
                states_[i].apparent_hand[p][h] = states_[i].true_hand[p][h];
                states_[i].is_confirmed[p][h] = true;
                states_[i].is_known_to_opp[p][h] = false;
                states_[i].is_used[p][h] = false;
                states_[i].is_deployed[p][h] = false;
                states_[i].miracle_used_this_turn[p][h] = false;
            }
        }
        states_[i].is_done = false;
        states_[i].p0_reward = 0.0f;
        states_[i].p1_reward = 0.0f;

        // Auto-advance if the starting state has only 1 legal action
        int auto_action;
        while (!states_[i].is_done && (auto_action = get_single_legal_action(states_[i])) != -1) {
            step_game(states_[i], static_cast<ActionType>(auto_action));
        }

        generate_observation(i);
        ready_env_ids_[i] = i; // All ready
    }
}

void EnvPool::step_all(pybind11::array_t<int> actions) {
    auto buf = actions.request();
    int* ptr = static_cast<int*>(buf.ptr);
    size_t batch_size = buf.shape[0];

    for (size_t i = 0; i < batch_size; ++i) {
        int env_id = ready_env_ids_[i];
        int action = ptr[i];
        step_env(env_id, action);
        generate_observation(env_id);
    }
}

pybind11::array_t<float> EnvPool::get_observations() {
    size_t total_floats = num_envs_ * (sizeof(Observation) / sizeof(float));

    // Zero-copy array pointing to std::vector data
    auto result = pybind11::array_t<float>(
        total_floats,
        reinterpret_cast<float*>(obs_buffers_.data())
    );
    return result;
}

pybind11::array_t<int> EnvPool::get_ready_env_ids() {
    auto result = pybind11::array_t<int>(
        ready_env_ids_.size(),
        ready_env_ids_.data()
    );
    return result;
}

void EnvPool::step_env(int env_id, int action) {
    InternalState& state = states_[env_id];
    
    // Call the decoupled game logic
    step_game(state, static_cast<ActionType>(action));

    // Auto-advance loop for phases with only 1 legal choice
    int auto_action;
    while (!state.is_done && (auto_action = get_single_legal_action(state)) != -1) {
        step_game(state, static_cast<ActionType>(auto_action));
    }
    
    // Environment specific artificial turn advance (for now)
    if (state.current_turn > MAX_EPISODE_TURNS) {
        state.is_done = true;
    }
}

void EnvPool::generate_observation(int env_id) {
    make_observation(states_[env_id], states_[env_id].current_actor_id, obs_buffers_[env_id]);
}

void EnvPool::check_done(int env_id) {
    // placeholder
}

void EnvPool::flush_n_step_queue(int env_id) {
    // placeholder
}
