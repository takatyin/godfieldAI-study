"""追加した観測（手札枚数・公開状態）が、特徴抽出器の出力に効いていること。

配線を間違えても例外は出ません。オフセットがずれれば別の値を読み、
足し忘れれば無視されるだけで、どちらも「静かに学習が悪くなる」形で表れます。
値を変えたら出力が変わることを固定しておきます。
"""

import gymnasium as gym
import numpy as np
import pytest
import torch

import godfield_core
from godfield_rl import feature_config as fc
from godfield_rl.feature_extractor import GodFieldTransformerExtractor

OBS_SIZE = godfield_core.OBSERVATION_FEATURE_SIZE - godfield_core.ACTION_SPACE_SIZE


@pytest.fixture
def extractor():
    torch.manual_seed(0)
    space = gym.spaces.Box(low=-np.inf, high=np.inf, shape=(OBS_SIZE,), dtype=np.float32)
    model = GodFieldTransformerExtractor(
        space, d_model=32, nhead=4, num_layers=2, dim_feedforward=64, features_dim=16
    )
    model.eval()
    return model


def base_observation() -> torch.Tensor:
    """カードが数枚入った、それらしい観測を1件作ります。"""
    obs = np.zeros((1, OBS_SIZE), dtype=np.float32)
    for block in (fc.HAND_CARDS_START, fc.STAGED_CARDS_START,
                  fc.OPP_HAND_CARDS_START, fc.OPP_STAGED_CARDS_START):
        obs[0, block : block + fc.MAX_HAND_SIZE] = -1
    obs[0, fc.HAND_CARDS_START : fc.HAND_CARDS_START + 3] = [10, 20, 30]
    obs[0, fc.OPP_HAND_CARDS_START : fc.OPP_HAND_CARDS_START + 2] = [40, 50]
    return torch.as_tensor(obs)


def output(extractor, obs) -> torch.Tensor:
    with torch.no_grad():
        return extractor(obs)


@pytest.mark.parametrize("offset", [0, 1], ids=["自分の手札枚数", "相手の手札枚数"])
def test_hand_count_changes_the_output(extractor, offset):
    obs = base_observation()
    before = output(extractor, obs)

    obs[0, fc.HAND_COUNT_START + offset] = 0.5
    after = output(extractor, obs)

    assert not torch.allclose(before, after), "手札枚数が出力に効いていません"


def test_own_reveal_flag_changes_the_output(extractor):
    obs = base_observation()
    before = output(extractor, obs)

    obs[0, fc.HAND_KNOWN_TO_OPP_START + 1] = 1.0
    after = output(extractor, obs)

    assert not torch.allclose(before, after), "自分の公開状態が出力に効いていません"


def test_opponent_deployed_flag_changes_the_output(extractor):
    obs = base_observation()
    before = output(extractor, obs)

    obs[0, fc.OPP_DEPLOYED_START] = 1.0
    after = output(extractor, obs)

    assert not torch.allclose(before, after), "相手の展開状態が出力に効いていません"


def test_flags_on_empty_slots_are_ignored(extractor):
    """空スロットのフラグは出力を変えない。

    空スロットは key_padding_mask で注意から外れるので、そこに属性が
    立っていても影響しないのが正しい挙動。逆にここで出力が変われば、
    フラグを別のトークンに足しているか、マスクが効いていない。
    """
    obs = base_observation()
    before = output(extractor, obs)

    probe = obs.clone()
    # 手札はスロット0〜2までしか埋めていないので、末尾は空
    probe[0, fc.HAND_KNOWN_TO_OPP_START + fc.MAX_HAND_SIZE - 1] = 1.0
    probe[0, fc.OPP_DEPLOYED_START + fc.MAX_HAND_SIZE - 1] = 1.0

    assert torch.allclose(before, output(extractor, probe))


def test_extractor_input_size_matches_the_engine(extractor):
    """観測を増やしたら特徴抽出器の入力も追従していること。"""
    assert extractor.global_proj.in_features == fc.CONTINUOUS_FEATURES_SIZE
    assert fc.CONTINUOUS_FEATURES_SIZE > fc.HAND_COUNT_START, (
        "手札枚数がグローバルトークンの入力範囲に入っていません"
    )
    assert extractor.card_flag_proj.in_features == 2
