#include "env_pool.h"
#include "game_logic.h"
#include "generated_card_ids.h"
#include <cstring>
#include <stdexcept>
#include <iostream>

EnvPool::EnvPool(int num_envs) : num_envs_(num_envs), seed_(42) {
    states_.resize(num_envs_);
    obs_buffers_.resize(num_envs_);
    reset_counts_.resize(num_envs_, 0);
    rewards_.resize(num_envs_, 0.0f);
    dones_.resize(num_envs_, 0.0f);
    ready_env_ids_.resize(num_envs_);
    for(int i=0; i<num_envs_; ++i) {
        ready_env_ids_[i] = i;
    }
}

EnvPool::~EnvPool() {}

void EnvPool::reset_env(int env_id, int seed) {
    std::mt19937 rng_copy;
    rng_copy.seed(seed);
    states_[env_id] = InternalState();
    states_[env_id].rng = rng_copy;

    states_[env_id].current_actor_id = 0;
    states_[env_id].current_turn = 0;
    states_[env_id].current_phase = GamePhase::PHASE_MAIN;
    states_[env_id].hp[0] = 40; states_[env_id].hp[1] = 40;
    states_[env_id].mp[0] = 10; states_[env_id].mp[1] = 10;
    states_[env_id].money[0] = 20; states_[env_id].money[1] = 20;
    states_[env_id].num_staged_cards[0] = 0; states_[env_id].num_staged_cards[1] = 0;
    
    states_[env_id].attacker_id = -1;
    states_[env_id].defender_id = -1;
    states_[env_id].pending_attack_power = 0;
    states_[env_id].pending_attack_element = ELEM_NONE;
    states_[env_id].pending_absorption = false;
    states_[env_id].pending_deal_same_damage = false;
    states_[env_id].num_pending_counters = 0;
    states_[env_id].pending_attack_curse = CURSE_NONE;
    states_[env_id].pending_take_cp = false;
    states_[env_id].pending_attack_source_id = CARD_EMPTY;
    states_[env_id].sickness[0] = SICKNESS_NONE; states_[env_id].sickness[1] = SICKNESS_NONE;
    states_[env_id].guardian[0] = GUARDIAN_NONE; states_[env_id].guardian[1] = GUARDIAN_NONE;
    std::memset(states_[env_id].curses, 0, sizeof(states_[env_id].curses));
    states_[env_id].turn_end_state = TurnEndSubstep::DEATH_CHECK_START;
    states_[env_id].pending_ascension_bows[0] = 0; states_[env_id].pending_ascension_bows[1] = 0;
    states_[env_id].heaven_seizure_occurred[0] = false; states_[env_id].heaven_seizure_occurred[1] = false;
    states_[env_id].history_head = 0;
    states_[env_id].history_count = 0;
    std::memset(states_[env_id].history, 0, sizeof(states_[env_id].history));

    // Draw initial hands
    for (int p=0; p<2; ++p) {
        for (int h=0; h<MAX_HAND_SIZE; ++h) {
            if (h < 9) {
                states_[env_id].true_hand[p][h] = draw_card(states_[env_id].rng);
            } else {
                states_[env_id].true_hand[p][h] = CARD_EMPTY; // Empty slot
            }
            states_[env_id].apparent_hand[p][h] = states_[env_id].true_hand[p][h];
            states_[env_id].is_confirmed[p][h] = true;
            states_[env_id].is_known_to_opp[p][h] = false;
            states_[env_id].is_used[p][h] = false;
            states_[env_id].is_deployed[p][h] = false;
        }
    }
    states_[env_id].is_done = false;
    states_[env_id].p0_reward = 0.0f;
    states_[env_id].p1_reward = 0.0f;

    // Auto-advance if the starting state has only 1 legal action
    int auto_action;
    while (!states_[env_id].is_done && (auto_action = get_single_legal_action(states_[env_id])) != -1) {
        step_game(states_[env_id], static_cast<ActionType>(auto_action));
    }
}

void EnvPool::reset(int seed) {
    seed_ = seed;
    for (int i = 0; i < num_envs_; ++i) {
        reset_counts_[i] = 0;
        rewards_[i] = 0.0f;
        dones_[i] = 0.0f;
        reset_env(i, seed_ + i);
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
    pybind11::handle base = pybind11::cast(this);
    return pybind11::array_t<float>(
        {static_cast<pybind11::ssize_t>(total_floats)},
        {sizeof(float)},
        reinterpret_cast<float*>(obs_buffers_.data()),
        base
    );
}

pybind11::array_t<float> EnvPool::get_rewards() {
    pybind11::handle base = pybind11::cast(this);
    return pybind11::array_t<float>(
        {static_cast<pybind11::ssize_t>(rewards_.size())},
        {sizeof(float)},
        rewards_.data(),
        base
    );
}

pybind11::array_t<float> EnvPool::get_dones() {
    pybind11::handle base = pybind11::cast(this);
    return pybind11::array_t<float>(
        {static_cast<pybind11::ssize_t>(dones_.size())},
        {sizeof(float)},
        dones_.data(),
        base
    );
}

pybind11::array_t<int> EnvPool::get_ready_env_ids() {
    pybind11::handle base = pybind11::cast(this);
    return pybind11::array_t<int>(
        {static_cast<pybind11::ssize_t>(ready_env_ids_.size())},
        {sizeof(int)},
        ready_env_ids_.data(),
        base
    );
}


void EnvPool::step_env(int env_id, int action) {
    InternalState& state = states_[env_id];
    int acting_player = state.current_actor_id;
    
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

    if (state.is_done) {
        // 元のアクション実行プレイヤー視点での最終報酬を設定
        rewards_[env_id] = (acting_player == 0) ? state.p0_reward : state.p1_reward;
        dones_[env_id] = 1.0f;

        // 次のゲームのために環境を自動リセット
        reset_env(env_id, seed_ + num_envs_ + (reset_counts_[env_id]++));
    } else {
        rewards_[env_id] = 0.0f;
        dones_[env_id] = 0.0f;
    }
}

void EnvPool::generate_observation(int env_id) {
    make_observation(states_[env_id], states_[env_id].current_actor_id, obs_buffers_[env_id]);
}


