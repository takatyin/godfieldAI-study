from setuptools import setup, Extension
import pybind11
import sys

# Platform-specific flags
if sys.platform == "win32":
    extra_compile_args = ["/std:c++17", "/O2"]
else:
    extra_compile_args = ["-std=c++17", "-O3"]

ext_modules = [
    Extension(
        "godfield_core",
        [
            "godfield_core/src/state.cpp",
            "godfield_core/src/cards.cpp",
            "godfield_core/src/vector_env.cpp",
            "godfield_core/src/bindings.cpp",
        ],
        include_dirs=[pybind11.get_include(), "godfield_core/src"],
        language="c++",
        extra_compile_args=extra_compile_args,
    ),
]

setup(
    name="godfield_rl",
    version="0.0.1",
    packages=["godfield_rl"],
    ext_modules=ext_modules,
)
