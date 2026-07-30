"""人手の戦略で指す相手（StrategicOpponent）の検証。

この方策は学習の初期対戦相手になるので、間違っていると学習者がその間違いを
覚えます。実際、旧 HeuristicOpponent が対象選択で常に「相手」を選んでいたために、
学習済みモデルが回復系の雑貨を相手に使うようになっていました。
"""

import numpy as np
import pytest

import godfield_core
from godfield_rl import feature_config as fc
from godfield_rl.cards import all_cards, card_id
from godfield_rl.opponents import make_opponent
from godfield_rl.strategy import (
    OPPONENT_SUNDRIES,
    STRONG_ATTACK_MIRACLES,
    STRONG_PLUS_MIRACLES,
    STRONG_SELF_MIRACLES,
    StrategicOpponent,
    exchange_allocation,
)

ACTION_TARGET_OPP = int(godfield_core.ActionType.ACTION_TARGET_OPP)
ACTION_TARGET_SELF = int(godfield_core.ActionType.ACTION_TARGET_SELF)
PHASE_TARGET_SELECT = int(godfield_core.GamePhase.PHASE_MAIN_TARGET_SELECT)


def test_named_cards_all_exist_in_the_card_data():
    """戦略で名指ししたカードが全部カードマスタに存在することを検証します。

    名前が1文字でも違うと、そのカードは永久に選ばれないのに例外も出ません
    （実際『女神の石鹸』は正しくは『女神の石けん』でした）。
    """
    known = {c["id"] for c in all_cards()}
    named = STRONG_ATTACK_MIRACLES | STRONG_PLUS_MIRACLES | STRONG_SELF_MIRACLES | OPPONENT_SUNDRIES
    assert named <= known
    assert len(STRONG_ATTACK_MIRACLES) == 7
    assert len(STRONG_PLUS_MIRACLES) == 4
    assert len(STRONG_SELF_MIRACLES) == 2
    assert len(OPPONENT_SUNDRIES) == 2


def test_card_id_raises_for_a_wrong_name():
    """存在しないカード名を書いたら例外になることを検証します。"""
    with pytest.raises(KeyError, match="女神の石鹸"):
        card_id("女神の石鹸")   # 正しくは『女神の石けん』


@pytest.mark.parametrize(
    ("total", "expected"),
    [
        (0, (0, 0, 0)),
        (30, (30, 0, 0)),
        (40, (40, 0, 0)),      # 40までは全部HP
        (50, (40, 10, 0)),     # 超えたぶんはMPへ（15まで）
        (60, (40, 15, 5)),     # MPが埋まったらお金へ（10まで）
        (70, (45, 15, 10)),
        (80, (55, 15, 10)),    # さらに余ったらHPへ戻す
    ],
)
def test_exchange_allocation_prioritises_hp(total, expected):
    """両替の配分がHP優先であることを検証します。

    両替を使うのは「HPが20を切ったとき」なので、MPを先に取るとHPがさらに減って
    本末転倒になります。
    """
    assert exchange_allocation(total) == expected
    assert sum(exchange_allocation(total)) == total


def test_exchange_allocation_conserves_the_total():
    """どの合計値でも、配分の合計が元の値と一致することを検証します。"""
    for total in range(0, 200):
        assert sum(exchange_allocation(total)) == total


def _target_select_obs(staged_card: int) -> np.ndarray:
    """対象選択フェイズの観測を最小限だけ組み立てます。"""
    obs = np.zeros(fc.TOTAL_OBSERVATION_FEATURE_SIZE_NO_MASK, dtype=np.float32)
    obs[fc.PHASE_START + PHASE_TARGET_SELECT] = 1.0
    obs[fc.HAND_CARDS_START : fc.HAND_CARDS_START + fc.MAX_HAND_SIZE] = -1
    obs[fc.STAGED_CARDS_START : fc.STAGED_CARDS_START + fc.MAX_HAND_SIZE] = -1
    obs[fc.STAGED_CARDS_START] = staged_card
    return obs


@pytest.mark.parametrize(
    ("card", "expect_opp"),
    [
        ("＜炎＞", True),          # 攻撃奇跡は相手へ
        ("売る", True),
        ("買う", True),
        ("女神の石けん", True),     # 相手の奇跡を壊す
        ("夜空のホウキ", True),     # 相手の手札を飛ばす
        ("ハートのしずく", False),  # 回復は自分へ
        ("スマイルの花", False),
        ("＜泉＞", False),
        ("＜財宝＞", False),
        ("守護封印のつぼ", False),
    ],
)
def test_target_selection_matches_the_card_purpose(card, expect_opp):
    """カードの性質どおりに対象を選ぶことを検証します。

    旧 HeuristicOpponent はここで常に「相手」を選んでおり、回復系の雑貨を
    相手に使っていました。
    """
    # 探索でぶれないよう、ルールを必ず適用させる
    policy = StrategicOpponent(seed=0, explore_rate=0.0)
    obs = _target_select_obs(card_id(card))[None, :]
    masks = np.zeros((1, godfield_core.ACTION_SPACE_SIZE), dtype=bool)
    masks[0, ACTION_TARGET_OPP] = True
    masks[0, ACTION_TARGET_SELF] = True

    action = int(policy.act(obs, masks)[0])

    expected = ACTION_TARGET_OPP if expect_opp else ACTION_TARGET_SELF
    assert action == expected, (
        f"{card} の対象が想定と違います:"
        f" {'相手' if action == ACTION_TARGET_OPP else '自分'} を選びました"
    )


def test_explore_rate_makes_the_policy_deviate():
    """explore_rate の分だけルールを外すことを検証します。

    完全に決定的だと、学習者が1つの相手に過適合します。
    """
    obs = np.repeat(_target_select_obs(card_id("ハートのしずく"))[None, :], 400, axis=0)
    masks = np.zeros((400, godfield_core.ACTION_SPACE_SIZE), dtype=bool)
    masks[:, ACTION_TARGET_OPP] = True
    masks[:, ACTION_TARGET_SELF] = True

    strict = StrategicOpponent(seed=0, explore_rate=0.0).act(obs, masks)
    assert (strict == ACTION_TARGET_SELF).all(), "explore_rate=0 なら必ずルールどおり"

    loose = StrategicOpponent(seed=0, explore_rate=1.0).act(obs, masks)
    assert (loose == ACTION_TARGET_OPP).mean() > 0.2, (
        "explore_rate=1 ならルールを外してランダムに選ぶはず"
    )


def test_strategic_opponent_beats_the_old_heuristic():
    """新しい戦略が、旧ヒューリスティックに明確に勝ち越すことを検証します。

    学習の初期対戦相手を差し替える以上、実際に強くなっていないと意味がありません。
    """
    all_cards()
    num_envs = 32
    pool = godfield_core.EnvPool(num_envs)
    pool.reset(0)
    players = {0: make_opponent("strategic", 0), 1: make_opponent("heuristic", 1)}

    fdim = godfield_core.OBSERVATION_FEATURE_SIZE
    adim = godfield_core.ACTION_SPACE_SIZE
    wins = games = 0

    for _ in range(4000):
        obs_all = pool.get_observations().reshape(num_envs, -1)
        obs = obs_all[:, : fdim - adim]
        masks = obs_all[:, fdim - adim : fdim].astype(bool)
        actors = pool.get_current_actors()
        actions = np.zeros(num_envs, dtype=np.int32)
        for seat, policy in players.items():
            idx = np.flatnonzero(actors == seat)
            if idx.size:
                actions[idx] = policy.act(obs[idx], masks[idx])
        pool.step_all(actions)

        dones = pool.get_dones()
        if dones.any():
            rewards = pool.get_rewards_for(0)
            for i in np.flatnonzero(dones):
                games += 1
                wins += rewards[i] > 0
        if games >= 200:
            break

    assert games >= 100, f"対戦が進んでいません（{games}局）"
    win_rate = wins / games
    assert win_rate > 0.6, f"旧ヒューリスティックに勝ち越せていません（勝率 {win_rate:.1%}）"


def test_it_does_not_produce_illegal_actions():
    """どのフェイズでも、返す行動が必ず合法手であることを検証します。

    非合法手を返すと C++ 側は黙って無視するので、方策が壊れていても
    「なぜか弱い」としか分かりません。
    """
    all_cards()
    num_envs = 32
    pool = godfield_core.EnvPool(num_envs)
    pool.reset(1)
    policy = make_opponent("strategic", 0)
    fdim = godfield_core.OBSERVATION_FEATURE_SIZE
    adim = godfield_core.ACTION_SPACE_SIZE

    phases_seen = set()
    for _ in range(1500):
        obs_all = pool.get_observations().reshape(num_envs, -1)
        obs = obs_all[:, : fdim - adim]
        masks = obs_all[:, fdim - adim : fdim].astype(bool)
        actions = policy.act(obs, masks)
        assert masks[np.arange(num_envs), actions].all(), "非合法手を返しました"
        for row in obs:
            phases_seen.add(int(np.argmax(row[fc.PHASE_START : fc.PHASE_START + fc.PHASE_LEN])))
        pool.step_all(actions.astype(np.int32))

    assert len(phases_seen) >= 6, (
        f"踏んだフェイズが少なすぎます（{sorted(phases_seen)}）。"
        f" 検証できていない経路が多い可能性があります"
    )
