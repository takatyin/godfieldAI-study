#include "vector_env.h"
#include <pybind11/pybind11.h>

namespace godfield {

VectorEnv::VectorEnv(int num_envs) : num_envs(num_envs), envs(num_envs) {
}

void VectorEnv::reset(pybind11::array_t<float>& obs_p0, pybind11::array_t<float>& obs_p1) {
    auto obs_p0_buf = obs_p0.mutable_unchecked<2>();
    auto obs_p1_buf = obs_p1.mutable_unchecked<2>();
    
    for (int i = 0; i < num_envs; ++i) {
        envs[i].reset();
        envs[i].get_observation(0, &obs_p0_buf(i, 0));
        envs[i].get_observation(1, &obs_p1_buf(i, 0));
    }
}

void VectorEnv::step(
    pybind11::array_t<int>& actions_p0,
    pybind11::array_t<int>& actions_p1,
    pybind11::array_t<float>& obs_p0,
    pybind11::array_t<float>& obs_p1,
    pybind11::array_t<float>& rewards_p0,
    pybind11::array_t<float>& rewards_p1,
    pybind11::array_t<bool>& dones) {
    
    auto a0_buf = actions_p0.unchecked<2>();
    auto a1_buf = actions_p1.unchecked<2>();
    
    auto obs_p0_buf = obs_p0.mutable_unchecked<2>();
    auto obs_p1_buf = obs_p1.mutable_unchecked<2>();
    
    auto r0_buf = rewards_p0.mutable_unchecked<1>();
    auto r1_buf = rewards_p1.mutable_unchecked<1>();
    
    auto done_buf = dones.mutable_unchecked<1>();
    
    // For multithreading: #pragma omp parallel for
    for (int i = 0; i < num_envs; ++i) {
        if (envs[i].is_done()) {
            envs[i].reset();
        }
        
        int act0[4] = {a0_buf(i, 0), a0_buf(i, 1), a0_buf(i, 2), a0_buf(i, 3)};
        int act1[4] = {a1_buf(i, 0), a1_buf(i, 1), a1_buf(i, 2), a1_buf(i, 3)};
        
        envs[i].step(act0, act1);
        
        envs[i].get_observation(0, &obs_p0_buf(i, 0));
        envs[i].get_observation(1, &obs_p1_buf(i, 0));
        
        bool done = envs[i].is_done();
        done_buf(i) = done;
        
        if (done) {
            r0_buf(i) = (envs[i].players[0].hp > 0) ? 1.0f : -1.0f;
            r1_buf(i) = (envs[i].players[1].hp > 0) ? 1.0f : -1.0f;
            if (envs[i].players[0].hp <= 0 && envs[i].players[1].hp <= 0) {
                r0_buf(i) = 0.0f;
            }
        } else {
            r0_buf(i) = 0.0f;
            r1_buf(i) = 0.0f;
        }
    }
}

std::string VectorEnv::get_state_json(int env_index) const {
    if (env_index < 0 || env_index >= num_envs) return "{}";
    return envs[env_index].get_state_json();
}

}
