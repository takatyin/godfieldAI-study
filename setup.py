import os
import platform
import sys

import pybind11
from setuptools import Extension, setup

# ビルドしたマシンのCPUに固有の命令を埋め込む -march=native は、別のマシンで実行すると
# 不正命令で異常終了する原因になる。Windows 側が /arch:AVX2 と固定ターゲットを指定しているのに
# 合わせ、既定では AVX2 までに揃える。
# ビルドと実行が同一マシンで完結する環境（学習用マシンなど）では、
# GODFIELD_MARCH_NATIVE=1 を指定するとネイティブ最適化を有効にできる。
_use_native = os.environ.get("GODFIELD_MARCH_NATIVE") == "1"
_is_x86 = platform.machine().lower() in ("x86_64", "amd64", "i386", "i686", "x86")

# Platform-specific flags
if sys.platform == "win32":
    extra_compile_args = ["/std:c++17", "/O2", "/utf-8", "/MP", "/openmp"]
    if _is_x86:
        extra_compile_args.append("/arch:AVX2")
    extra_link_args = []
else:
    extra_compile_args = ["-std=c++17", "-O3", "-fopenmp"]
    extra_link_args = ["-fopenmp"]
    if _use_native:
        extra_compile_args.append("-march=native")
    elif _is_x86:
        # ARM 等には存在しないフラグなので、x86 系でのみ付与する
        extra_compile_args.append("-mavx2")

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
        extra_link_args=extra_link_args,
    ),
]

setup(
    name="godfield_rl",
    version="0.1.0",
    packages=["godfield_rl"],
    ext_modules=ext_modules,
)
