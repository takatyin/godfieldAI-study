from __future__ import annotations

import copy
import csv
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from godfield_rl.feature_config import NUM_CARD_TYPES
from godfield_rl.hand_value_dataset import HandValueDataset, split_by_episode
from godfield_rl.hand_value_model import HandValueModel


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "runs" / "hand_value_data"
OUTPUT_DIR = Path(__file__).resolve().parent / "calibration_results"


def latest_dataset() -> Path:
    candidates = list(DATA_DIR.glob("hand_value_data_s*/dataset.npz"))
    if not candidates:
        raise FileNotFoundError(f"No dataset found under {DATA_DIR}")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def evaluate(
    model: nn.Module,
    loader: DataLoader,
    device: torch.device,
) -> tuple[float, np.ndarray, np.ndarray]:
    model.eval()
    predictions: list[np.ndarray] = []
    targets: list[np.ndarray] = []

    with torch.no_grad():
        for batch in loader:
            values = model(
                batch["obs"].to(device),
                batch["stats"].to(device),
                batch["my_hands"].to(device),
                batch["opp_hands"].to(device),
            )
            predictions.append(values.cpu().numpy())
            targets.append(batch["labels"].numpy())

    prediction = np.concatenate(predictions).astype(np.float64)
    target = np.concatenate(targets).astype(np.float64)
    loss = float(np.mean((prediction - target) ** 2))
    return loss, prediction, target


def calibration_rows(
    prediction: np.ndarray,
    target: np.ndarray,
    num_bins: int = 10,
) -> list[dict[str, float | int]]:
    order = np.argsort(prediction)
    rows: list[dict[str, float | int]] = []

    for bin_index, indices in enumerate(np.array_split(order, num_bins), start=1):
        pred_bin = prediction[indices]
        target_bin = target[indices]
        pred_mean = float(pred_bin.mean())
        actual_mean = float(target_bin.mean())
        rows.append(
            {
                "bin": bin_index,
                "count": len(indices),
                "pred_min": float(pred_bin.min()),
                "pred_max": float(pred_bin.max()),
                "pred_mean": pred_mean,
                "actual_mean": actual_mean,
                "gap": pred_mean - actual_mean,
            }
        )

    return rows


def main() -> None:
    torch.manual_seed(42)
    np.random.seed(42)

    dataset_path = latest_dataset()
    data = np.load(dataset_path)
    train_mask, val_mask = split_by_episode(
        data["episode_ids"], val_ratio=0.2, seed=42
    )
    train_dataset = HandValueDataset(
        obs=data["obs"][train_mask],
        stats=data["stats"][train_mask],
        my_hands=data["my_hands"][train_mask],
        opp_hands=data["opp_hands"][train_mask],
        labels=data["labels"][train_mask],
    )
    val_dataset = HandValueDataset(
        obs=data["obs"][val_mask],
        stats=data["stats"][val_mask],
        my_hands=data["my_hands"][val_mask],
        opp_hands=data["opp_hands"][val_mask],
        labels=data["labels"][val_mask],
    )
    generator = torch.Generator().manual_seed(42)
    train_loader = DataLoader(
        train_dataset, batch_size=256, shuffle=True, generator=generator
    )
    val_loader = DataLoader(val_dataset, batch_size=256, shuffle=False)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = HandValueModel(
        num_card_types=NUM_CARD_TYPES,
        obs_dim=data["obs"].shape[1],
    ).to(device)
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)

    best_loss = float("inf")
    best_epoch = 0
    best_state: dict[str, torch.Tensor] | None = None

    print(f"dataset: {dataset_path}")
    print(f"device: {device}")
    for epoch in range(1, 11):
        model.train()
        for batch in train_loader:
            optimizer.zero_grad()
            values = model(
                batch["obs"].to(device),
                batch["stats"].to(device),
                batch["my_hands"].to(device),
                batch["opp_hands"].to(device),
            )
            loss = criterion(values, batch["labels"].to(device))
            loss.backward()
            optimizer.step()

        val_loss, _, _ = evaluate(model, val_loader, device)
        print(f"epoch={epoch} val_loss={val_loss:.6f}", flush=True)
        if val_loss < best_loss:
            best_loss = val_loss
            best_epoch = epoch
            best_state = copy.deepcopy(model.state_dict())

    assert best_state is not None
    model.load_state_dict(best_state)
    best_loss, prediction, target = evaluate(model, val_loader, device)
    rows = calibration_rows(prediction, target)
    ece = sum(abs(float(row["gap"])) * int(row["count"]) for row in rows)
    ece /= len(target)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUTPUT_DIR / "validation_calibration.csv"
    with csv_path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    npz_path = OUTPUT_DIR / "validation_predictions.npz"
    np.savez_compressed(npz_path, prediction=prediction, target=target)

    quantiles = np.quantile(
        prediction, [0.0, 0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99, 1.0]
    )
    print(f"best_epoch={best_epoch} best_val_loss={best_loss:.6f}")
    print(
        "prediction_summary "
        f"mean={prediction.mean():+.6f} std={prediction.std():.6f} "
        f"outside_range={np.count_nonzero((prediction < -1) | (prediction > 1))}"
    )
    print("quantiles:", " ".join(f"{value:+.6f}" for value in quantiles))
    print("calibration:")
    for row in rows:
        print(
            f"bin={row['bin']:02d} n={row['count']} "
            f"range=[{row['pred_min']:+.4f},{row['pred_max']:+.4f}] "
            f"pred={row['pred_mean']:+.4f} actual={row['actual_mean']:+.4f} "
            f"gap={row['gap']:+.4f}"
        )
    print(f"calibration_ece={ece:.6f}")
    for label in (-1.0, 0.0, 1.0):
        label_predictions = prediction[target == label]
        print(
            f"target={label:+.0f} n={len(label_predictions)} "
            f"pred_mean={label_predictions.mean():+.6f} "
            f"pred_std={label_predictions.std():.6f}"
        )
    print(f"csv: {csv_path}")
    print(f"predictions: {npz_path}")


if __name__ == "__main__":
    main()
