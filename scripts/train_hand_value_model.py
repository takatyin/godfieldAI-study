from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from godfield_rl.feature_config import NUM_CARD_TYPES
from godfield_rl.hand_value_dataset import (
    HandValueDataset,
    split_by_episode,
)
from godfield_rl.hand_value_model import HandValueModel

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = REPO_ROOT / "runs" / "hand_value_data"
DEFAULT_MODEL_DIR = REPO_ROOT / "runs" / "hand_value_model"


def create_run_dir() -> Path:
    DEFAULT_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    run_numbers = []
    for path in DEFAULT_MODEL_DIR.glob("hand_value_model_*"):
        suffix = path.name.removeprefix("hand_value_model_")
        if path.is_dir() and suffix.isdigit():
            run_numbers.append(int(suffix))

    run_number = max(run_numbers, default=0) + 1
    while True:
        run_dir = DEFAULT_MODEL_DIR / f"hand_value_model_{run_number}"
        try:
            run_dir.mkdir(exist_ok=False)
            return run_dir
        except FileExistsError:
            run_number += 1


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        help="学習に使う dataset.npz（省略時は最新のデータを使用）",
    )
    return parser.parse_args()


def resolve_dataset_path(dataset: Path | None) -> Path:
    if dataset is not None:
        path = dataset.expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"dataset not found: {path}")
        return path

    candidates = sorted(
        DEFAULT_DATA_DIR.glob("hand_value_data_s*/dataset.npz"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(
            f"dataset not found under: {DEFAULT_DATA_DIR}\n"
            "Run scripts/collect_hand_value_data.py first, or pass --dataset."
        )

    latest_candidates = candidates[:2]
    sample_counts = {}
    for path in latest_candidates:
        with np.load(path) as data:
            sample_counts[path] = int(data["labels"].shape[0])

    print("dataset candidates (latest two):")
    for path in latest_candidates:
        print(f"  {path}: {sample_counts[path]} samples")

    return max(latest_candidates, key=lambda path: sample_counts[path])


def main():
    args = parse_args()

    # ------------------------------------------------------------
    # データ読み込み
    # ------------------------------------------------------------
    dataset_path = resolve_dataset_path(args.dataset)
    print(f"loading: {dataset_path}")
    data = np.load(dataset_path)

    train_mask, val_mask = split_by_episode(
        data["episode_ids"],
        val_ratio=0.2,
        seed=42,
    )
    train_dataset = HandValueDataset(
        obs = data["obs"][train_mask],
        stats=data["stats"][train_mask],
        my_hands=data["my_hands"][train_mask],
        opp_hands=data["opp_hands"][train_mask],
        labels=data["labels"][train_mask],
    )

    val_dataset = HandValueDataset(
        obs = data["obs"][val_mask],
        stats=data["stats"][val_mask],
        my_hands=data["my_hands"][val_mask],
        opp_hands=data["opp_hands"][val_mask],
        labels=data["labels"][val_mask],
    )

    train_loader = DataLoader(
        train_dataset,
        batch_size=256,
        shuffle=True,
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=256,
        shuffle=False,
    )

    print(
        f"samples: train={len(train_dataset)} "
        f"validation={len(val_dataset)}"
    )

    # ------------------------------------------------------------
    # model
    # ------------------------------------------------------------
    device = torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )
    print(f"device: {device}")

    obs_dim = data["obs"].shape[1]

    model = HandValueModel(
        num_card_types=NUM_CARD_TYPES,
        obs_dim = obs_dim,
    ).to(device)

    criterion = nn.MSELoss()

    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=1e-3,
    )

    # ------------------------------------------------------------
    # 学習
    # ------------------------------------------------------------
    epochs = 30
    run_dir = create_run_dir()
    print(f"run_dir: {run_dir}")

    config = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset": str(dataset_path),
        "train_samples": len(train_dataset),
        "validation_samples": len(val_dataset),
        "validation_ratio": 0.2,
        "split_seed": 42,
        "device": str(device),
        "epochs": epochs,
        "batch_size": 256,
        "optimizer": "Adam",
        "learning_rate": 1e-3,
        "loss": "MSELoss",
        "model": "HandValueModel",
        "model_config": {
            "num_card_types": NUM_CARD_TYPES,
            "obs_dim": obs_dim,
            "stats_dim": 6,
            "hand_embed_dim": 16,
            "obs_feature_dim": 64,
            "hidden_dim": 64,
        },
    }
    write_json(run_dir / "config.json", config)

    epoch_metrics = []
    best_val_loss = float("inf")
    best_epoch = 0

    for epoch in range(epochs):
        model.train()

        train_loss_sum = 0.0
        train_value_sum = 0.0
        train_target_sum = 0.0
        train_sample_count = 0

        for batch in train_loader:
            obs = batch["obs"].to(device)
            stats = batch["stats"].to(device)
            my_hands = batch["my_hands"].to(device)
            opp_hands = batch["opp_hands"].to(device)
            labels = batch["labels"].to(device)

            optimizer.zero_grad()

            values = model(
                obs,
                stats,
                my_hands,
                opp_hands,
            )

            loss = criterion(
                values,
                labels,
            )

            loss.backward()
            optimizer.step()

            batch_size = labels.numel()
            train_loss_sum += loss.item() * batch_size
            train_value_sum += values.detach().sum().item()
            train_target_sum += labels.sum().item()
            train_sample_count += batch_size

        train_loss = train_loss_sum / train_sample_count
        train_value = train_value_sum / train_sample_count
        train_target = train_target_sum / train_sample_count

        # --------------------------------------------------------
        # validation
        # --------------------------------------------------------
        model.eval()

        val_loss_sum = 0.0
        val_value_sum = 0.0
        val_target_sum = 0.0
        val_sample_count = 0

        with torch.no_grad():
            for batch in val_loader:
                obs = batch["obs"].to(device)
                stats = batch["stats"].to(device)
                my_hands = batch["my_hands"].to(device)
                opp_hands = batch["opp_hands"].to(device)
                labels = batch["labels"].to(device)

                values = model(
                    obs,
                    stats,
                    my_hands,
                    opp_hands,
                )

                loss = criterion(
                    values,
                    labels,
                )

                batch_size = labels.numel()
                val_loss_sum += loss.item() * batch_size
                val_value_sum += values.sum().item()
                val_target_sum += labels.sum().item()
                val_sample_count += batch_size

        val_loss = val_loss_sum / val_sample_count
        val_value = val_value_sum / val_sample_count
        val_target = val_target_sum / val_sample_count

        metrics = {
            "epoch": epoch + 1,
            "train_value": train_value,
            "train_target": train_target,
            "train_loss": train_loss,
            "val_value": val_value,
            "val_target": val_target,
            "val_loss": val_loss,
        }
        epoch_metrics.append(metrics)

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_epoch = epoch + 1
            torch.save(
                {
                    "epoch": best_epoch,
                    "model_state_dict": model.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict(),
                    "metrics": metrics,
                    "model_config": config["model_config"],
                },
                run_dir / "best_model.pt",
            )

        write_json(
            run_dir / "metrics.json",
            {
                "best_epoch": best_epoch,
                "best_val_loss": best_val_loss,
                "epochs": epoch_metrics,
            },
        )

        print(
            f"epoch={epoch + 1} "
            f"train_value={train_value:+.4f} "
            f"train_target={train_target:+.4f} "
            f"train_loss={train_loss:.6f} "
            f"val_value={val_value:+.4f} "
            f"val_target={val_target:+.4f} "
            f"val_loss={val_loss:.6f}",
            flush=True,
        )

    torch.save(
        {
            "epoch": epochs,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "metrics": epoch_metrics[-1],
            "model_config": config["model_config"],
        },
        run_dir / "final_model.pt",
    )

    print(f"best model: epoch={best_epoch} val_loss={best_val_loss:.6f}")
    print(f"saved: {run_dir}")


if __name__ == "__main__":
    main()
