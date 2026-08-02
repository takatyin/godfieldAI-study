"""手書き方策が、自分を害する手を指さないこと。

対戦中に2つ報告された。

  1. カードを全部捨てる
     捨てるフェイズは ACTION_CONFIRM で初めて廃棄が実行される仕様なのに、
     方針が確定を返さず手札スロットを選び続けていた。選べるスロットが
     無くなるまで仮置きするので、結果として手札が空になる。

  2. 自分に攻撃する
     20%の探索が「行動そのもの」をランダムにしていたため、対象選択まで
     乱れていた。実測で武器の対象の 10.9% が自分に向いていた
     （探索を切ると 0%）。多様性は「どのカードを出すか」だけで出せばよい。
"""

import numpy as np
import pytest

import godfield_core
from godfield_rl import feature_config as fc
from godfield_rl.cards import card_id
from godfield_rl.strategy import (
    ACTION_CONFIRM,
    ACTION_HAND_0,
    ACTION_TARGET_OPP,
    ACTION_TARGET_SELF,
    StrategicOpponent,
)

P = godfield_core.GamePhase
OBS_SIZE = godfield_core.OBSERVATION_FEATURE_SIZE - godfield_core.ACTION_SPACE_SIZE
MAX_HAND = fc.MAX_HAND_SIZE


def make_obs(phase, hand=(), staged=()) -> np.ndarray:
    obs = np.zeros(OBS_SIZE, dtype=np.float32)
    obs[fc.PHASE_START + int(phase)] = 1.0
    obs[fc.STAT_START] = 0.4      # hp
    obs[fc.STAT_START + 2] = 0.4  # mp
    obs[fc.STAT_START + 4] = 0.4  # money
    for block in (fc.HAND_CARDS_START, fc.STAGED_CARDS_START,
                  fc.OPP_HAND_CARDS_START, fc.OPP_STAGED_CARDS_START):
        obs[block : block + MAX_HAND] = -1
    for i, name in enumerate(hand):
        obs[fc.HAND_CARDS_START + i] = card_id(name)
    for i, name in enumerate(staged):
        obs[fc.STAGED_CARDS_START + i] = card_id(name)
    return obs


def make_mask(*, hand_slots=(), actions=()) -> np.ndarray:
    """合法手マスク。許す行動を添字で明示します。

    行動空間は添字を使い回していて、意味はフェイズで決まります
    （ACTION_CONFIRM と ACTION_TARGET_SELF はどちらも 19、
      ACTION_TARGET_OPP と ACTION_DEAL_YES はどちらも 18）。
    真偽値の引数ごとに代入すると、後の行が前の行を False で上書きします。
    """
    mask = np.zeros(godfield_core.ACTION_SPACE_SIZE, dtype=bool)
    for i in hand_slots:
        mask[ACTION_HAND_0 + i] = True
    for a in actions:
        mask[a] = True
    return mask


CONFIRM_ONLY = (ACTION_CONFIRM,)
BOTH_TARGETS = (ACTION_TARGET_OPP, ACTION_TARGET_SELF)


def act(obs, mask, explore_rate=0.0):
    return StrategicOpponent(seed=0, explore_rate=explore_rate)._act_row(obs, mask)


# --- 全部捨てる ---------------------------------------------------------


def test_discard_confirms_once_candidates_run_out():
    """捨てる候補が無くなったら確定する。確定しないと全部捨ててしまう。"""
    hand = ["神の盾", "アイアンアーマー"]          # どれも捨てたくないもの
    obs = make_obs(P.PHASE_DISCARD, hand=hand, staged=["スマイルのしずく"])
    chosen = act(obs, make_mask(hand_slots=range(len(hand)), actions=CONFIRM_ONLY))
    assert chosen == ACTION_CONFIRM


def test_discard_confirms_when_nothing_is_selectable():
    obs = make_obs(P.PHASE_DISCARD, hand=["神の盾"], staged=["両替"])
    assert act(obs, make_mask(actions=CONFIRM_ONLY)) == ACTION_CONFIRM


def test_discard_still_picks_the_first_card_before_confirming():
    """1枚も仮置きしていないうちは確定せず、捨てるものを選ぶ。"""
    hand = ["両替", "両替", "両替"]
    obs = make_obs(P.PHASE_DISCARD, hand=hand)
    chosen = act(obs, make_mask(hand_slots=range(len(hand)), actions=CONFIRM_ONLY))
    assert chosen != ACTION_CONFIRM
    assert chosen in [ACTION_HAND_0 + i for i in range(3)]


def test_discarding_terminates_instead_of_emptying_the_hand():
    """仮置きが進むにつれ確定に向かい、手札を空にしないこと。

    実際の進行と同じく、選んだスロットを毎回マスクから外していく。
    """
    hand = ["両替", "両替", "両替", "神の盾", "アイアンアーマー"]
    remaining = set(range(len(hand)))
    staged: list[str] = []

    for _ in range(len(hand) + 2):
        obs = make_obs(P.PHASE_DISCARD, hand=hand, staged=staged)
        chosen = act(obs, make_mask(hand_slots=sorted(remaining), actions=CONFIRM_ONLY))
        if chosen == ACTION_CONFIRM:
            break
        slot = chosen - ACTION_HAND_0
        remaining.discard(slot)
        staged.append(hand[slot])
    else:
        pytest.fail("確定に到達せず、手札を選び続けています")

    assert remaining, "手札が空になっています"
    # 両替は2枚残す方針なので、捨てるのは1枚だけ
    assert staged == ["両替"], f"捨てすぎです: {staged}"


# --- 自分に攻撃する -----------------------------------------------------


@pytest.mark.parametrize("phase", [P.PHASE_ATTACK_PLUS, P.PHASE_MAIN_TARGET_SELECT])
def test_weapons_never_target_yourself(phase):
    obs = make_obs(phase, staged=["パンチ"])
    assert act(obs, make_mask(actions=BOTH_TARGETS)) == ACTION_TARGET_OPP


def test_exploration_never_changes_the_target():
    """20%の探索が対象選択を乱さないこと。乱すと自分に攻撃する。"""
    opponent = StrategicOpponent(seed=0, explore_rate=1.0)   # 常に探索
    obs = make_obs(P.PHASE_ATTACK_PLUS, staged=["パンチ"])
    mask = make_mask(actions=BOTH_TARGETS)

    actions = opponent.act(np.repeat(obs[None], 200, axis=0), np.repeat(mask[None], 200, axis=0))
    assert not (actions == ACTION_TARGET_SELF).any(), "探索で自分に攻撃しています"


def test_exploration_still_varies_the_card_choice():
    """多様性そのものは残っていること（カード選びで出す）。"""
    hand = ["パンチ", "アイアンアーマー", "スマイルのしずく", "＜氷＞"]
    obs = make_obs(P.PHASE_MAIN, hand=hand)
    mask = make_mask(hand_slots=range(len(hand)))

    always = StrategicOpponent(seed=0, explore_rate=1.0)
    picks = set(always.act(np.repeat(obs[None], 200, axis=0), np.repeat(mask[None], 200, axis=0)))
    assert len(picks) > 1, "探索しても手札の選択が1つに固まっています"


def test_exploration_does_not_invent_illegal_actions():
    hand = ["パンチ", "アイアンアーマー"]
    obs = make_obs(P.PHASE_MAIN, hand=hand)
    mask = make_mask(hand_slots=range(len(hand)))

    opponent = StrategicOpponent(seed=1, explore_rate=1.0)
    actions = opponent.act(np.repeat(obs[None], 100, axis=0), np.repeat(mask[None], 100, axis=0))
    assert all(mask[a] for a in actions)
