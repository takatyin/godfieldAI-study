#include "env_pool.h"
#include "game_logic.h"
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
        states_[i].current_phase = GamePhase::STATE_0_GUARDIAN;
        states_[i].hp[0] = 40; states_[i].hp[1] = 40;
        states_[i].mp[0] = 0; states_[i].mp[1] = 0;
        states_[i].money[0] = 0; states_[i].money[1] = 0;
        states_[i].sickness[0] = 0; states_[i].sickness[1] = 0;
        states_[i].status_ailments[0] = 0; states_[i].status_ailments[1] = 0;
        states_[i].guardian[0] = 0; states_[i].guardian[1] = 0;
        states_[i].num_staged_cards[0] = 0; states_[i].num_staged_cards[1] = 0;

        // Draw initial hands
        for (int p=0; p<2; ++p) {
            for (int h=0; h<MAX_HAND_SIZE; ++h) {
                if (h < 9) {
                    states_[i].true_hand[p][h] = draw_card(states_[i].rng);
                } else {
                    states_[i].true_hand[p][h] = -1; // Empty slot
                }
                states_[i].is_known_to_opp[p][h] = false;
            }
        }
        states_[i].is_done = false;
        states_[i].p0_reward = 0.0f;
        states_[i].p1_reward = 0.0f;
        states_[i].queue_size_p0 = 0;
        states_[i].queue_size_p1 = 0;

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
    step_game(state, action);
    
    // Environment specific artificial turn advance (for now)
    state.current_turn++;
    if (state.current_turn > MAX_EPISODE_TURNS) {
        state.is_done = true;
    }
}

void EnvPool::generate_observation(int env_id) {
    InternalState& state = states_[env_id];
    Observation& obs = obs_buffers_[env_id];
    std::memset(&obs, 0, sizeof(Observation));
    
    int me = state.current_actor_id;
    int opp = 1 - me;
    
    // Normalizing logic
    obs.hp_me = state.hp[me] / 100.0f;
    obs.hp_opp = state.hp[opp] / 100.0f;
    obs.mp_me = state.mp[me] / 100.0f;
    obs.mp_opp = state.mp[opp] / 100.0f;
    
    obs.is_apocalypse = (state.current_turn >= APOCALYPSE_TURN) ? 1.0f : 0.0f;

    // Default mask allows everything for now
    for (int i=0; i<ACTION_SPACE_SIZE; ++i) {
        obs.action_mask[i] = 1.0f;
    }
}

void EnvPool::check_done(int env_id) {
    // placeholder
}

void EnvPool::flush_n_step_queue(int env_id) {
    // placeholder
}
