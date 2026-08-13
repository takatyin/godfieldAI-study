from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from godfield_rl.hand_value_data import collect_value_data
from godfield_rl.opponents import make_opponent

REPO_ROOT = Path(__file__).resolve().parents[1]

def main():
    # ------------------------------------------------------------
    # 実験設定
    # ------------------------------------------------------------
    seed = 42
    games = 100000
    num_envs = 128
    sample_every = 10
    learner_seat = 0

    # ------------------------------------------------------------
    # 対戦相手を用意
    # ------------------------------------------------------------
    seat0 = make_opponent(
        "strategic",
        seed=seed,
    )

    seat1 = make_opponent(
        "strategic",
        seed=seed + 1,
    )

    # ------------------------------------------------------------
    # データ収集
    # ------------------------------------------------------------
    data = collect_value_data(
        seat0,
        seat1,
        games=games,
        num_envs=num_envs,
        seed=seed,
        sample_every=sample_every,
        learner_seat=0,
    )

    # ------------------------------------------------------------
    # 簡単な確認
    # ------------------------------------------------------------
    print("stats:", data["stats"].shape)
    print("my_hands:", data["my_hands"].shape)
    print("opp_hands:", data["opp_hands"].shape)
    print("labels:", data["labels"].shape)
    print("episode_ids:", data["episode_ids"].shape)

    print(
        "label counts:",
        np.unique(data["labels"], return_counts=True),
    )

    # ------------------------------------------------------------
    # 保存先を作る
    # ------------------------------------------------------------
    timestamp = datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    )

    run_id = f"hand_value_data_s{seed}_{timestamp}"

    run_dir = (
        REPO_ROOT
        / "runs"
        / "hand_value_data"
        / run_id
    )

    run_dir.mkdir(
        parents=True,
        exist_ok=False,
    )

    output_path = run_dir / "dataset.npz"

    # ------------------------------------------------------------
    # 保存
    # ------------------------------------------------------------
    np.savez_compressed(
        output_path,
        obs = data["obs"],
        stats=data["stats"],
        my_hands=data["my_hands"],
        opp_hands=data["opp_hands"],
        labels=data["labels"],
        episode_ids=data["episode_ids"],
    )

    print(f"saved: {output_path}")


if __name__ == "__main__":
    main()