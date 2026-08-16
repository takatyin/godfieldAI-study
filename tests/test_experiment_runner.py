from __future__ import annotations

import importlib.util
import io
import sys
import threading
from pathlib import Path

import pytest


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


def test_gpu_ids_accept_any_positive_count_and_are_assigned_round_robin() -> None:
    runner = load_runner_module()

    assert runner.parse_gpu_ids("0", variant_count=2, dry_run=False) == ["0"]
    assert runner.assign_gpus(["0"], variant_count=2) == ["0", "0"]
    assert runner.parse_gpu_ids("0, 2,4", variant_count=2, dry_run=False) == ["0", "2", "4"]
    assert runner.assign_gpus(["0", "2", "4"], variant_count=5) == ["0", "2", "4", "0", "2"]


def test_relay_process_output_keeps_raw_log_and_prefixes_terminal() -> None:
    runner = load_runner_module()
    stream = io.StringIO("first\nwin_rate=75%\n")
    log_file = io.StringIO()
    terminal = io.StringIO()

    runner.relay_process_output(
        stream,
        log_file,
        "[baseline|GPU 0]",
        terminal,
        threading.Lock(),
    )

    assert log_file.getvalue() == "first\nwin_rate=75%\n"
    assert terminal.getvalue() == (
        "[baseline|GPU 0] first\n"
        "[baseline|GPU 0] win_rate=75%\n"
    )


def test_hand_value_checkpoint_uses_highest_numbered_run(tmp_path: Path) -> None:
    runner = load_runner_module()
    model_root = tmp_path / "runs" / "hand_value_model"
    older = model_root / "hand_value_model_2" / "best_model.pt"
    latest = model_root / "hand_value_model_10" / "best_model.pt"
    older.parent.mkdir(parents=True)
    latest.parent.mkdir(parents=True)
    older.write_bytes(b"older")
    latest.write_bytes(b"latest")
    config = runner.config_defaults()
    config["shape_hand"] = 0.2

    assert runner.resolve_hand_value_checkpoint(tmp_path, config) == latest


def test_hand_value_checkpoint_is_not_required_when_disabled(tmp_path: Path) -> None:
    runner = load_runner_module()
    config = runner.config_defaults()
    config["shape_hand"] = 0.0

    assert runner.resolve_hand_value_checkpoint(tmp_path, config) is None


def test_hand_value_checkpoint_missing_from_latest_run_is_an_error(
    tmp_path: Path,
) -> None:
    runner = load_runner_module()
    model_root = tmp_path / "runs" / "hand_value_model"
    older = model_root / "hand_value_model_1" / "best_model.pt"
    older.parent.mkdir(parents=True)
    older.write_bytes(b"older")
    (model_root / "hand_value_model_2").mkdir()
    config = runner.config_defaults()
    config["shape_hand"] = 0.2

    with pytest.raises(ValueError, match="best hand value model"):
        runner.resolve_hand_value_checkpoint(tmp_path, config)
