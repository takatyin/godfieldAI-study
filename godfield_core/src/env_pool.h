#pragma once

#include "types.h"
#include <vector>
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>

/**
 * @brief 並列化管理とバッチ処理のインターフェース
 * 
 * 大量のゲーム状態を並列に保持・進行し、AI推論（判断）が必要になったタイミングでゲームをストップし、
 * 状態をキューに溜めて一気にGPU（Python側）へ投げる。
 * 推論結果のアクションを受け取って再びゲームを進める、というCPU-GPU間のバッチ化管理に特化する。
 * ゲーム固有のルールやカード情報の知識は持たない。
 */
class EnvPool {
public:
    EnvPool(int num_envs = NUM_ENVS);
    ~EnvPool();

    void reset(int seed);
    void step_all(pybind11::array_t<int> actions);
    pybind11::array_t<float> get_observations();
    pybind11::array_t<int> get_ready_env_ids();
    
    InternalState get_state(int env_id) const { return states_[env_id]; }
    void set_state(int env_id, const InternalState &state) {
        states_[env_id] = state;
        generate_observation(env_id);
    }

private:
    int num_envs_;
    std::vector<InternalState> states_;
    std::vector<Observation> obs_buffers_;
    std::vector<int> ready_env_ids_;

    // Internal helper functions for game logic
    void step_env(int env_id, int action);
    void generate_observation(int env_id);
    void check_done(int env_id);
    void flush_n_step_queue(int env_id);
};
