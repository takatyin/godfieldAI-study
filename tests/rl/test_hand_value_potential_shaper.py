import numpy as np
import pytest
import torch

import godfield_core
from godfield_rl.hand_value_model import HandValueModel
from godfield_rl.shaping import (
    HAND_VALUE_HP_RESIDUAL_BETA,
    HandValuePotentialShaper,
    PotentialShaper,
    load_latest_hand_value_model,
    make_shaper,
)


def constant_model(value: float) -> HandValueModel:
    model = HandValueModel(num_card_types=294, obs_dim=8)
    with torch.no_grad():
        for parameter in model.parameters():
            parameter.zero_()
        model.mlp[-1].bias.fill_(value)
    return model


def inputs(batch_size: int = 3) -> tuple[np.ndarray, ...]:
    return (
        np.zeros((batch_size, 8), dtype=np.float64),
        np.zeros((batch_size, 6), dtype=np.int32),
        np.full((batch_size, 18), -1, dtype=np.int32),
        np.full((batch_size, 18), -1, dtype=np.int32),
    )


def save_checkpoint(path, value: float) -> None:
    model = constant_model(value)
    path.parent.mkdir(parents=True)
    torch.save(
        {
            "model_config": {
                "num_card_types": 294,
                "obs_dim": 8,
                "stats_dim": 6,
                "hand_embed_dim": 16,
                "obs_feature_dim": 64,
                "hidden_dim": 64,
            },
            "model_state_dict": model.state_dict(),
        },
        path,
    )


@pytest.mark.parametrize(
    ("clip_value", "raw_value", "expected"),
    [(1.0, 2.0, 1.0), (0.5, -2.0, -0.5), (None, 2.0, 2.0)],
)
def test_potential_shape_dtype_and_clipping(clip_value, raw_value, expected):
    shaper = HandValuePotentialShaper(
        model=constant_model(raw_value),
        clip_value=clip_value,
    )

    phi = shaper.potential(*inputs())

    assert phi.shape == (3,)
    assert phi.dtype == np.float32
    assert phi == pytest.approx(np.full(3, expected, dtype=np.float32))


@pytest.mark.parametrize("clip_value", [0.0, -0.5])
def test_non_positive_clip_value_is_rejected(clip_value):
    with pytest.raises(ValueError, match="clip_value"):
        HandValuePotentialShaper(
            model=constant_model(0.0),
            clip_value=clip_value,
        )


def test_shape_scales_pbrs_and_zeros_terminal_next_potential():
    shaper = HandValuePotentialShaper(
        model=constant_model(0.0),
        gamma=0.9,
        alpha=0.2,
    )
    prev = np.array([0.5, 0.5], dtype=np.float64)
    nxt = np.array([0.8, 0.8], dtype=np.float64)
    terminated = np.array([False, True])

    shaped = shaper.shape(prev, nxt, terminated)

    assert shaped.dtype == np.float32
    assert shaped[0] == pytest.approx(0.2 * (0.9 * 0.8 - 0.5))
    assert shaped[1] == pytest.approx(0.2 * (0.0 - 0.5))


def test_potential_shaper_combines_stats_and_scaled_hand_value():
    hand_shaper = HandValuePotentialShaper(
        model=constant_model(0.5),
        gamma=0.1,
        alpha=0.2,
    )
    shaper = PotentialShaper(
        hp=0.2,
        gamma=0.9,
        hand_value_shaper=hand_shaper,
    )
    obs, stats, my_hands, opp_hands = inputs(batch_size=2)
    stats[:, 0] = 50
    stats[:, 3] = 40

    phi = shaper.potential(
        stats,
        learner_seat=0,
        my_hands=my_hands,
        opp_hands=opp_hands,
        obs=obs,
    )

    hp_phi = (50 - 40) / 99.0
    expected = 0.2 * hp_phi + 0.2 * (
        0.5 - HAND_VALUE_HP_RESIDUAL_BETA * hp_phi
    )
    assert phi.dtype == np.float32
    assert phi == pytest.approx(np.full(2, expected, dtype=np.float32))
    assert shaper.enabled


@pytest.mark.parametrize(("learner_seat", "sign"), [(0, 1.0), (1, -1.0)])
def test_hand_value_potential_removes_hp_component_from_learner_side(
    learner_seat,
    sign,
):
    hand_shaper = HandValuePotentialShaper(
        model=constant_model(0.5),
        alpha=1.0,
    )
    shaper = PotentialShaper(
        hp=0.0,
        hand_value_shaper=hand_shaper,
    )
    obs, stats, my_hands, opp_hands = inputs(batch_size=1)
    stats[:, 0] = 50
    stats[:, 3] = 40

    phi = shaper.potential(
        stats,
        learner_seat=learner_seat,
        my_hands=my_hands,
        opp_hands=opp_hands,
        obs=obs,
    )

    hp_phi = sign * (50 - 40) / 99.0
    expected = 0.5 - HAND_VALUE_HP_RESIDUAL_BETA * hp_phi
    assert phi == pytest.approx(np.array([expected], dtype=np.float32))


def test_combined_shaper_requires_hand_value_model_inputs():
    shaper = PotentialShaper(
        hp=0.0,
        hand_value_shaper=HandValuePotentialShaper(model=constant_model(0.5)),
    )

    with pytest.raises(ValueError, match="obs, my_hands, and opp_hands"):
        shaper.potential(np.zeros((2, 6), dtype=np.float32), learner_seat=0)


def test_env_wrapper_passes_current_observation_to_combined_shaper():
    from godfield_rl.env_wrapper import GodFieldVectorEnv
    from godfield_rl.opponents import make_opponent

    obs_dim = (
        godfield_core.OBSERVATION_FEATURE_SIZE - godfield_core.ACTION_SPACE_SIZE
    )
    hand_shaper = HandValuePotentialShaper(
        model=HandValueModel(num_card_types=294, obs_dim=obs_dim),
        alpha=0.2,
    )
    shaper = PotentialShaper(
        hp=0.2,
        gamma=0.995,
        hand_value_shaper=hand_shaper,
    )
    env = GodFieldVectorEnv(
        4,
        opponent=make_opponent("heuristic", seed=1),
        shaper=shaper,
    )
    env.seed(3)

    obs = env.reset()
    assert obs.shape == (4, obs_dim)
    assert env._prev_potential.shape == (4,)

    masks = env.action_masks()
    actions = np.argmax(masks, axis=1).astype(np.int32)
    next_obs, rewards, _, _ = env.step(actions)

    assert next_obs.shape == (4, obs_dim)
    assert rewards.shape == (4,)
    assert env._prev_potential.shape == (4,)
    env.close()


def test_make_shaper_loads_best_model_from_highest_numbered_run(tmp_path):
    save_checkpoint(tmp_path / "hand_value_model_2" / "best_model.pt", 0.2)
    save_checkpoint(tmp_path / "hand_value_model_10" / "best_model.pt", 0.7)

    shaper = make_shaper(
        0.0,
        0.0,
        0.0,
        gamma=0.9,
        hand=0.3,
        hand_value_model_dir=tmp_path,
    )

    assert shaper is not None
    assert shaper.hand_value_shaper is not None
    assert shaper.hand_value_shaper.alpha == pytest.approx(0.3)
    assert shaper.hand_value_shaper.gamma == pytest.approx(0.9)
    phi = shaper.potential(
        inputs()[1],
        learner_seat=0,
        my_hands=inputs()[2],
        opp_hands=inputs()[3],
        obs=inputs()[0],
    )
    assert phi == pytest.approx(np.full(3, 0.3 * 0.7, dtype=np.float32))


def test_loading_latest_model_requires_its_best_checkpoint(tmp_path):
    save_checkpoint(tmp_path / "hand_value_model_1" / "best_model.pt", 0.2)
    (tmp_path / "hand_value_model_2").mkdir()

    with pytest.raises(FileNotFoundError, match="best hand value model"):
        load_latest_hand_value_model(tmp_path)
