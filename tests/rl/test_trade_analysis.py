"""取引の診断が、観測から正しい情報を読めていることの検証。

観測のオフセットを1つ間違えても例外は出ません。別の値を読んで、それらしい
数字が出るだけです。実際この診断を作る過程で

  - 人手の方策を正解として扱う（一致度で良し悪しを判断する）
  - 「自分に売るのは明らかに損」と決めつける（上書きすると勝率は下がった）

という誤りを2つやっています。読み取りが合っていることだけでも固定しておきます。
"""

import numpy as np
import pytest

import godfield_core
from godfield_rl import feature_config as fc
from godfield_rl.cards import card_id
from godfield_rl.trade_analysis import (
    ACTION_DEAL_YES,
    ACTION_TARGET_OPP,
    ACTION_TARGET_SELF,
    PHASE_BUY,
    PHASE_SELL_SELECT,
    PHASE_TARGET_SELECT,
    BuyDecision,
    SellDecision,
    TradeOverride,
    TradeProbe,
    price_of,
    sell_card_id,
)

OBS_SIZE = godfield_core.OBSERVATION_FEATURE_SIZE - godfield_core.ACTION_SPACE_SIZE
STAT_SCALE = 100.0


class Fixed:
    """常に同じ行動を返す方策。"""

    def __init__(self, action: int):
        self.action = action

    def act(self, observations, action_masks):
        return np.full(len(observations), self.action, dtype=np.int32)


def blank(n: int = 1) -> np.ndarray:
    obs = np.zeros((n, OBS_SIZE), dtype=np.float32)
    for block in (fc.HAND_CARDS_START, fc.STAGED_CARDS_START,
                  fc.OPP_HAND_CARDS_START, fc.OPP_STAGED_CARDS_START):
        obs[:, block : block + fc.MAX_HAND_SIZE] = -1
    return obs


def set_phase(obs: np.ndarray, phase: int) -> None:
    obs[:, fc.PHASE_START : fc.PHASE_START + fc.PHASE_LEN] = 0.0
    obs[:, fc.PHASE_START + phase] = 1.0


def full_mask() -> np.ndarray:
    return np.ones((1, godfield_core.ACTION_SPACE_SIZE), dtype=bool)


# --- 買う ------------------------------------------------------------------


def test_the_offered_card_is_read_from_the_opponent_staged_block():
    """公開された札は売り手の仮置き場に入る（買う側から見ると OPP_STAGED）。"""
    obs = blank()
    set_phase(obs, PHASE_BUY)
    obs[0, fc.OPP_STAGED_CARDS_START] = card_id("神の盾")
    obs[0, fc.STAT_START + 4] = 40 / STAT_SCALE

    probe = TradeProbe(Fixed(ACTION_DEAL_YES), sell_card_id())
    probe.act(obs, full_mask())

    assert len(probe.stats.buys) == 1
    decision = probe.stats.buys[0]
    assert decision.card == card_id("神の盾")
    assert decision.money == 40
    assert decision.bought is True


def test_declining_is_recorded_as_not_bought():
    obs = blank()
    set_phase(obs, PHASE_BUY)
    obs[0, fc.OPP_STAGED_CARDS_START] = card_id("パンチ")

    probe = TradeProbe(Fixed(godfield_core.ACTION_DEAL_NO), sell_card_id())
    probe.act(obs, full_mask())

    assert probe.stats.buys[0].bought is False


def test_an_unreadable_offer_is_counted_not_guessed():
    """公開札が読めない局面は、黙って捨てずに件数を出す。"""
    obs = blank()
    set_phase(obs, PHASE_BUY)

    probe = TradeProbe(Fixed(ACTION_DEAL_YES), sell_card_id())
    probe.act(obs, full_mask())

    assert probe.stats.buys == []
    assert probe.stats.unreadable == 1


def test_affordability_uses_the_card_price():
    cheap = BuyDecision(card_id("パンチ"), money=40, bought=True)
    assert cheap.affordable
    broke = BuyDecision(card_id("神の盾"), money=0, bought=False)
    assert not broke.affordable


# --- 売る ------------------------------------------------------------------


def test_the_sell_choice_records_what_was_available():
    obs = blank()
    set_phase(obs, PHASE_SELL_SELECT)
    obs[0, fc.HAND_CARDS_START : fc.HAND_CARDS_START + 3] = [
        card_id("パンチ"), card_id("神の盾"), card_id("革の帽子")
    ]
    obs[0, fc.STAT_START + 5] = 3 / STAT_SCALE   # 相手の所持金
    obs[0, fc.STAT_START + 3] = 1 / STAT_SCALE   # 相手のMP

    mask = np.zeros((1, godfield_core.ACTION_SPACE_SIZE), dtype=bool)
    mask[0, 0:3] = True
    probe = TradeProbe(Fixed(0), sell_card_id())  # スロット0（パンチ）を選ぶ
    probe.act(obs, mask)

    assert len(probe.stats.sells) == 1
    sell = probe.stats.sells[0]
    assert sell.picked == card_id("パンチ")
    assert sorted(sell.choices) == sorted(
        [card_id("パンチ"), card_id("神の盾"), card_id("革の帽子")]
    )
    assert sell.opponent_can_pay == 4


def test_a_single_choice_is_not_a_decision():
    obs = blank()
    set_phase(obs, PHASE_SELL_SELECT)
    obs[0, fc.HAND_CARDS_START] = card_id("パンチ")
    mask = np.zeros((1, godfield_core.ACTION_SPACE_SIZE), dtype=bool)
    mask[0, 0] = True

    probe = TradeProbe(Fixed(0), sell_card_id())
    probe.act(obs, mask)

    assert probe.stats.sells == []


def test_damage_is_what_the_opponent_cannot_pay():
    """支払いは お金 -> MP -> HP。足りないぶんが HP から引かれる。"""
    sell = SellDecision(card_id("神の盾"), [card_id("神の盾")], opp_money=3, opp_mp=2)
    assert sell.opponent_can_pay == 5
    assert sell.damage(20) == 15
    assert sell.damage(4) == 0


def test_took_best_compares_prices():
    cheap, pricey = card_id("パンチ"), card_id("神の盾")
    assert price_of(pricey) > price_of(cheap)
    assert SellDecision(pricey, [cheap, pricey], 0, 0).took_best
    assert not SellDecision(cheap, [cheap, pricey], 0, 0).took_best


def test_sell_target_is_only_counted_when_sell_is_staged():
    """対象選択フェイズは武器でも使う。売るが仮置きされている局面だけを拾う。"""
    obs = blank(2)
    set_phase(obs, PHASE_TARGET_SELECT)
    obs[0, fc.STAGED_CARDS_START] = sell_card_id()
    obs[1, fc.STAGED_CARDS_START] = card_id("パンチ")

    probe = TradeProbe(Fixed(ACTION_TARGET_SELF), sell_card_id())
    probe.act(obs, np.ones((2, godfield_core.ACTION_SPACE_SIZE), dtype=bool))

    assert probe.stats.sold_to_self == [True]


# --- 上書き ----------------------------------------------------------------


def test_override_buys_a_free_miracle():
    obs = blank()
    set_phase(obs, PHASE_BUY)
    obs[0, fc.OPP_STAGED_CARDS_START] = card_id("＜氷＞")  # 奇跡は値段0

    override = TradeOverride(Fixed(godfield_core.ACTION_DEAL_NO), sell_card_id(),
                             buy_obvious=True)
    actions = override.act(obs, full_mask())

    assert int(actions[0]) == ACTION_DEAL_YES
    assert override.changed == 1


def test_override_does_not_buy_what_it_cannot_afford():
    obs = blank()
    set_phase(obs, PHASE_BUY)
    obs[0, fc.OPP_STAGED_CARDS_START] = card_id("革の帽子")
    obs[0, fc.STAT_START + 4] = 0.0  # 所持金0

    override = TradeOverride(Fixed(godfield_core.ACTION_DEAL_NO), sell_card_id(),
                             buy_obvious=True)
    actions = override.act(obs, full_mask())

    assert int(actions[0]) == godfield_core.ACTION_DEAL_NO
    assert override.changed == 0


def test_override_picks_the_most_expensive_card():
    obs = blank()
    set_phase(obs, PHASE_SELL_SELECT)
    obs[0, fc.HAND_CARDS_START : fc.HAND_CARDS_START + 2] = [
        card_id("パンチ"), card_id("神の盾")
    ]
    mask = np.zeros((1, godfield_core.ACTION_SPACE_SIZE), dtype=bool)
    mask[0, 0:2] = True

    override = TradeOverride(Fixed(0), sell_card_id(), sell_highest=True)
    actions = override.act(obs, mask)

    assert int(actions[0]) == 1  # 神の盾のスロット


def test_override_leaves_other_phases_alone():
    """武器の対象選択には触らない（売るが仮置きされていない）。"""
    obs = blank()
    set_phase(obs, PHASE_TARGET_SELECT)
    obs[0, fc.STAGED_CARDS_START] = card_id("パンチ")

    override = TradeOverride(Fixed(ACTION_TARGET_SELF), sell_card_id(),
                             sell_to_opponent=True)
    actions = override.act(obs, full_mask())

    assert int(actions[0]) == ACTION_TARGET_SELF
    assert override.changed == 0


def test_override_redirects_a_sell_to_the_opponent():
    obs = blank()
    set_phase(obs, PHASE_TARGET_SELECT)
    obs[0, fc.STAGED_CARDS_START] = sell_card_id()

    override = TradeOverride(Fixed(ACTION_TARGET_SELF), sell_card_id(),
                             sell_to_opponent=True)
    actions = override.act(obs, full_mask())

    assert int(actions[0]) == ACTION_TARGET_OPP
    assert override.changed == 1


@pytest.mark.parametrize("flag", ["buy_obvious", "sell_to_opponent", "sell_highest"])
def test_nothing_changes_when_the_flag_is_off(flag):
    obs = blank()
    set_phase(obs, PHASE_BUY)
    obs[0, fc.OPP_STAGED_CARDS_START] = card_id("＜氷＞")

    override = TradeOverride(Fixed(godfield_core.ACTION_DEAL_NO), sell_card_id(),
                             **{f: False for f in [flag]})
    override.act(obs, full_mask())

    assert override.changed == 0
