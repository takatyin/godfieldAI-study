import torch

from godfield_rl.hand_value_model import HandValueModel


def test_hand_value_model_forward():
    batch_size = 4
    obs_dim = 100  # 仮。実際は data["obs"].shape[1]
    num_card_types = 294

    model = HandValueModel(
        num_card_types=num_card_types,
        obs_dim=obs_dim,
    )

    obs = torch.randn(
        batch_size,
        obs_dim,
    )

    stats = torch.tensor(
        [
            [40, 10, 20, 40, 10, 20],
            [30, 15, 10, 20, 5, 30],
            [10, 0, 5, 35, 20, 20],
            [25, 8, 12, 25, 8, 12],
        ],
        dtype=torch.float32,
    )

    my_hands = torch.full(
        (batch_size, 18),
        -1,
        dtype=torch.long,
    )

    opp_hands = torch.full(
        (batch_size, 18),
        -1,
        dtype=torch.long,
    )

    my_hands[0, :3] = torch.tensor([0, 1, 2])
    my_hands[1, :2] = torch.tensor([5, 8])

    opp_hands[0, :2] = torch.tensor([3, 4])
    opp_hands[2, :3] = torch.tensor([10, 11, 12])

    values = model(
        obs,
        stats,
        my_hands,
        opp_hands,
    )

    print("obs:", obs.shape)
    print("stats:", stats.shape)
    print("my_hands:", my_hands.shape)
    print("opp_hands:", opp_hands.shape)
    print("values:", values.shape)
    print(values)

    assert values.shape == (batch_size,)
    assert torch.isfinite(values).all()