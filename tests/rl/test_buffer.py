import numpy as np
import torch as th
from gymnasium.spaces import Box, Discrete

import godfield_core

from godfield_rl.privileged.buffer import PrivilegedRolloutBuffer


def test_privileged_rollout_buffer():
    buffer_size = 2
    n_envs = 2
    obs_dim = 3

    observation_space = Box(
        low=-1.0,
        high=1.0,
        shape=(obs_dim,),
        dtype=np.float32,
    )
    action_space = Discrete(4)

    buffer = PrivilegedRolloutBuffer(
        buffer_size=buffer_size,
        observation_space=observation_space,
        action_space=action_space,
        device="cpu",
        gamma=0.99,
        gae_lambda=0.95,
        n_envs=n_envs,
    )

    for t in range(buffer_size):
        obs = np.full((n_envs, obs_dim), t, dtype=np.float32)
        actions = np.zeros((n_envs, 1), dtype=np.int64)
        rewards = np.zeros(n_envs, dtype=np.float32)
        episode_starts = np.zeros(n_envs, dtype=np.float32)

        values = th.zeros(n_envs)
        log_probs = th.zeros(n_envs)

        hands = np.full(
            (n_envs, godfield_core.MAX_HAND_SIZE),
            t,
            dtype=np.int32,
        )

        action_masks = np.ones(
            (n_envs, action_space.n),
            dtype=bool,
        )

        buffer.add(
            obs,
            actions,
            rewards,
            episode_starts,
            values,
            log_probs,
            opponent_true_hands=hands,
            action_masks=action_masks,
        )

    assert buffer.full

    last_values = th.zeros(n_envs)
    dones = np.zeros(n_envs, dtype=bool)

    buffer.compute_returns_and_advantage(
        last_values=last_values,
        dones=dones,
    )

    batch = next(buffer.get(batch_size=None))

    assert batch.observations.shape == (
        buffer_size * n_envs,
        obs_dim,
    )

    assert batch.opponent_true_hands.shape == (
        buffer_size * n_envs,
        godfield_core.MAX_HAND_SIZE,
    )

    for i in range(buffer_size * n_envs):
        obs_t = batch.observations[i, 0]
        hand_t = batch.opponent_true_hands[i, 0]

        assert obs_t.item() == hand_t.item()