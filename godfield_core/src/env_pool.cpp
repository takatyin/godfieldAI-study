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
        states_[i].sickness[0] = 0; states_[i].sickness[1] = 0;
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
    InternalState& state = states_[env_id];
    Observation& obs = obs_buffers_[env_id];
    std::memset(&obs, 0, sizeof(Observation));
    
    int me = state.current_actor_id;
    int opp = 1 - me;
    
    bool is_me_fog = state.curses[me][static_cast<int>(CurseType::CURSE_FOG)];
    bool is_me_dream = state.curses[me][static_cast<int>(CurseType::CURSE_DREAM)];

    // Normalizing logic
    obs.hp_me = state.hp[me] / 100.0f;
    obs.mp_me = state.mp[me] / 100.0f;
    obs.money_me = state.money[me] / 100.0f;

    if (is_me_fog) {
        obs.hp_opp = 0.0f;
        obs.mp_opp = 0.0f;
        obs.money_opp = 0.0f;
    } else {
        obs.hp_opp = state.hp[opp] / 100.0f;
        obs.mp_opp = state.mp[opp] / 100.0f;
        obs.money_opp = state.money[opp] / 100.0f;
    }
    
    obs.sickness_me[state.sickness[me]] = 1.0f;
    if (!is_me_fog) {
        obs.sickness_opp[state.sickness[opp]] = 1.0f;
    }
    
    obs.guardian_me[state.guardian[me]] = 1.0f;
    if (!is_me_fog) {
        obs.guardian_opp[state.guardian[opp]] = 1.0f;
    }

    for (int i = 0; i < 4; ++i) {
        obs.curses_me[i] = state.curses[me][i] ? 1.0f : 0.0f;
        if (is_me_fog) {
            obs.curses_opp[i] = 0.0f;
        } else {
            obs.curses_opp[i] = state.curses[opp][i] ? 1.0f : 0.0f;
        }
    }
    
    obs.is_apocalypse = (state.current_turn >= APOCALYPSE_TURN) ? 1.0f : 0.0f;

    // Hand cards
    for (int i = 0; i < MAX_HAND_SIZE; ++i) {
        if (state.true_hand[me][i] != CARD_EMPTY) {
            obs.hand_cards[i] = is_me_dream ? ID_DREAM : state.true_hand[me][i];
        } else {
            obs.hand_cards[i] = CARD_EMPTY;
        }
    }

    // Staged cards
    std::fill(std::begin(obs.staged_cards), std::end(obs.staged_cards), CARD_EMPTY);
    for (int i = 0; i < state.num_staged_cards[me]; ++i) {
        int h_idx = state.staged_cards[me][i];
        obs.staged_cards[i] = is_me_dream ? ID_DREAM : state.true_hand[me][h_idx];
    }

    // Opponent hand cards (相手の公開手札のスロット位置リークを防ぐため、左詰めで格納する)
    int known_count = 0;
    std::fill(std::begin(obs.opponent_hand_cards), std::end(obs.opponent_hand_cards), 0);
    if (!is_me_fog) {
        for (int i = 0; i < MAX_HAND_SIZE; ++i) {
            if (state.is_known_to_opp[opp][i] || state.is_deployed[opp][i]) {
                obs.opponent_hand_cards[known_count++] = state.true_hand[opp][i];
            }
        }
    }

    // Opponent staged cards
    std::fill(std::begin(obs.opponent_staged_cards), std::end(obs.opponent_staged_cards), CARD_EMPTY);
    if (state.num_staged_cards[opp] > 0) {
        for (int i = 0; i < state.num_staged_cards[opp]; ++i) {
            int h_idx = state.staged_cards[opp][i];
            obs.opponent_staged_cards[i] = state.true_hand[opp][h_idx];
        }
    } else if (state.pending_attack_source_id != CARD_EMPTY) {
        obs.opponent_staged_cards[0] = state.pending_attack_source_id;
    }

    // Legal actions mask
    bool legal_actions[ACTION_SPACE_SIZE];
    get_legal_actions(state, legal_actions);
    for (int i = 0; i < ACTION_SPACE_SIZE; ++i) {
        obs.action_mask[i] = legal_actions[i] ? 1.0f : 0.0f;
    }
}

void EnvPool::check_done(int env_id) {
    // placeholder
}

void EnvPool::flush_n_step_queue(int env_id) {
    // placeholder
}
