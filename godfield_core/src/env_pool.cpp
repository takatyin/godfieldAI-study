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
    current_actors_.resize(num_envs_, 0);
    for (int p = 0; p < 2; ++p) {
        terminal_obs_buffers_[p].resize(num_envs_);
        rewards_per_player_[p].resize(num_envs_, 0.0f);
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
                states_[env_id].true_hand[p][h] = draw_card(states_[env_id]);
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
        current_actors_[i] = states_[i].current_actor_id;
        rewards_per_player_[0][i] = 0.0f;
        rewards_per_player_[1][i] = 0.0f;
    }
}

void EnvPool::step_all(pybind11::array_t<int> actions) {
    auto buf = actions.request();
    int* ptr = static_cast<int*>(buf.ptr);
    size_t batch_size = buf.shape[0];

    // actions[i] は環境 i への行動。各反復は自分の環境の状態とバッファにしか触れないため並列化できる
#pragma omp parallel for
    for (int env_id = 0; env_id < static_cast<int>(batch_size); ++env_id) {
        step_env(env_id, ptr[env_id]);
        generate_observation(env_id);
    }
}

void EnvPool::step_subset(pybind11::array_t<int> env_ids, pybind11::array_t<int> actions) {
    auto id_buf = env_ids.request();
    auto act_buf = actions.request();
    if (id_buf.shape[0] != act_buf.shape[0]) {
        throw std::runtime_error("step_subset: env_ids と actions の長さが一致しません");
    }
    int* ids = static_cast<int*>(id_buf.ptr);
    int* acts = static_cast<int*>(act_buf.ptr);
    int count = static_cast<int>(id_buf.shape[0]);

    // env_ids に重複がない限り、各反復は自分の環境にしか触れないため並列化できる
#pragma omp parallel for
    for (int k = 0; k < count; ++k) {
        int env_id = ids[k];
        if (env_id < 0 || env_id >= num_envs_) continue;
        step_env(env_id, acts[k]);
        generate_observation(env_id);
    }
}

pybind11::array_t<int> EnvPool::get_current_actors() {
    pybind11::handle base = pybind11::cast(this);
    return pybind11::array_t<int>(
        {static_cast<pybind11::ssize_t>(current_actors_.size())},
        {sizeof(int)},
        current_actors_.data(),
        base
    );
}

pybind11::array_t<float> EnvPool::get_rewards_for(int player_id) {
    if (player_id < 0 || player_id > 1) {
        throw std::runtime_error("get_rewards_for: player_id は 0 か 1 である必要があります");
    }
    pybind11::handle base = pybind11::cast(this);
    return pybind11::array_t<float>(
        {static_cast<pybind11::ssize_t>(rewards_per_player_[player_id].size())},
        {sizeof(float)},
        rewards_per_player_[player_id].data(),
        base
    );
}

pybind11::array_t<float> EnvPool::get_terminal_observations_for(int player_id) {
    if (player_id < 0 || player_id > 1) {
        throw std::runtime_error("get_terminal_observations_for: player_id は 0 か 1 である必要があります");
    }
    size_t total_floats = num_envs_ * (sizeof(Observation) / sizeof(float));
    pybind11::handle base = pybind11::cast(this);
    return pybind11::array_t<float>(
        {static_cast<pybind11::ssize_t>(total_floats)},
        {sizeof(float)},
        reinterpret_cast<float*>(terminal_obs_buffers_[player_id].data()),
        base
    );
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
    
    // ターン数による人為的な打ち切りは行わない。
    // 上級者同士の膠着から終末の時（150ターン）へ突入する展開もエージェントに学習させたいため、
    // 決着はゲームルール（run_death_check）にのみ委ねる。終末の時に入れば比較的すぐ決着する。
    // 打ち切りを安全弁として使えないので、進行不能な状態を作らないこと自体が要件になる
    // （合法手が0件になる状態は tests/test_rl_pipeline.py で検知している）。

    if (state.is_done) {
        // 元のアクション実行プレイヤー視点での最終報酬を設定
        rewards_[env_id] = (acting_player == 0) ? state.p0_reward : state.p1_reward;
        // 学習者が相手の手番で負ける／勝つ場合に備え、両プレイヤー視点の報酬も残す
        rewards_per_player_[0][env_id] = state.p0_reward;
        rewards_per_player_[1][env_id] = state.p1_reward;
        dones_[env_id] = 1.0f;

        // 自動リセットで真の終端が失われるため、両プレイヤー視点でキャッシュしておく
        for (int p = 0; p < 2; ++p) {
            make_observation(state, p, terminal_obs_buffers_[p][env_id]);
        }

        // 次のゲームのために環境を自動リセット (シード衝突を防ぐため、env_idごとに異なるシード系列を配分)
        reset_env(env_id, seed_ + num_envs_ * (1 + reset_counts_[env_id]++) + env_id);
    } else {
        rewards_[env_id] = 0.0f;
        rewards_per_player_[0][env_id] = 0.0f;
        rewards_per_player_[1][env_id] = 0.0f;
        dones_[env_id] = 0.0f;
    }
    current_actors_[env_id] = states_[env_id].current_actor_id;
}

void EnvPool::generate_observation(int env_id) {
    make_observation(states_[env_id], states_[env_id].current_actor_id, obs_buffers_[env_id]);
}


