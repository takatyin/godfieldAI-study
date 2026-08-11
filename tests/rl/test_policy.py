import torch as th

from godfield_rl.env_wrapper import GodFieldVectorEnv
from godfield_rl.privileged.policy import PrivilegedMaskableActorCriticPolicy


def test_privileged_policy_forward():
    num_envs = 4

    env = GodFieldVectorEnv(num_envs=num_envs)
    obs = env.reset()

    policy = PrivilegedMaskableActorCriticPolicy(
        observation_space=env.observation_space,
        action_space=env.action_space,
        lr_schedule=lambda _: 3e-4,
    )

    obs_tensor = th.as_tensor(obs, dtype=th.float32)

    hands = env.get_opponent_true_hands()
    hand_tensor = th.as_tensor(hands)

    masks = env.action_masks()

    with th.no_grad():
        actions, values, log_probs = policy(
            obs_tensor,
            hand_tensor,
            action_masks=masks,
        )

    assert actions.shape == (num_envs,)
    assert values.shape == (num_envs, 1)
    assert log_probs.shape == (num_envs,)

def test_privileged_policy_evaluate_actions():
    num_envs = 4

    env = GodFieldVectorEnv(num_envs=num_envs)
    obs = env.reset()

    policy = PrivilegedMaskableActorCriticPolicy(
        observation_space=env.observation_space,
        action_space=env.action_space,
        lr_schedule=lambda _: 3e-4,
    )

    obs_tensor = th.as_tensor(obs, dtype=th.float32)

    hands = env.get_opponent_true_hands()
    hand_tensor = th.as_tensor(hands)

    masks = env.action_masks()

    with th.no_grad():
        actions, _, _ = policy(
            obs_tensor,
            hand_tensor,
            action_masks=masks,
        )

        values, log_probs, entropy = policy.evaluate_actions(
            obs_tensor,
            actions,
            hand_tensor,
            action_masks=masks,
        )

    assert values.shape == (num_envs, 1)
    assert log_probs.shape == (num_envs,)
    assert entropy.shape == (num_envs,)

def test_privileged_policy_predict_values():
    num_envs = 4

    env = GodFieldVectorEnv(num_envs=num_envs)
    obs = env.reset()

    policy = PrivilegedMaskableActorCriticPolicy(
        observation_space=env.observation_space,
        action_space=env.action_space,
        lr_schedule=lambda _: 3e-4,
    )

    obs_tensor = th.as_tensor(obs, dtype=th.float32)

    hands = env.get_opponent_true_hands()
    hand_tensor = th.as_tensor(hands)

    with th.no_grad():
        values = policy.predict_values(
            obs_tensor,
            hand_tensor,
        )

    assert values.shape == (num_envs, 1)