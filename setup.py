import sys

import pybind11
from setuptools import Extension, setup

# Platform-specific flags
if sys.platform == "win32":
    extra_compile_args = ["/std:c++17", "/O2", "/utf-8", "/MP"]
else:
    extra_compile_args = ["-std=c++17", "-O3"]

ext_modules = [
    Extension(
        "godfield_core",
        [
            "godfield_core/src/env_pool.cpp",
            "godfield_core/src/game_logic.cpp",
            "godfield_core/src/card_registry.cpp",
            "godfield_core/src/combat_resolution.cpp",
            "godfield_core/src/phase_handlers.cpp",
            "godfield_core/src/legal_actions.cpp",
            "godfield_core/src/bindings.cpp",
        ],
        include_dirs=[pybind11.get_include(), "godfield_core/src"],
        language="c++",
        extra_compile_args=extra_compile_args,
    ),
]

setup(
    name="godfield_rl",
    version="0.1.0",
    packages=["godfield_rl"],
    ext_modules=ext_modules,
)
