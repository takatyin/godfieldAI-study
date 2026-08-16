#!/usr/bin/env python3
"""TOMLで定義された比較実験を同一条件・指定GPU群で実行する。"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from godfield_rl.config import TrainingConfig  # noqa: E402

NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")
CONFIG_SECTIONS = ("training", "reward_shaping", "network", "opponent")
NETWORK_METADATA_KEYS = {"feature_extractor"}
MANAGED_CONFIG_KEYS = {"seed", "tensorboard_log", "save_path", "wandb_name"}
ENV_ALIASES = {
    "TIMESTEPS": "total_timesteps",
    "HAND_VALUE_WEIGHT": "shape_hand",
}
FORBIDDEN_EXTRA_ARGS = {
    "--seed",
    "--tensorboard-log",
    "--save-path",
    "--wandb-name",
}


@dataclass(frozen=True)
class VariantDefinition:
    name: str
    path: Path
    raw: dict[str, Any]
    overrides: dict[str, Any]
    extra_args: tuple[str, ...]


@dataclass(frozen=True)
class ExperimentDefinition:
    name: str
    directory: Path
    common_path: Path
    common: dict[str, Any]
    variants: tuple[VariantDefinition, ...]
    base_config: dict[str, Any]


@dataclass
class RunState:
    index: int
    variant: VariantDefinition
    gpu: str
    run_id: str
    run_dir: Path
    config: dict[str, Any]
    command: list[str]
    environment: dict[str, str]
    hand_value_checkpoint: Path | None = None
    hand_value_checkpoint_sha256: str = ""
    process: subprocess.Popen[str] | None = None
    log_file: Any = None
    log_thread: threading.Thread | None = None
    finalized: bool = False


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_iso(value: datetime | None = None) -> str:
    return (value or utc_now()).strftime("%Y-%m-%dT%H:%M:%SZ")


def validate_name(kind: str, value: str) -> None:
    if not NAME_RE.fullmatch(value):
        raise ValueError(f"{kind} must match {NAME_RE.pattern!r}: {value!r}")


def load_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as file:
            return tomllib.load(file)
    except FileNotFoundError as exc:
        raise ValueError(f"definition does not exist: {path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"invalid TOML in {path}: {exc}") from exc


def config_defaults() -> dict[str, Any]:
    defaults = TrainingConfig()
    return {field.name: getattr(defaults, field.name) for field in dataclasses.fields(defaults)}


def extract_config_values(data: dict[str, Any], source: Path) -> dict[str, Any]:
    """既知の意味別sectionと[overrides]をTrainingConfigのキーへ変換する。"""

    known = config_defaults()
    values: dict[str, Any] = {}
    for section_name in CONFIG_SECTIONS:
        section = data.get(section_name, {})
        if not isinstance(section, dict):
            raise ValueError(f"{source}: [{section_name}] must be a table")
        for key, value in section.items():
            resolved_key = "opponent" if section_name == "opponent" and key == "kind" else key
            if section_name == "network" and key in NETWORK_METADATA_KEYS:
                continue
            if resolved_key not in known:
                raise ValueError(f"{source}: [{section_name}].{key} is not a TrainingConfig field")
            values[resolved_key] = value

    overrides = data.get("overrides", {})
    if not isinstance(overrides, dict):
        raise ValueError(f"{source}: [overrides] must be a table")
    for key, value in overrides.items():
        if isinstance(value, dict):
            raise ValueError(f"{source}: [overrides].{key} must be a scalar or array")
        if key not in known:
            raise ValueError(f"{source}: [overrides].{key} is not a TrainingConfig field")
        values[key] = value

    logging = data.get("logging", {})
    if not isinstance(logging, dict):
        raise ValueError(f"{source}: [logging] must be a table")
    for key in ("wandb", "wandb_project"):
        if key in logging:
            values[key] = logging[key]
    return values


def parse_extra_args(data: dict[str, Any], source: Path) -> tuple[str, ...]:
    cli = data.get("cli", {})
    if not isinstance(cli, dict):
        raise ValueError(f"{source}: [cli] must be a table")
    extra_args = cli.get("extra_args", [])
    if not isinstance(extra_args, list) or not all(isinstance(arg, str) for arg in extra_args):
        raise ValueError(f"{source}: [cli].extra_args must be an array of strings")
    forbidden = {
        arg for arg in extra_args if arg.split("=", 1)[0] in FORBIDDEN_EXTRA_ARGS
    }
    if forbidden:
        raise ValueError(f"{source}: runner-managed arguments are forbidden in extra_args: {sorted(forbidden)}")
    return tuple(extra_args)


def load_experiment(root: Path, experiment: str) -> ExperimentDefinition:
    validate_name("experiment", experiment)
    directory = root / "experiments" / experiment
    common_path = directory / "common.toml"
    common = load_toml(common_path)
    declared_experiment = common.get("experiment")
    if declared_experiment != experiment:
        raise ValueError(
            f"{common_path}: experiment must be {experiment!r} (got {declared_experiment!r})"
        )

    pairing = common.get("pairing", {})
    if not isinstance(pairing, dict):
        raise ValueError(f"{common_path}: [pairing] must be a table")
    variant_names = pairing.get("variants")
    if variant_names is None:
        variant_names = sorted(
            path.parent.name for path in directory.glob("*/variant.toml") if path.parent.is_dir()
        )
    if (
        not isinstance(variant_names, list)
        or not variant_names
        or not all(isinstance(name, str) for name in variant_names)
    ):
        raise ValueError(f"{common_path}: pairing.variants must be a non-empty array of strings")
    if len(set(variant_names)) != len(variant_names):
        raise ValueError(f"{common_path}: pairing.variants contains duplicates")

    variants: list[VariantDefinition] = []
    for name in variant_names:
        validate_name("variant", name)
        path = directory / name / "variant.toml"
        raw = load_toml(path)
        if raw.get("experiment") != experiment or raw.get("variant") != name:
            raise ValueError(f"{path}: experiment/variant identity does not match its directory")
        overrides = extract_config_values(raw, path)
        if MANAGED_CONFIG_KEYS.intersection(overrides):
            keys = sorted(MANAGED_CONFIG_KEYS.intersection(overrides))
            raise ValueError(f"{path}: runner-managed config cannot be overridden by a variant: {keys}")
        variants.append(
            VariantDefinition(
                name=name,
                path=path,
                raw=raw,
                overrides=overrides,
                extra_args=parse_extra_args(raw, path),
            )
        )

    base_config = config_defaults()
    base_config.update(extract_config_values(common, common_path))
    return ExperimentDefinition(
        name=experiment,
        directory=directory,
        common_path=common_path,
        common=common,
        variants=tuple(variants),
        base_config=base_config,
    )


def parse_env_value(name: str, raw: str, default: Any) -> Any:
    if isinstance(default, bool):
        normalized = raw.lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        raise ValueError(f"{name} must be a boolean (got {raw!r})")
    if isinstance(default, int) and not isinstance(default, bool):
        try:
            return int(raw)
        except ValueError as exc:
            raise ValueError(f"{name} must be an integer (got {raw!r})") from exc
    if isinstance(default, float):
        try:
            return float(raw)
        except ValueError as exc:
            raise ValueError(f"{name} must be numeric (got {raw!r})") from exc
    return raw


def common_env_overrides(base: dict[str, Any], environ: dict[str, str]) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    aliases = {key.upper(): key for key in base}
    aliases.update(ENV_ALIASES)
    for env_name, config_key in aliases.items():
        if env_name in environ:
            overrides[config_key] = parse_env_value(env_name, environ[env_name], base[config_key])
    return overrides


def resolve_variant_config(
    definition: ExperimentDefinition, variant: VariantDefinition, environ: dict[str, str]
) -> dict[str, Any]:
    resolved = dict(definition.base_config)
    resolved.update(common_env_overrides(resolved, environ))
    resolved.update(variant.overrides)
    pairing = definition.common.get("pairing", {})
    default_seed = pairing.get("primary_seed", resolved["seed"])
    resolved["seed"] = parse_env_value("SEED", environ.get("SEED", str(default_seed)), resolved["seed"])
    defaults = config_defaults()
    for key, value in resolved.items():
        default = defaults[key]
        if isinstance(default, bool) and not isinstance(value, bool):
            raise ValueError(f"{variant.path}: {key} must be a boolean")
        if isinstance(default, int) and not isinstance(default, bool):
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(f"{variant.path}: {key} must be an integer")
        if isinstance(default, float):
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ValueError(f"{variant.path}: {key} must be numeric")
        if isinstance(default, str) and not isinstance(value, str):
            raise ValueError(f"{variant.path}: {key} must be a string")
        if default is None and value is not None and not isinstance(value, str):
            raise ValueError(f"{variant.path}: {key} must be a string")
    for key in (
        "num_envs",
        "total_timesteps",
        "n_steps",
        "batch_size",
        "n_epochs",
        "d_model",
        "nhead",
        "num_layers",
        "dim_feedforward",
        "features_dim",
    ):
        if resolved[key] <= 0:
            raise ValueError(f"{variant.path}: {key} must be positive")
    if resolved["seed"] < 0:
        raise ValueError(f"{variant.path}: seed must be non-negative")
    try:
        validated = TrainingConfig(**resolved)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{variant.path}: invalid resolved training config: {exc}") from exc
    return {field.name: getattr(validated, field.name) for field in dataclasses.fields(validated)}


def training_args(config: dict[str, Any]) -> list[str]:
    defaults = config_defaults()
    args: list[str] = []
    for key, value in config.items():
        if key in {"tensorboard_log", "save_path", "wandb_name"} or value is None:
            continue
        flag = "--" + key.replace("_", "-")
        if isinstance(value, bool):
            if value == defaults[key]:
                continue
            args.append(flag if value else "--no-" + key.replace("_", "-"))
        else:
            args.extend((flag, str(value)))
    return args


def parse_gpu_ids(raw: str, variant_count: int, dry_run: bool) -> list[str]:
    if not raw:
        if dry_run:
            return [f"<gpu-{index}>" for index in range(variant_count)]
        raise ValueError(
            "set GPU_IDS to one or more comma-separated GPU IDs "
            "(for example GPU_IDS=0 or GPU_IDS=0,1)"
        )
    gpu_ids = [gpu.strip() for gpu in raw.split(",")]
    if any(not gpu.isdigit() for gpu in gpu_ids):
        raise ValueError(f"GPU_IDS must contain only non-negative integers (got {raw!r})")
    if len(set(gpu_ids)) != len(gpu_ids):
        raise ValueError(f"GPU_IDS contains duplicates (got {raw!r})")
    return gpu_ids


def assign_gpus(gpu_ids: list[str], variant_count: int) -> list[str]:
    """variantを指定GPUへround-robinで割り当てる。"""

    if not gpu_ids:
        raise ValueError("at least one GPU ID is required")
    return [gpu_ids[index % len(gpu_ids)] for index in range(variant_count)]


def relay_process_output(
    stream: Any,
    log_file: Any,
    prefix: str,
    terminal: Any,
    output_lock: threading.Lock,
) -> None:
    """子プロセスの出力を生ログへ保存しつつ、識別子付きで端末へ中継する。"""

    try:
        for line in stream:
            log_file.write(line)
            log_file.flush()
            with output_lock:
                terminal.write(f"{prefix} {line}")
                terminal.flush()
    finally:
        stream.close()


def gpu_preflight(python: Path, gpu: str) -> dict[str, str]:
    code = """
import json, platform, torch
if not torch.cuda.is_available():
    raise SystemExit("CUDA is unavailable for the requested GPU")
if torch.cuda.device_count() != 1:
    raise SystemExit(f"expected exactly one visible GPU, got {torch.cuda.device_count()}")
print(json.dumps({
    "python_version": platform.python_version(),
    "torch_version": torch.__version__,
    "torch_cuda_version": torch.version.cuda or "unknown",
    "gpu_name": torch.cuda.get_device_name(0),
}))
"""
    environment = os.environ.copy()
    environment["CUDA_VISIBLE_DEVICES"] = gpu
    result = subprocess.run(
        [str(python), "-c", code],
        cwd=REPO_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise ValueError(f"CUDA preflight failed for GPU {gpu}: {detail}")
    return json.loads(result.stdout)


def git_output(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True).strip()


def toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if value is None:
        return '""'
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(toml_value(item) for item in value) + "]"
    raise TypeError(f"unsupported TOML metadata value: {value!r}")


def append_toml_table(lines: list[str], name: str, values: dict[str, Any]) -> None:
    lines.extend((f"[{name}]",))
    for key, value in values.items():
        if isinstance(value, dict):
            continue
        lines.append(f"{key} = {toml_value(value)}")
    lines.append("")


def write_atomic(path: Path, text: str) -> None:
    temporary = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def display_path(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def resolve_hand_value_checkpoint(root: Path, config: dict[str, Any]) -> Path | None:
    """hand shaping有効時に最新連番runのbest checkpointを検証します。"""
    if config["shape_hand"] == 0.0:
        return None

    model_dir = Path(config["hand_value_model_dir"]).expanduser()
    if not model_dir.is_absolute():
        model_dir = root / model_dir
    model_dir = model_dir.resolve()

    candidates: list[tuple[int, Path]] = []
    for path in model_dir.glob("hand_value_model_*"):
        suffix = path.name.removeprefix("hand_value_model_")
        if path.is_dir() and suffix.isdigit():
            candidates.append((int(suffix), path))
    if not candidates:
        raise ValueError(f"hand value model run not found under: {model_dir}")

    _, latest_run = max(candidates, key=lambda item: item[0])
    checkpoint = latest_run / "best_model.pt"
    if not checkpoint.is_file():
        raise ValueError(f"best hand value model not found: {checkpoint}")
    return checkpoint


def build_metadata(
    state: RunState,
    definition: ExperimentDefinition,
    pair_id: str,
    run_kind: str,
    started_at: str,
    status: str,
    finished_at: str,
    exit_code: int,
    source: dict[str, Any],
    gpu_info: dict[str, str],
    model_sha: str,
    note: str,
) -> str:
    relative_dir = state.run_dir.relative_to(REPO_ROOT).as_posix()
    lines = [
        "schema_version = 1",
        f"run_id = {toml_value(state.run_id)}",
        f"pair_id = {toml_value(pair_id)}",
        f"experiment = {toml_value(definition.name)}",
        f"variant = {toml_value(state.variant.name)}",
        f"run_kind = {toml_value(run_kind)}",
        f"status = {toml_value(status)}",
        f"started_at_utc = {toml_value(started_at)}",
        f"finished_at_utc = {toml_value(finished_at)}",
        f"exit_code = {exit_code}",
        "",
    ]
    append_toml_table(lines, "source", source)
    append_toml_table(lines, "resolved_training", state.config)
    if state.hand_value_checkpoint is not None:
        append_toml_table(
            lines,
            "hand_value_model",
            {
                "checkpoint": display_path(state.hand_value_checkpoint),
                "sha256": state.hand_value_checkpoint_sha256,
                "weight": state.config["shape_hand"],
                "clip_value": state.config["hand_value_clip_value"],
            },
        )
    inherited = definition.common.get("ppo_inherited_defaults", {})
    if inherited:
        append_toml_table(lines, "inherited_ppo_defaults", inherited)
    evaluation = dict(definition.common.get("evaluation", {}))
    seed_offset = evaluation.pop("seed_offset_from_training", 0)
    evaluation["seed"] = state.config["seed"] + seed_offset
    append_toml_table(lines, "resolved_evaluation", evaluation)
    append_toml_table(
        lines,
        "environment",
        {
            "python_executable": ".venv/bin/python",
            **gpu_info,
            "requested_gpu_id": state.gpu,
            "visible_cuda_device": "cuda:0",
        },
    )
    append_toml_table(
        lines,
        "artifacts",
        {
            "directory": relative_dir,
            "model": f"{relative_dir}/checkpoints/final_model.zip",
            "model_sha256": model_sha,
            "tensorboard": f"{relative_dir}/tensorboard",
            "stdout_log": f"{relative_dir}/logs/train.log",
            "command_log": f"{relative_dir}/logs/command.log",
            "eval_log": f"{relative_dir}/logs/eval.log",
            "wandb_run": "",
        },
    )
    append_toml_table(lines, "notes", {"text": note})
    return "\n".join(lines)


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TOMLで定義した比較実験を指定GPU群で実行する")
    parser.add_argument("experiment", help="experiments/以下の実験名（例: privileged_critic）")
    parser.add_argument(
        "--variant",
        action="append",
        dest="variants",
        metavar="NAME",
        help="実行するvariant名。省略時は定義済みの全variantを実行する（複数回指定可）",
    )
    parser.add_argument("--dry-run", action="store_true", help="設定とコマンドを検証・表示し、GPUや出力を変更しない")
    return parser


def select_variants(
    definition: ExperimentDefinition, requested: list[str] | None
) -> ExperimentDefinition:
    if not requested:
        return definition
    if len(set(requested)) != len(requested):
        raise ValueError("--variant contains duplicates")

    variants_by_name = {variant.name: variant for variant in definition.variants}
    unknown = [name for name in requested if name not in variants_by_name]
    if unknown:
        available = ", ".join(variants_by_name)
        raise ValueError(
            f"unknown variant(s): {', '.join(unknown)} (available: {available})"
        )
    return dataclasses.replace(
        definition,
        variants=tuple(variants_by_name[name] for name in requested),
    )


def main() -> int:
    args = create_parser().parse_args()
    dry_run = args.dry_run or os.environ.get("DRY_RUN") == "1"
    run_kind = os.environ.get("RUN_KIND", "full")
    if run_kind not in {"full", "smoke_test"}:
        raise ValueError(f"RUN_KIND must be 'full' or 'smoke_test' (got {run_kind!r})")

    definition = select_variants(
        load_experiment(REPO_ROOT, args.experiment), args.variants
    )
    python = REPO_ROOT / ".venv" / "bin" / "python"
    if not python.is_file() and not dry_run:
        raise ValueError(f"expected executable Python at {python}")
    gpu_ids = parse_gpu_ids(os.environ.get("GPU_IDS", ""), len(definition.variants), dry_run)
    assigned_gpu_ids = assign_gpus(gpu_ids, len(definition.variants))
    startup_check_sec = int(os.environ.get("STARTUP_CHECK_SEC", "10"))
    if startup_check_sec < 0:
        raise ValueError("STARTUP_CHECK_SEC must be non-negative")

    resolved = [resolve_variant_config(definition, variant, os.environ) for variant in definition.variants]
    hand_value_checkpoints = [
        resolve_hand_value_checkpoint(REPO_ROOT, config) for config in resolved
    ]
    started = utc_now()
    compact = started.strftime("%Y%m%dT%H%M%SZ")
    started_iso = utc_iso(started)
    seed = resolved[0]["seed"]
    if any(config["seed"] != seed for config in resolved):
        raise ValueError("all variants in a comparison must use the same seed")
    pair_id = f"{definition.name}_s{seed}_{compact}"

    states: list[RunState] = []
    for index, (variant, gpu, config, hand_value_checkpoint) in enumerate(
        zip(
            definition.variants,
            assigned_gpu_ids,
            resolved,
            hand_value_checkpoints,
            strict=True,
        )
    ):
        run_id = f"{definition.name}_{variant.name}_s{seed}_{compact}"
        run_dir = REPO_ROOT / "runs" / definition.name / run_id
        command = [str(python), str(REPO_ROOT / "train.py"), *training_args(config)]
        command.extend(
            (
                "--tensorboard-log",
                str(run_dir / "tensorboard"),
                "--save-path",
                str(run_dir / "checkpoints" / "final_model"),
            )
        )
        if config["wandb"]:
            command.extend(("--wandb-name", run_id))
        command.extend(variant.extra_args)
        environment = os.environ.copy()
        environment["CUDA_VISIBLE_DEVICES"] = gpu
        environment["PYTHONUNBUFFERED"] = "1"
        states.append(
            RunState(
                index=index,
                variant=variant,
                gpu=gpu,
                run_id=run_id,
                run_dir=run_dir,
                config=config,
                command=command,
                environment=environment,
                hand_value_checkpoint=hand_value_checkpoint,
                hand_value_checkpoint_sha256=(
                    sha256_file(hand_value_checkpoint)
                    if hand_value_checkpoint is not None
                    else ""
                ),
            )
        )

    print(f"Experiment: {definition.name}")
    print(f"  comparison : {pair_id}")
    print(f"  variants   : {', '.join(variant.name for variant in definition.variants)}")
    print(f"  GPUs       : {', '.join(gpu_ids)}")
    print(f"  conditions : seed={seed} run_kind={run_kind}")
    for state in states:
        print(f"  {state.variant.name}: GPU {state.gpu} -> {state.run_dir.relative_to(REPO_ROOT)}")
        if state.hand_value_checkpoint is not None:
            print(
                "    hand value: "
                f"{display_path(state.hand_value_checkpoint)} "
                f"(weight={state.config['shape_hand']}, "
                f"clip={state.config['hand_value_clip_value']})"
            )
        print(f"    CUDA_VISIBLE_DEVICES={shlex.quote(state.gpu)} {shlex.join(state.command)}")
    if len(gpu_ids) > len(definition.variants):
        unused = gpu_ids[len(definition.variants) :]
        print(f"  unused GPUs: {', '.join(unused)} (there are fewer variants than GPUs)")
    if dry_run:
        print("Dry run complete; no GPU checks, directories, or processes were created.")
        return 0

    results_dir = definition.directory / "results"
    for state in states:
        result_meta = results_dir / f"{state.run_id}.toml"
        if state.run_dir.exists() or result_meta.exists():
            raise ValueError(f"refusing to overwrite existing run: {state.run_id}")

    used_gpu_ids = list(dict.fromkeys(state.gpu for state in states))
    gpu_details = {gpu: gpu_preflight(python, gpu) for gpu in used_gpu_ids}
    git_commit = git_output("rev-parse", "HEAD")
    git_branch = git_output("branch", "--show-current") or "DETACHED"
    git_dirty = bool(git_output("status", "--porcelain", "--untracked-files=normal"))
    lockfile = REPO_ROOT / "uv.lock"
    lock_sha = sha256_file(lockfile) if lockfile.exists() else ""
    results_dir.mkdir(parents=True, exist_ok=True)

    def metadata_source(state: RunState) -> dict[str, Any]:
        return {
            "git_commit": git_commit,
            "git_branch": git_branch,
            "working_tree_dirty": git_dirty,
            "uv_lock_sha256": lock_sha,
            "common_definition": definition.common_path.relative_to(REPO_ROOT).as_posix(),
            "variant_definition": state.variant.path.relative_to(REPO_ROOT).as_posix(),
        }

    def update_metadata(
        state: RunState, status: str, exit_code: int, model_sha: str = "", note: str = "", finished: str = ""
    ) -> None:
        text = build_metadata(
            state,
            definition,
            pair_id,
            run_kind,
            started_iso,
            status,
            finished,
            exit_code,
            metadata_source(state),
            gpu_details[state.gpu],
            model_sha,
            note,
        )
        write_atomic(state.run_dir / "run_meta.toml", text)
        write_atomic(results_dir / f"{state.run_id}.toml", text)

    for state in states:
        state.run_dir.mkdir(parents=True)
        for child in ("checkpoints", "logs", "tensorboard", "definitions"):
            (state.run_dir / child).mkdir()
        (state.run_dir / "definitions" / "common.toml").write_bytes(definition.common_path.read_bytes())
        (state.run_dir / "definitions" / "variant.toml").write_bytes(state.variant.path.read_bytes())
        command_text = f"CUDA_VISIBLE_DEVICES={shlex.quote(state.gpu)} {shlex.join(state.command)}\n"
        (state.run_dir / "logs" / "command.log").write_text(command_text, encoding="utf-8")
        update_metadata(state, "running", -1)

    stopping = False
    output_lock = threading.Lock()

    def terminal_print(message: str, *, error: bool = False) -> None:
        with output_lock:
            print(message, file=sys.stderr if error else sys.stdout, flush=True)

    def finish_output(state: RunState) -> None:
        if state.log_thread is not None:
            state.log_thread.join()
            state.log_thread = None
        if state.log_file is not None:
            state.log_file.close()
            state.log_file = None

    def stop_all(signum: int | None = None, _frame: Any = None) -> None:
        nonlocal stopping
        if stopping:
            return
        stopping = True
        for state in states:
            if state.process is not None and state.process.poll() is None:
                state.process.terminate()
        deadline = time.monotonic() + 10
        for state in states:
            if state.process is None or state.process.poll() is not None:
                continue
            try:
                state.process.wait(timeout=max(0.0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                state.process.kill()
                state.process.wait()
        for state in states:
            finish_output(state)
        for state in states:
            if state.finalized:
                continue
            if state.process is None:
                return_code = -1
            else:
                return_code = state.process.returncode if state.process.returncode is not None else -1
            if state.run_dir.exists():
                update_metadata(
                    state,
                    "interrupted",
                    return_code,
                    note="comparison stopped before all variants completed",
                    finished=utc_iso(),
                )
                state.finalized = True
        if signum is not None:
            raise KeyboardInterrupt

    for caught_signal in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(caught_signal, stop_all)

    try:
        queued = list(range(len(states)))
        running: set[int] = set()

        def start_available() -> None:
            busy_gpus = {states[index].gpu for index in running}
            for index in list(queued):
                state = states[index]
                if state.gpu in busy_gpus:
                    continue
                queued.remove(index)
                busy_gpus.add(state.gpu)
                running.add(index)
                state.log_file = (state.run_dir / "logs" / "train.log").open("w", encoding="utf-8")
                state.process = subprocess.Popen(
                    state.command,
                    cwd=REPO_ROOT,
                    env=state.environment,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                if state.process.stdout is None:
                    raise OSError("failed to capture training process output")
                prefix = f"[{state.variant.name}|GPU {state.gpu}]"
                state.log_thread = threading.Thread(
                    target=relay_process_output,
                    args=(state.process.stdout, state.log_file, prefix, sys.stdout, output_lock),
                    name=f"log-{state.variant.name}",
                    daemon=True,
                )
                state.log_thread.start()
                terminal_print(f"Started {state.variant.name} on GPU {state.gpu} (pid={state.process.pid})")

        start_available()

        initial_running = set(running)
        deadline = time.monotonic() + startup_check_sec
        while time.monotonic() < deadline and all(
            states[index].process.poll() is None for index in initial_running
        ):
            time.sleep(min(0.2, max(0.0, deadline - time.monotonic())))
        early_failure = next(
            (
                states[index]
                for index in initial_running
                if states[index].process.poll() not in (None, 0)
            ),
            None,
        )
        if early_failure is not None:
            finish_output(early_failure)
            terminal_print(
                f"error: {early_failure.variant.name} failed during startup "
                f"(exit={early_failure.process.returncode})",
                error=True,
            )
            update_metadata(
                early_failure,
                "failed",
                early_failure.process.returncode,
                note="training command failed during startup; see logs/train.log",
                finished=utc_iso(),
            )
            early_failure.finalized = True
            stop_all()
            return 1

        while running:
            completed_any = False
            for index in list(running):
                state = states[index]
                return_code = state.process.poll()
                if return_code is None:
                    continue
                completed_any = True
                running.remove(index)
                finish_output(state)
                model_path = state.run_dir / "checkpoints" / "final_model.zip"
                event_exists = any((state.run_dir / "tensorboard").glob("**/events.out.tfevents.*"))
                if return_code == 0 and model_path.is_file() and event_exists:
                    final_status = "smoke_test" if run_kind == "smoke_test" else "completed"
                    update_metadata(
                        state,
                        final_status,
                        0,
                        sha256_file(model_path),
                        "artifacts validated",
                        utc_iso(),
                    )
                    state.finalized = True
                    terminal_print(f"{state.variant.name}: completed and artifacts validated")
                    continue
                if return_code == 0:
                    return_code = 66 if not model_path.is_file() else 67
                    note = "training exited successfully but required artifacts are missing"
                else:
                    note = "training command exited non-zero; see logs/train.log"
                update_metadata(state, "failed", return_code, note=note, finished=utc_iso())
                state.finalized = True
                terminal_print(f"error: {state.variant.name} failed (exit={return_code})", error=True)
                stop_all()
                return 1

            if completed_any:
                start_available()
            else:
                time.sleep(0.2)
    except KeyboardInterrupt:
        stop_all()
        return 130
    except OSError as exc:
        print(f"error: failed to start training process: {exc}", file=sys.stderr)
        stop_all()
        return 1
    finally:
        for state in states:
            finish_output(state)

    print(f"Comparison complete. View: .venv/bin/tensorboard --logdir runs/{definition.name}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
