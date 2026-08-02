"""カード属性と閾値符号が、特徴抽出器の出力に本当に効いていることの検証。

配線を間違えても例外は出ません。足し忘れれば無視されるだけで、
「カードの意味を知らないまま学習が進む」という、実際に起きた状態に戻ります。
"""

import gymnasium as gym
import numpy as np
import pytest
import torch

import godfield_core
from godfield_rl import feature_config as fc
from godfield_rl.card_features import card_attr_dim
from godfield_rl.cards import card_id
from godfield_rl.feature_extractor import (
    STAT_THERMOMETER_DIM,
    GodFieldTransformerExtractor,
)

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


def base_observation() -> np.ndarray:
    obs = np.zeros((1, OBS_SIZE), dtype=np.float32)
    for block in (fc.HAND_CARDS_START, fc.STAGED_CARDS_START,
                  fc.OPP_HAND_CARDS_START, fc.OPP_STAGED_CARDS_START):
        obs[0, block : block + fc.MAX_HAND_SIZE] = -1
    return obs


def run(model, obs: np.ndarray) -> torch.Tensor:
    with torch.no_grad():
        return model(torch.as_tensor(obs))


# --- カード属性 -------------------------------------------------------------


def test_the_attribute_table_is_available_to_the_network(extractor):
    assert extractor.card_attrs.shape == (fc.NUM_CARD_TYPES + 1, card_attr_dim())
    assert not extractor.card_attrs[0].any(), "空スロット用の行が全ゼロではありません"


def test_the_table_given_to_the_network_is_standardized(extractor):
    """共通成分が残っていると、全カードトークンに同じベクトルが足される。

    情報を持たない定数が乗ると ReLU 前の分布が偏ってユニットが死に、局面ごとの
    変動が薄まります。実測では 256 ユニット中 134 が常にゼロになり、
    approx_kl が 0.002 まで落ちて学習が止まりました。
    """
    real = extractor.card_attrs[1:].numpy()
    assert abs(np.linalg.norm(real.mean(axis=0))) < 1e-4, (
        f"共通成分が残っています（ノルム {np.linalg.norm(real.mean(axis=0)):.3f}）"
    )


def test_the_attribute_table_is_not_stored_in_the_checkpoint(extractor):
    """カードマスタから決まる派生データなので保存しない（読み込み時に作り直す）。"""
    keys = extractor.state_dict().keys()
    assert "card_attrs" not in keys
    assert "card_attr_proj.weight" in keys, "射影の重みは学習対象なので保存されるべきです"


def open_gates(extractor) -> None:
    """学習開始時点ではゲートが0で属性が効かないので、配線の検証用に開ける。

    ゲートが0から始まること自体は tests/rl/test_added_paths_start_inert.py が
    検証しています。ここで見たいのは「開けたときに正しく届くか」です。
    """
    with torch.no_grad():
        extractor.card_attr_gate.fill_(1.0)
        extractor.stat_thermometer_gate.fill_(1.0)


def test_card_attributes_change_the_output(extractor):
    """属性の射影を殺すと出力が変わる ＝ 属性が実際に使われている。"""
    open_gates(extractor)
    obs = base_observation()
    obs[0, fc.HAND_CARDS_START] = card_id("神の盾")
    before = run(extractor, obs)

    with torch.no_grad():
        extractor.card_attr_proj.weight.zero_()
        extractor.card_attr_proj.bias.zero_()
    after = run(extractor, obs)

    assert not torch.allclose(before, after), "カード属性が出力に効いていません"


def test_history_cards_also_carry_attributes(extractor):
    """履歴のカードにも属性を足している（相手が何を出したかの読みに要る）。"""
    open_gates(extractor)
    obs = base_observation()
    ev = fc.HISTORY_START
    obs[0, ev + 1] = float(godfield_core.EventType.ATTACK_HIT)  # event_type
    obs[0, ev + 2] = card_id("神の盾")                          # card_id
    before = run(extractor, obs)

    with torch.no_grad():
        extractor.card_attr_proj.weight.zero_()
        extractor.card_attr_proj.bias.zero_()
    after = run(extractor, obs)

    assert not torch.allclose(before, after), "履歴のカード属性が使われていません"


def test_an_empty_hand_is_unaffected_by_the_attribute_table(extractor):
    """空スロットしかない観測では、属性の射影を殺しても（バイアス以外）変わらない。

    空スロットの行は全ゼロなので、線形射影の出力はバイアスだけになる。
    バイアスも0にすれば完全に一致するはず。
    """
    open_gates(extractor)
    obs = base_observation()
    with torch.no_grad():
        extractor.card_attr_proj.bias.zero_()
    before = run(extractor, obs)
    with torch.no_grad():
        extractor.card_attr_proj.weight.zero_()
    after = run(extractor, obs)

    assert torch.allclose(before, after, atol=1e-5), (
        "空スロットに属性が漏れています（padding の規約が合っていません）"
    )


# --- ステータスの温度計符号 -------------------------------------------------


def test_stat_thermometer_dimensions_line_up(extractor):
    assert extractor._stat_index.shape == extractor._stat_edge.shape
    assert extractor._stat_index.numel() == STAT_THERMOMETER_DIM
    # 参照するのは観測の先頭6次元（自HP,敵HP,自MP,敵MP,自金,敵金）だけ
    assert int(extractor._stat_index.max()) == 5
    assert int(extractor._stat_index.min()) == 0


def test_stat_thermometer_changes_the_output(extractor):
    open_gates(extractor)
    obs = base_observation()
    obs[0, fc.STAT_START + 4] = 0.20  # 自分の所持金 20円
    before = run(extractor, obs)

    with torch.no_grad():
        extractor.stat_thermometer_proj.weight.zero_()
        extractor.stat_thermometer_proj.bias.zero_()
    after = run(extractor, obs)

    assert not torch.allclose(before, after), "閾値符号が出力に効いていません"


def test_crossing_a_money_threshold_flips_a_dimension(extractor):
    """「所持金10円以上」の1次元が、9円と11円の間で切り替わること。"""
    edge_index = int(fc.STAT_START)  # 参照のみ（意図を明示するため）
    assert edge_index == fc.STAT_START

    def thermometer_of(money: float) -> torch.Tensor:
        obs = base_observation()
        obs[0, fc.STAT_START + 4] = money / 100.0
        stats = torch.as_tensor(obs[:, fc.STAT_START : fc.STAT_START + 6])
        return (stats[:, extractor._stat_index] >= extractor._stat_edge).float()

    below, above = thermometer_of(9), thermometer_of(11)
    flipped = torch.nonzero(below[0] != above[0]).flatten()
    assert flipped.numel() == 1, f"10円をまたいで切り替わった次元が {flipped.numel()} 個あります"
    assert above[0, flipped[0]] == 1.0 and below[0, flipped[0]] == 0.0
