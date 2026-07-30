"""ポテンシャルベースの報酬シェーピングの検証。

シェーピングの要点は「最適方策を変えないこと」で、それは
`r' = r + γΦ(s') − Φ(s)` という形に依存しています。形が崩れると保証も消えるので、
ここで固定します。

torch を必要としないので、学習まわりの依存を入れない CI でも実行されます。
"""

import numpy as np
import pytest

import godfield_core
from godfield_rl.shaping import STAT_SCALE, PotentialShaper, make_shaper


def test_make_shaper_returns_none_when_all_weights_are_zero():
    """重みが全部0ならシェーピング無しとして扱われることを検証します。"""
    assert make_shaper(0.0, 0.0, 0.0, gamma=0.995) is None
    assert make_shaper(0.2, 0.0, 0.0, gamma=0.995) is not None


@pytest.mark.parametrize("seat", [0, 1])
def test_potential_is_the_weighted_difference_from_the_learner_side(seat):
    """Φ が「自分 − 相手」の重み付き差であり、席によって符号が反転することを検証します。

    絶対値だと双方が伸びる局面まで報われてしまうため、差であることが要点です。
    """
    shaper = PotentialShaper(hp=0.2, mp=0.1, money=0.05, gamma=0.995)
    # [p0_hp, p0_mp, p0_money, p1_hp, p1_mp, p1_money]
    stats = np.array([[40, 10, 20, 30, 5, 8]], dtype=np.int32)

    phi = shaper.potential(stats, learner_seat=seat)

    sign = 1.0 if seat == 0 else -1.0
    expected = sign * (0.2 * (40 - 30) + 0.1 * (10 - 5) + 0.05 * (20 - 8)) / STAT_SCALE
    assert phi.shape == (1,)
    assert phi[0] == pytest.approx(expected, rel=1e-5)


def test_potential_is_zero_sum_between_the_two_seats():
    """同じ盤面を両席から見ると、Φ の符号だけが反転することを検証します。"""
    shaper = PotentialShaper(hp=0.2, mp=0.1, money=0.05, gamma=0.995)
    stats = np.array([[40, 10, 20, 30, 5, 8], [1, 2, 3, 4, 5, 6]], dtype=np.int32)

    assert shaper.potential(stats, 0) == pytest.approx(-shaper.potential(stats, 1))


def test_shaping_telescopes_to_zero_over_a_non_terminal_path():
    """途中の Φ が打ち消し合うことを検証します。

    これが成り立つから「シェーピングを稼いで勝たない」方策が得をしません。
    割引を1にすると、経路上の合計は Φ(終点) − Φ(始点) にしかなりません。
    """
    shaper = PotentialShaper(hp=1.0, gamma=1.0)
    phis = [0.1, 0.4, -0.2, 0.3, 0.25]
    not_terminated = np.array([False])

    total = 0.0
    for prev, nxt in zip(phis, phis[1:]):
        total += float(
            shaper.shape(np.array([prev]), np.array([nxt]), not_terminated)[0]
        )

    assert total == pytest.approx(phis[-1] - phis[0], abs=1e-6)


def test_shaping_treats_the_terminal_next_potential_as_zero():
    """終端では Φ(s') を0として扱うことを検証します。

    終端の先には遷移が無く、自動リセット後の「次の局」の Φ を拾ってしまうと、
    局のまたぎで偽の報酬が入ります。
    """
    shaper = PotentialShaper(hp=1.0, gamma=0.9)
    prev = np.array([0.5, 0.5])
    nxt = np.array([0.8, 0.8])
    terminated = np.array([False, True])

    shaped = shaper.shape(prev, nxt, terminated)

    assert shaped[0] == pytest.approx(0.9 * 0.8 - 0.5)
    assert shaped[1] == pytest.approx(0.0 - 0.5)


def test_healing_the_opponent_produces_a_negative_shaping_reward():
    """相手を回復させると、その場で負のシェーピング報酬が出ることを検証します。

    これが今回シェーピングを入れる目的そのものです。終端の勝敗だけでは
    「回復系の雑貨を相手に使う」が咎められず、実際に学習済みモデルは
    対象選択の100%で相手を選ぶまで潰れていました。
    """
    shaper = PotentialShaper(hp=0.2, gamma=1.0)
    before = np.array([[40, 0, 0, 40, 0, 0]], dtype=np.int32)
    after = np.array([[40, 0, 0, 50, 0, 0]], dtype=np.int32)  # 相手だけ +10

    phi_before = shaper.potential(before, learner_seat=0)
    phi_after = shaper.potential(after, learner_seat=0)
    shaped = shaper.shape(phi_before, phi_after, np.array([False]))

    assert shaped[0] < 0
    assert shaped[0] == pytest.approx(-0.2 * 10 / STAT_SCALE, rel=1e-5)


def test_player_stats_reports_the_true_values_even_under_fog():
    """霧がかかっていても、真の HP/MP/お金 が取れることを検証します。

    観測（get_observations）は霧で相手の値が0に潰れます。そこからポテンシャルを
    作ると、霧を付与・解除するだけで巨大な偽の報酬が出てしまいます。
    シェーピングが観測ではなくこちらを使う理由です。
    """
    pool = godfield_core.EnvPool(1)
    pool.reset(0)
    state = pool.get_state(0)
    state.set_hp(0, 33)
    state.set_hp(1, 44)
    state.set_mp(1, 7)
    state.set_money(1, 21)
    state.set_curses(0, godfield_core.CurseType.CURSE_FOG, True)  # P0 が霧
    pool.set_state(0, state)

    stats = pool.get_player_stats()
    assert stats.shape == (1, 6)
    assert list(stats[0]) == [33, state.get_mp(0), state.get_money(0), 44, 7, 21]

    # 一方、観測では相手（P1）の値が隠れている
    obs = godfield_core.get_observation(pool.get_state(0), 0)
    assert obs.hp_opp == 0.0, "霧がかかっていれば観測では相手のHPは見えない"
