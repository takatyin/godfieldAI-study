"""手書き方策の、取引と廃棄の方針。

これらのフェイズには方針が無く、act() の既定（ランダムな合法手）が
そのまま採用されていました。実測で判断の 8.9% がランダムに落ちており、
無料のカードを半々でしか買わない・防具を捨てる、といった手を
学習者に教えていました。
"""

import numpy as np
import pytest

import godfield_core
from godfield_rl import feature_config as fc
from godfield_rl.cards import card_id
from godfield_rl.strategy import (
    ACTION_DEAL_NO,
    ACTION_DEAL_YES,
    ACTION_DISCARD,
    ACTION_HAND_0,
    DISCARD_HAND_SIZE,
    StrategicOpponent,
)

A = godfield_core.ActionType
P = godfield_core.GamePhase
OBS_SIZE = godfield_core.OBSERVATION_FEATURE_SIZE - godfield_core.ACTION_SPACE_SIZE


def make_obs(phase, hand=(), opp_staged=(), hp=40, mp=40, money=40) -> np.ndarray:
    obs = np.zeros(OBS_SIZE, dtype=np.float32)
    obs[fc.PHASE_START + int(phase)] = 1.0
    obs[fc.STAT_START] = hp / 100.0
    obs[fc.STAT_START + 2] = mp / 100.0
    obs[fc.STAT_START + 4] = money / 100.0
    for block in (fc.HAND_CARDS_START, fc.STAGED_CARDS_START,
                  fc.OPP_HAND_CARDS_START, fc.OPP_STAGED_CARDS_START):
        obs[block : block + fc.MAX_HAND_SIZE] = -1
    for i, name in enumerate(hand):
        obs[fc.HAND_CARDS_START + i] = card_id(name)
    for i, name in enumerate(opp_staged):
        obs[fc.OPP_STAGED_CARDS_START + i] = card_id(name)
    return obs


def make_mask(*, hand_slots=(), deal=False, discard=False) -> np.ndarray:
    mask = np.zeros(godfield_core.ACTION_SPACE_SIZE, dtype=bool)
    for i in hand_slots:
        mask[ACTION_HAND_0 + i] = True
    if deal:
        mask[ACTION_DEAL_YES] = True
        mask[ACTION_DEAL_NO] = True
    if discard:
        mask[ACTION_DISCARD] = True
    return mask


def act(obs, mask):
    return StrategicOpponent(seed=0)._act_row(obs, mask)


# --- 買うか断るか -----------------------------------------------------------


@pytest.mark.parametrize("card", ["＜氷＞", "＜火の玉＞"])
def test_miracles_are_always_bought(card):
    obs = make_obs(P.PHASE_BUY, opp_staged=[card])
    assert act(obs, make_mask(deal=True)) == ACTION_DEAL_YES


@pytest.mark.parametrize("card", ["神の盾", "アイアンアーマー"])
def test_armor_is_always_bought(card):
    """防具は30円の神の盾でも買う。"""
    obs = make_obs(P.PHASE_BUY, opp_staged=[card])
    assert act(obs, make_mask(deal=True)) == ACTION_DEAL_YES


def test_cheap_cards_are_bought():
    obs = make_obs(P.PHASE_BUY, opp_staged=["スマイルの貝がら"])  # 5円
    assert act(obs, make_mask(deal=True)) == ACTION_DEAL_YES


def test_expensive_non_armor_is_declined():
    obs = make_obs(P.PHASE_BUY, opp_staged=["神の剣"])  # 武器30円
    assert act(obs, make_mask(deal=True)) == ACTION_DEAL_NO


def test_buying_happens_even_with_a_full_hand():
    """満杯でも買う。自分のカードが1枚置き換わるより、相手の手札を削るほうが大きい。"""
    obs = make_obs(P.PHASE_BUY, hand=["パンチ"] * fc.MAX_HAND_SIZE, opp_staged=["＜氷＞"])
    assert act(obs, make_mask(deal=True)) == ACTION_DEAL_YES


def test_unknown_offer_is_declined_not_random():
    """読めない提示でも None を返さない（None はランダムに落ちる）。"""
    obs = make_obs(P.PHASE_BUY)
    assert act(obs, make_mask(deal=True)) == ACTION_DEAL_NO


# --- 何を売るか -------------------------------------------------------------


def test_the_most_expensive_item_is_offered():
    hand = ["売る", "パンチ", "神の盾", "ハートの貝がら"]
    obs = make_obs(P.PHASE_SELL_SELECT, hand=hand)
    chosen = act(obs, make_mask(hand_slots=range(len(hand))))
    assert chosen == ACTION_HAND_0 + 2, "神の盾(30円)を出すはず"


def test_deal_cards_are_never_offered():
    hand = ["売る", "買う", "両替", "ハートの貝がら"]
    obs = make_obs(P.PHASE_SELL_SELECT, hand=hand)
    chosen = act(obs, make_mask(hand_slots=range(len(hand))))
    assert chosen == ACTION_HAND_0 + 3


def test_something_is_always_offered_even_if_all_cheap():
    """15円以上が無くても出品は必要。None だとランダムに落ちる。"""
    hand = ["売る", "パンチ", "スマイルのしずく"]
    obs = make_obs(P.PHASE_SELL_SELECT, hand=hand)
    assert act(obs, make_mask(hand_slots=range(len(hand)))) is not None


# --- 何を捨てるか -----------------------------------------------------------


def test_excess_exchange_cards_are_discarded_first():
    """両替は2枚まで残す。"""
    hand = ["両替", "両替", "両替", "神の盾"]
    obs = make_obs(P.PHASE_DISCARD, hand=hand)
    chosen = act(obs, make_mask(hand_slots=range(len(hand))))
    assert chosen in (ACTION_HAND_0, ACTION_HAND_0 + 1, ACTION_HAND_0 + 2)


@pytest.mark.parametrize("card", ["買う", "売る", "スマイルの貝がら"])
def test_duplicate_utility_cards_are_discarded(card):
    """買う・売る・スマイルの貝がらは1枚まで。"""
    hand = [card, card, "神の盾"]
    obs = make_obs(P.PHASE_DISCARD, hand=hand)
    chosen = act(obs, make_mask(hand_slots=range(len(hand))))
    assert chosen in (ACTION_HAND_0, ACTION_HAND_0 + 1)


def test_weak_miracles_are_discarded_before_armor():
    hand = ["神の盾", "＜歌声＞", "＜氷＞"]
    obs = make_obs(P.PHASE_DISCARD, hand=hand)
    chosen = act(obs, make_mask(hand_slots=range(len(hand))))
    assert chosen == ACTION_HAND_0 + 1, "弱い奇跡＜歌声＞を捨てるはず"


def test_strong_miracles_are_kept():
    hand = ["＜氷＞", "＜オーラ＞", "スマイルのしずく"]
    obs = make_obs(P.PHASE_DISCARD, hand=hand)
    chosen = act(obs, make_mask(hand_slots=range(len(hand))))
    assert chosen == ACTION_HAND_0 + 2, "強い奇跡ではなく雑貨を捨てるはず"


def test_armor_is_discarded_last():
    """該当カードが無くても、防具より先に他を捨てる。"""
    hand = ["神の盾", "スマイルのしずく"]
    obs = make_obs(P.PHASE_DISCARD, hand=hand)
    chosen = act(obs, make_mask(hand_slots=range(len(hand))))
    assert chosen == ACTION_HAND_0 + 1


def test_discard_never_falls_back_to_random():
    """防具しか無くても必ず答えを返す（None はランダムに落ちる）。"""
    hand = ["神の盾", "アイアンアーマー"]
    obs = make_obs(P.PHASE_DISCARD, hand=hand)
    assert act(obs, make_mask(hand_slots=range(len(hand)))) is not None


# --- いつ捨てるか -----------------------------------------------------------


def test_discard_is_chosen_when_the_hand_overflows():
    hand = ["パンチ"] * (DISCARD_HAND_SIZE + 1)
    obs = make_obs(P.PHASE_MAIN, hand=hand)
    mask = make_mask(hand_slots=range(len(hand)), discard=True)
    assert act(obs, mask) == ACTION_DISCARD


def test_discard_is_not_chosen_with_room_to_spare():
    hand = ["パンチ"] * DISCARD_HAND_SIZE
    obs = make_obs(P.PHASE_MAIN, hand=hand)
    mask = make_mask(hand_slots=range(len(hand)), discard=True)
    assert act(obs, mask) != ACTION_DISCARD
