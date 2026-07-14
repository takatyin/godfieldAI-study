#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include "vector_env.h"

namespace py = pybind11;

PYBIND11_MODULE(godfield_core, m) {
    m.doc() = "GodField RL Core Environment (C++)";

    py::class_<godfield::VectorEnv>(m, "VectorEnv")
        .def(py::init<int>(), py::arg("num_envs"))
        .def("reset", &godfield::VectorEnv::reset)
        .def("step", &godfield::VectorEnv::step)
        .def("get_state_json", &godfield::VectorEnv::get_state_json, py::arg("env_index"));
}
