"""特徴抽出器に後から足した経路が、学習開始時点で「何もしない」ことの検証。

【なぜこのテストがあるのか】

カード属性と閾値符号をトークンに足しただけで、50M ステップの学習が丸ごと
無駄になりました。例外は出ず、学習も普通に進んでいるように見えたまま、

    常にゼロのユニット   0 -> 134 / 256
    局面ごとのばらつき  0.508 -> 0.158
    approx_kl        0.02〜0.05 -> 0.002
    対 strategic 勝率     44.9% -> 21.0%

となりました。新しい成分を足すと ReLU 前の分布がずれてユニットが死ぬためです。

係数を0から始めれば初期状態の出力は追加前と一致し、役に立つぶんだけ係数が
自分で大きくなります。ここが静かに戻ると同じ事故が再発するので固定します。

【SB3 の再初期化に注意】

`ActorCriticPolicy` は構築後に特徴抽出器へ直交初期化をかけ直すため、
`__init__` で重みを0にしても上書きされます。素の `nn.Parameter` は対象外なので、
係数（ゲート）として持つ必要があります。
"""

import gymnasium as gym
import numpy as np
import pytest
import torch

import godfield_core
from godfield_rl.feature_extractor import GodFieldTransformerExtractor, zero_gate

OBS_SIZE = godfield_core.OBSERVATION_FEATURE_SIZE - godfield_core.ACTION_SPACE_SIZE
GATES = ("card_attr_gate", "stat_thermometer_gate")


@pytest.fixture
def extractor():
    torch.manual_seed(0)
    space = gym.spaces.Box(low=-np.inf, high=np.inf, shape=(OBS_SIZE,), dtype=np.float32)
    model = GodFieldTransformerExtractor(
        space, d_model=32, nhead=4, num_layers=2, dim_feedforward=64, features_dim=16
    )
    model.eval()
    return model


def observation() -> torch.Tensor:
    """カードと履歴が入った、それらしい観測。"""
    from godfield_rl import feature_config as fc

    obs = np.zeros((4, OBS_SIZE), dtype=np.float32)
    for block in (fc.HAND_CARDS_START, fc.STAGED_CARDS_START,
                  fc.OPP_HAND_CARDS_START, fc.OPP_STAGED_CARDS_START):
        obs[:, block : block + fc.MAX_HAND_SIZE] = -1
    obs[:, fc.HAND_CARDS_START : fc.HAND_CARDS_START + 3] = [10, 20, 30]
    obs[:, fc.STAT_START : fc.STAT_START + 6] = [0.4, 0.3, 0.2, 0.1, 0.25, 0.05]
    obs[:, fc.HISTORY_START + 1] = float(godfield_core.EventType.ATTACK_HIT)
    obs[:, fc.HISTORY_START + 2] = 42
    return torch.as_tensor(obs)


# --- ゲートが 0 から始まること -----------------------------------------------


@pytest.mark.parametrize("name", GATES)
def test_gates_start_at_zero(extractor, name):
    assert getattr(extractor, name).item() == 0.0, f"{name} が0から始まっていません"


@pytest.mark.parametrize("name", GATES)
def test_gates_are_learnable(extractor, name):
    """0で固定してしまうと、属性を一生使えない。"""
    assert getattr(extractor, name).requires_grad


def test_zero_gate_helper_returns_a_trainable_zero():
    gate = zero_gate()
    assert isinstance(gate, torch.nn.Parameter)
    assert gate.item() == 0.0
    assert gate.requires_grad


# --- 初期状態では出力に影響しないこと ---------------------------------------


def test_added_paths_contribute_nothing_at_initialisation(extractor):
    """ゲートが0の間は、属性・閾値符号を変えても出力が1ビットも変わらない。"""
    obs = observation()
    with torch.no_grad():
        before = extractor(obs)
        # 属性テーブルと閾値の射影を滅茶苦茶にしても影響が無いはず
        extractor.card_attrs.mul_(100.0).add_(7.0)
        extractor.card_attr_proj.weight.fill_(5.0)
        extractor.stat_thermometer_proj.weight.fill_(-3.0)
        after = extractor(obs)

    assert torch.equal(before, after), (
        "ゲートが0なのに追加経路が出力へ漏れています"
    )


def test_opening_the_gate_changes_the_output(extractor):
    """ゲートを開ければ効くこと（＝配線自体は繋がっている）。"""
    obs = observation()
    with torch.no_grad():
        before = extractor(obs)
        extractor.card_attr_gate.fill_(1.0)
        after = extractor(obs)

    assert not torch.allclose(before, after), "ゲートを開けても属性が効いていません"


def test_gradient_reaches_the_gate(extractor):
    """0から始めても勾配が流れること。流れなければ永久に0のまま。"""
    out = extractor(observation()).sum()
    out.backward()

    for name in GATES:
        grad = getattr(extractor, name).grad
        assert grad is not None, f"{name} に勾配が届いていません"
        assert float(grad.abs().sum()) > 0.0, f"{name} の勾配がゼロです"


# --- SB3 の再初期化を生き延びること -----------------------------------------


def test_gates_survive_sb3_orthogonal_init():
    """SB3 は構築後に特徴抽出器へ直交初期化をかけ直す。

    重みのゼロ初期化はそこで消える（実測で射影の出力が 9.62 残った）。
    ゲートが Parameter であれば対象外なので0のまま残る。
    """
    from sb3_contrib import MaskablePPO

    from godfield_rl.amp import policy_class
    from godfield_rl.config import TrainingConfig
    from godfield_rl.env_wrapper import GodFieldVectorEnv
    from godfield_rl.opponents import make_opponent
    from godfield_rl.training import build_policy_kwargs

    cfg = TrainingConfig(d_model=32, nhead=4, num_layers=1, dim_feedforward=32,
                         features_dim=16)
    env = GodFieldVectorEnv(4, opponent=make_opponent("random", seed=0))
    model = MaskablePPO(policy_class(False), env, policy_kwargs=build_policy_kwargs(cfg),
                        n_steps=4, batch_size=4, device="cpu", seed=0, verbose=0)

    extractor = model.policy.features_extractor
    for name in GATES:
        assert getattr(extractor, name).item() == 0.0, (
            f"SB3 の初期化で {name} が上書きされています"
        )
