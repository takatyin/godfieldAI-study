import godfield_core

def test_get_opponent_true_hands_shape():
    num_envs = 4

    env = godfield_core.EnvPool(num_envs)
    env.reset(42)

    hands = env.get_opponent_true_hands(player_id=0)

    assert hands.shape == (
        num_envs,
        godfield_core.MAX_HAND_SIZE,
    )
    