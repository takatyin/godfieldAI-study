#pragma once
#include "state.h"
#include <vector>
#include <pybind11/numpy.h>

namespace godfield {

class VectorEnv {
private:
    int num_envs;
    std::vector<GameState> envs;
    static const int OBS_SIZE = 30;

public:
    VectorEnv(int num_envs);
    
    void reset(pybind11::array_t<float>& obs_p0, pybind11::array_t<float>& obs_p1);
    
    void step(
        pybind11::array_t<int>& actions_p0,
        pybind11::array_t<int>& actions_p1,
        pybind11::array_t<float>& obs_p0,
        pybind11::array_t<float>& obs_p1,
        pybind11::array_t<float>& rewards_p0,
        pybind11::array_t<float>& rewards_p1,
        pybind11::array_t<bool>& dones
    );
    
    std::string get_state_json(int env_index) const;
};

}
