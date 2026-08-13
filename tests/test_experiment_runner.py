from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def load_runner_module():
    script = Path(__file__).parents[1] / "scripts" / "run_experiment.py"
    spec = importlib.util.spec_from_file_location("run_experiment", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_experiment(root: Path) -> None:
    experiment = root / "experiments" / "reward_shaping"
    (experiment / "baseline").mkdir(parents=True)
    (experiment / "hp_mp").mkdir()
    (experiment / "common.toml").write_text(
        """
schema_version = 1
experiment = "reward_shaping"

[pairing]
variants = ["baseline", "hp_mp"]
primary_seed = 42

[training]
total_timesteps = 5000000

[reward_shaping]
shape_hp = 0.2
shape_mp = 0.0
shape_money = 0.0
shape_hand = 0.0
""",
        encoding="utf-8",
    )
    (experiment / "baseline" / "variant.toml").write_text(
        """
schema_version = 1
experiment = "reward_shaping"
variant = "baseline"
""",
        encoding="utf-8",
    )
    (experiment / "hp_mp" / "variant.toml").write_text(
        """
schema_version = 1
experiment = "reward_shaping"
variant = "hp_mp"

[reward_shaping]
shape_mp = 0.05
shape_money = 0.01
""",
        encoding="utf-8",
    )


def test_reward_shaping_variant_overrides_common_values(tmp_path: Path) -> None:
    runner = load_runner_module()
    write_experiment(tmp_path)

    definition = runner.load_experiment(tmp_path, "reward_shaping")
    baseline = runner.resolve_variant_config(definition, definition.variants[0], {})
    hp_mp = runner.resolve_variant_config(definition, definition.variants[1], {})

    assert [variant.name for variant in definition.variants] == ["baseline", "hp_mp"]
    assert baseline["shape_hp"] == 0.2
    assert baseline["shape_mp"] == 0.0
    assert hp_mp["shape_hp"] == 0.2
    assert hp_mp["shape_mp"] == 0.05
    assert hp_mp["shape_money"] == 0.01


def test_environment_override_is_shared_before_variant_difference(tmp_path: Path) -> None:
    runner = load_runner_module()
    write_experiment(tmp_path)

    definition = runner.load_experiment(tmp_path, "reward_shaping")
    environment = {"TIMESTEPS": "10000", "SHAPE_HP": "0.3", "SEED": "43"}
    baseline = runner.resolve_variant_config(definition, definition.variants[0], environment)
    hp_mp = runner.resolve_variant_config(definition, definition.variants[1], environment)

    assert baseline["total_timesteps"] == hp_mp["total_timesteps"] == 10000
    assert baseline["seed"] == hp_mp["seed"] == 43
    assert baseline["shape_hp"] == hp_mp["shape_hp"] == 0.3
    assert baseline["shape_mp"] == 0.0
    assert hp_mp["shape_mp"] == 0.05


def test_boolean_override_becomes_training_flag(tmp_path: Path) -> None:
    runner = load_runner_module()
    write_experiment(tmp_path)
    variant_path = tmp_path / "experiments" / "reward_shaping" / "hp_mp" / "variant.toml"
    variant_path.write_text(
        variant_path.read_text(encoding="utf-8") + "\n[overrides]\nprivileged_critic = true\n",
        encoding="utf-8",
    )

    definition = runner.load_experiment(tmp_path, "reward_shaping")
    config = runner.resolve_variant_config(definition, definition.variants[1], {})

    assert config["privileged_critic"] is True
    assert "--privileged-critic" in runner.training_args(config)
