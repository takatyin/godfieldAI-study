from __future__ import annotations


import numpy as np
import torch
from torch.utils.data import Dataset


def split_by_episode(
    episode_ids: np.ndarray,
    val_ratio: float = 0.2,
    seed: int = 42,
):
    rng = np.random.default_rng(seed)

    unique_episode_ids = np.unique(episode_ids)
    rng.shuffle(unique_episode_ids)

    num_val = int(len(unique_episode_ids) * val_ratio)

    val_episode_ids = unique_episode_ids[:num_val]
    train_episode_ids = unique_episode_ids[num_val:]

    train_mask = np.isin(
        episode_ids,
        train_episode_ids,
    )

    val_mask = np.isin(
        episode_ids,
        val_episode_ids,
    )

    return train_mask, val_mask



class HandValueDataset(Dataset):
    def __init__(
        self,
        *,
        obs: np.ndarray,
        stats: np.ndarray,
        my_hands: np.ndarray,
        opp_hands: np.ndarray,
        labels: np.ndarray,
    ):
        self.obs = torch.as_tensor(
            obs,
            dtype = torch.float32,
        )

        self.stats = torch.as_tensor(
            stats,
            dtype=torch.float32,
        )

        self.my_hands = torch.as_tensor(
            my_hands,
            dtype=torch.long,
        )

        self.opp_hands = torch.as_tensor(
            opp_hands,
            dtype=torch.long,
        )

        self.labels = torch.as_tensor(
            labels,
            dtype=torch.float32,
        )

        n = len(self.labels)

        if not (
            len(self.obs)
            == len(self.stats)
            == len(self.my_hands)
            == len(self.opp_hands)
            == n
        ):
            raise ValueError("dataset arrays must have the same length")

    def __len__(self) -> int:
        return len(self.labels)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        return {
            "obs": self.obs[idx],
            "stats": self.stats[idx],
            "my_hands": self.my_hands[idx],
            "opp_hands": self.opp_hands[idx],
            "labels": self.labels[idx],
        }