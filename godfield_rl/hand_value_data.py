from __future__ import annotations

import numpy as np

import godfield_core
from godfield_rl.cards import all_cards
from godfield_rl.evaluation import split_observation
from godfield_rl.opponents import Opponent


def collect_value_data(
    seat0: Opponent,
    seat1: Opponent,
    *,
    games: int,
    learner_seat:int = 0,
    num_envs: int = 512,
    seed: int = 0,
    sample_every: int = 10,
    max_steps_per_game: int = 2000,
) -> dict[str, np.ndarray]:
    # ------------------------------------------------------------
    # 保存用バッファ
    # ------------------------------------------------------------
    stats_buffer: list[np.ndarray] = []
    my_hands_buffer: list[np.ndarray] = []
    opp_hands_buffer: list[np.ndarray] = []
    episode_ids: list[np.ndarray] = []
    obs_buffer: list[np.ndarray] = []

    # episode_id -> 最終勝敗
    # seat0 視点で
    #   +1 : win
    #    0 : draw
    #   -1 : loss
    episode_outcomes: dict[int, float] = {}

    # ------------------------------------------------------------
    # 環境初期化
    # ------------------------------------------------------------
    all_cards()

    pool = godfield_core.EnvPool(num_envs)
    pool.reset(seed)

    players = {
        0: seat0,
        1: seat1,
    }

    # 各並列envが現在どのepisodeを走っているか
    current_episode_ids = np.arange(num_envs, dtype=np.int64)
    next_episode_id = num_envs

    # 各env内で何decision進んだか
    decision_counts = np.zeros(num_envs, dtype=np.int64)

    # ------------------------------------------------------------
    # 対戦しながら途中状態を保存
    # ------------------------------------------------------------
    for step in range(games * max_steps_per_game):
        learner_raw_obs = pool.get_observations_for(learner_seat)

        obs, masks = split_observation(
            learner_raw_obs,
            num_envs,
        )

        actors = pool.get_current_actors()

        actions = np.zeros(num_envs, dtype=np.int32)

        for seat, policy in players.items():
            idx = np.flatnonzero(actors == seat)

            if idx.size:
                actions[idx] = policy.act(
                    obs[idx],
                    masks[idx],
                )

        # --------------------------------------------------------
        # actionを進める前の状態を一定間隔で保存
        # --------------------------------------------------------
        decision_counts += 1
        sample_mask = (decision_counts % sample_every) == 0

        if sample_mask.any():
            idx = np.flatnonzero(sample_mask)

            stats = pool.get_player_stats()
            my_hands = pool.get_true_hands(learner_seat)
            opp_hands = pool.get_true_hands(1 - learner_seat)

            obs_buffer.append(obs[idx].copy())
            stats_buffer.append(stats[idx].copy())
            my_hands_buffer.append(my_hands[idx].copy())
            opp_hands_buffer.append(opp_hands[idx].copy())
            episode_ids.append(current_episode_ids[idx].copy())

        # --------------------------------------------------------
        # 環境を1step進める
        # --------------------------------------------------------
        pool.step_all(actions)

        dones = pool.get_dones().astype(bool)

        if dones.any():
            rewards = pool.get_rewards_for(learner_seat)


            # 終了episodeの最終結果を保存
            for i in np.flatnonzero(dones):
                episode_outcomes[
                    int(current_episode_ids[i])
                ] = float(rewards[i])

            # 終了したenvは次のepisodeへ
            for i in np.flatnonzero(dones):
                current_episode_ids[i] = next_episode_id
                next_episode_id += 1

                # 新しいepisodeなのでdecision数もリセット
                decision_counts[i] = 0

        # 必要なゲーム数に達したら終了
        if len(episode_outcomes) >= games:
            break

    else:
        raise RuntimeError(
            f"{step + 1} steps回しても {games} 局に届きませんでした。"
        )

    # ------------------------------------------------------------
    # 保存したbatchを1本のarrayへ結合
    # ------------------------------------------------------------
    if not episode_ids:
        raise RuntimeError(
            "状態が1件も保存されませんでした。"
            " sample_every が大きすぎる可能性があります。"
        )

    obs_array = np.concatenate(obs_buffer, axis=0)
    stats_array = np.concatenate(stats_buffer, axis=0)
    my_hands_array = np.concatenate(my_hands_buffer, axis=0)
    opp_hands_array = np.concatenate(opp_hands_buffer, axis=0)
    episode_ids_array = np.concatenate(episode_ids, axis=0)

    # ------------------------------------------------------------
    # まだ終了していないepisode由来のstateを除外
    # ------------------------------------------------------------
    valid_mask = np.array(
        [
            int(ep_id) in episode_outcomes
            for ep_id in episode_ids_array
        ],
        dtype=bool,
    )
    
    obs_array = obs_array[valid_mask]
    stats_array = stats_array[valid_mask]
    my_hands_array = my_hands_array[valid_mask]
    opp_hands_array = opp_hands_array[valid_mask]
    episode_ids_array = episode_ids_array[valid_mask]

    # ------------------------------------------------------------
    # 各途中状態に最終勝敗ラベルを付与
    # ------------------------------------------------------------
    labels = np.array(
        [
            episode_outcomes[int(ep_id)]
            for ep_id in episode_ids_array
        ],
        dtype=np.float32,
    )

    return {
        "obs": obs_array,
        "stats": stats_array,
        "my_hands": my_hands_array,
        "opp_hands": opp_hands_array,
        "labels": labels,
        "episode_ids": episode_ids_array,
    }