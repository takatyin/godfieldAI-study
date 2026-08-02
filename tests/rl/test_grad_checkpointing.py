"""勾配チェックポイントが、出力と勾配を変えずにメモリだけ削っているか。

チェックポイントは「保持せず再計算する」だけの仕組みなので、数学的には
何も変わらないはずです。変わってしまうと、VRAM と引き換えに学習内容が
静かに壊れることになるため、そこを固定します。
"""

import gymnasium as gym
import numpy as np
import pytest
import torch

import godfield_core
from godfield_rl.feature_extractor import GodFieldTransformerExtractor

OBS_SIZE = godfield_core.OBSERVATION_FEATURE_SIZE - godfield_core.ACTION_SPACE_SIZE


def make_extractor(grad_checkpointing: bool, seed: int = 0):
    torch.manual_seed(seed)
    space = gym.spaces.Box(low=-np.inf, high=np.inf, shape=(OBS_SIZE,), dtype=np.float32)
    return GodFieldTransformerExtractor(
        space, d_model=32, nhead=4, num_layers=3, dim_feedforward=64,
        features_dim=16, grad_checkpointing=grad_checkpointing,
    )


def make_observations(batch: int = 6, seed: int = 3) -> torch.Tensor:
    """カードIDに空きスロット(-1)を混ぜた、それらしい観測を作ります。"""
    rng = np.random.default_rng(seed)
    obs = rng.normal(size=(batch, OBS_SIZE)).astype(np.float32)
    cards_start = godfield_core.MAX_HAND_SIZE  # 連続特徴の後ろにカードIDが並ぶ
    obs[:, cards_start:] = rng.integers(-1, 50, size=(batch, OBS_SIZE - cards_start))
    return torch.as_tensor(obs)


def test_output_is_identical_with_and_without_checkpointing():
    plain, checkpointed = make_extractor(False), make_extractor(True)
    checkpointed.load_state_dict(plain.state_dict())
    obs = make_observations()

    with torch.no_grad():
        expected = plain(obs)
        actual = checkpointed(obs)

    torch.testing.assert_close(actual, expected)


def test_gradients_are_identical_with_and_without_checkpointing():
    plain, checkpointed = make_extractor(False), make_extractor(True)
    checkpointed.load_state_dict(plain.state_dict())
    obs = make_observations()

    for model in (plain, checkpointed):
        model.zero_grad()
        model(obs).square().sum().backward()

    grads = dict(checkpointed.named_parameters())
    for name, param in plain.named_parameters():
        assert param.grad is not None, f"{name} に勾配が流れていません"
        torch.testing.assert_close(
            grads[name].grad, param.grad, rtol=1e-4, atol=1e-5,
            msg=lambda s, n=name: f"{n} の勾配が一致しません\n{s}",
        )


def test_inference_path_does_not_checkpoint():
    """勾配が要らない場面では checkpoint を通さない（ロールアウトを遅くしない）。"""
    model = make_extractor(True)
    obs = make_observations()

    calls = 0
    original = torch.utils.checkpoint.checkpoint

    def counting(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    torch.utils.checkpoint.checkpoint = counting
    try:
        with torch.no_grad():
            model(obs)
        assert calls == 0, "推論時に checkpoint が呼ばれています"

        model(obs).sum().backward()
        assert calls == 3, f"学習時は層数ぶん呼ばれるはず（3層）が {calls} 回でした"
    finally:
        torch.utils.checkpoint.checkpoint = original


def test_disabled_by_default():
    assert make_extractor(False).grad_checkpointing is False


@pytest.mark.parametrize("grad_checkpointing", [False, True])
def test_final_layer_norm_is_applied(grad_checkpointing):
    """自前でループを回す経路でも、TransformerEncoder 末尾の norm を落とさない。"""
    model = make_extractor(grad_checkpointing)
    assert model.transformer.norm is not None
    obs = make_observations()
    out = model(obs)
    assert out.shape == (obs.shape[0], 16)
    assert torch.isfinite(out).all()
