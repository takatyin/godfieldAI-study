import godfield_core

from godfield_rl.env_wrapper import GodFieldVectorEnv

def test_vector_env_get_opponent_true_hands():
    env = GodFieldVectorEnv(num_envs=4)

    env.reset()

    hands = env.get_opponent_true_hands()

    assert hands.shape == (
        4,
        godfield_core.MAX_HAND_SIZE,
    )