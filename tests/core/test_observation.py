"""強化学習エージェントへ渡す観測（Observation）の検証。

【移行メモ】
従来はカードIDが数値で直書きされており、しかもコメントが実データと食い違って
いました（`sim.state.set_true_hand(0, 0, 0)  # weapons/bronze-club` とあるが、
ID 0 は実際には「両替」）。カード名から引くようにして、この種のズレを防ぎます。

フェイズ one-hot の長さやインデックスも GamePhase enum から導出するようにし、
フェイズを追加したときにテストが黙って別の位置を検証しないようにしています。
"""

import copy

import numpy as np
import pytest

import godfield_core
from godfield_core import CurseType, GamePhase
from tests.core.dsl import Side, card_feature, card_id

# 観測は各値を 1/100 に正規化して渡す（HP 40 -> 0.4）
NORMALIZE = 100.0


def test_observation_normalizes_status_values(board):
    """HP・MP・お金が観測へ正規化して渡されることを検証します。"""
    g = board(
        p0=Side(hp=40, mp=10, money=20, hand=["deals/exchange", "deals/sell"]),
        p1=Side(hp=35, mp=15, money=25),
    )

    obs = godfield_core.get_observation(g.state, 0)

    assert obs.hp_me == pytest.approx(40 / NORMALIZE)
    assert obs.hp_opp == pytest.approx(35 / NORMALIZE)
    assert obs.mp_me == pytest.approx(10 / NORMALIZE)
    assert obs.mp_opp == pytest.approx(15 / NORMALIZE)
    assert obs.money_me == pytest.approx(20 / NORMALIZE)
    assert obs.money_opp == pytest.approx(25 / NORMALIZE)


def test_observation_exposes_hand_cards_by_slot(board):
    """手札がスロット順にカードIDとして観測へ載り、空きスロットが -1 になることを検証します。"""
    g = board(
        p0=Side(hp=40, hand=["deals/exchange", "deals/sell"]),
        p1=Side(hp=35),
    )

    hand = godfield_core.get_observation(g.state, 0).get_hand_cards()

    assert hand[0] == card_id("deals/exchange")
    assert hand[1] == card_id("deals/sell")
    assert hand[2] == godfield_core.CARD_EMPTY


def test_observation_is_copyable_and_convertible_to_numpy(board):
    """観測がコピー可能で、float32 の1次元配列へ変換できることを検証します。"""
    g = board(p0=Side(hp=40, mp=10, money=20), p1=Side(hp=35, mp=15, money=25))
    obs = godfield_core.get_observation(g.state, 0)

    assert copy.copy(obs).hp_me == pytest.approx(40 / NORMALIZE)

    arr = obs.to_numpy()
    assert isinstance(arr, np.ndarray)
    assert arr.dtype == np.float32
    assert arr.shape == (godfield_core.OBSERVATION_SIZE,)
    # 先頭2要素は hp_me, hp_opp（構造体の並びと一致していること）
    assert arr[0] == pytest.approx(40 / NORMALIZE)
    assert arr[1] == pytest.approx(35 / NORMALIZE)


@pytest.mark.parametrize("attr", ["pending_card", "history_count", "player_id"])
def test_observation_does_not_expose_removed_attributes(board, attr):
    """削除済みの属性が復活していないことを検証します。

    観測のレイアウトは学習側と暗黙に結合しているため、消したはずのフィールドが
    戻ると気付きにくいバグになります。
    """
    g = board(p0=Side(hp=40), p1=Side(hp=40))
    obs = godfield_core.get_observation(g.state, 0)

    assert not hasattr(obs, attr)


def test_fog_hides_the_opponent_status_from_the_cursed_player(board):
    """霧にかかったプレイヤーからは相手のHP・MP・お金が見えなくなることを検証します。

    霧を持たない側からは通常どおり見えることも併せて確認します（片側だけ隠れる）。
    """
    g = board(
        p0=Side(hp=40, mp=10, money=20, curses=[CurseType.CURSE_FOG]),
        p1=Side(hp=35, mp=15, money=25),
    )

    fogged = godfield_core.get_observation(g.state, 0)
    assert fogged.hp_me == pytest.approx(40 / NORMALIZE)
    assert fogged.hp_opp == pytest.approx(0.0)
    assert fogged.mp_opp == pytest.approx(0.0)
    assert fogged.money_opp == pytest.approx(0.0)

    clear = godfield_core.get_observation(g.state, 1)
    assert clear.hp_me == pytest.approx(35 / NORMALIZE)
    assert clear.hp_opp == pytest.approx(40 / NORMALIZE)


def test_phase_one_hot_matches_the_game_phase_enum(board):
    """フェイズ one-hot の長さと立つ位置が GamePhase enum と一致することを検証します。

    従来は長さ18とインデックス7が直書きされており、フェイズを追加すると黙って
    別の位置を検証してしまう状態でした。
    """
    g = board(p0=Side(hp=40, hand=["armor/wood-shield"]), p1=Side(hp=40))
    g.state.current_phase = GamePhase.PHASE_DEFENSE
    g.state.attacker_id = 1
    g.state.defender_id = 0

    phases = godfield_core.get_observation(g.state, 0).get_phase_one_hot()

    num_phases = len(GamePhase.__members__)
    assert len(phases) == num_phases
    assert phases[int(GamePhase.PHASE_DEFENSE)] == pytest.approx(1.0)
    assert sum(phases) == pytest.approx(1.0), "one-hot なので合計は1でなければならない"


def test_incoming_damage_and_staged_defense_are_reported(board):
    """飛んできている攻撃力と、仮置き中の防御力が観測へ載ることを検証します。"""
    armor = "armor/wood-shield"
    incoming = 30
    g = board(p0=Side(hp=40, hand=[armor]), p1=Side(hp=40))
    g.state.current_phase = GamePhase.PHASE_DEFENSE
    g.state.attacker_id = 1
    g.state.defender_id = 0
    g.state.pending_attack_power = incoming

    before = godfield_core.get_observation(g.state, 0)
    assert before.incoming_damage == pytest.approx(incoming / NORMALIZE)
    assert before.current_staged_defense == pytest.approx(0.0)

    # 木の盾を仮置きする
    g.state.set_staged_card(0, 0, 0)
    g.state.set_num_staged_cards(0, 1)

    after = godfield_core.get_observation(g.state, 0)
    assert after.incoming_damage == pytest.approx(incoming / NORMALIZE)
    assert after.current_staged_defense == pytest.approx(
        card_feature(armor, "defense_power") / NORMALIZE
    )


# ============================================================================
# 守護神が仕掛けた取引（仮置き列に手札スロットではない番兵が入る局面）
# ============================================================================


def test_a_guardian_deal_does_not_leak_out_of_bounds_memory_into_the_observation(board):
    """地球神の「売る」の最中に、観測が範囲外を読んで実在しないカードを載せないことを検証します。

    地球神は「売る」カード自体を手札に持たないため、仮置き列には手札スロットではない
    番兵 -1 が入ります。make_observation はこれを無検査で添字にしていたため、
    true_hand[1][-1] が true_hand[0][17]（相手自身の手札スロット17）を読み、
    「相手が場に出しているカード」として観測に載っていました。

    スロット17 に目印のカードを置き、それが相手の仮置きとして現れないことを確認します。
    観測は毎ステップ作られるので、この読み出しは取引が解決するまで毎回走っていました。
    """
    marker = "armor/god-shield"   # 目印。祈るを合法に保つため防具を使う
    filler = "armor/wood-shield"
    offer_slot = 5
    earth = int(godfield_core.GuardianType.EARTH)

    g = board(
        p0=Side(hp=99, money=50, hand=[filler] + [None] * 16 + [marker]),
        p1=Side(hp=40, money=50, guardian=earth, hand=[None] * offer_slot + [filler]),
    )
    g.rng.guardian_act(acts=True)
    g.rng.next_draws(filler, "deals/sell", then=filler)

    g.pray()

    g.expect(phase=GamePhase.PHASE_SELL_SELECT_MIRROR, actor=0)
    assert g.state.get_staged_card(1, 0) == -1, (
        "守護神の「売る」は手札に無いので、仮置きの手札スロットは -1 になる前提"
    )
    assert g.state.get_staged_card_id(1, 0) == card_id("deals/sell"), (
        "手札スロットは無くても、仮想カードとしてカードIDは解決できる前提"
    )
    assert g.state.get_true_hand(0, 17) == card_id(marker), "目印が置かれている前提"

    obs = godfield_core.get_observation(g.state, 0)
    opponent_staged = [int(c) for c in obs.get_opponent_staged_cards()]

    assert card_id(marker) not in opponent_staged, (
        f"自分の手札が相手の仮置きとして観測に漏れています: {opponent_staged}"
    )
    # 守護神の「売る」も場に出ているカードとして観測できる。
    # 番兵方式だったころは、ここが範囲外の値になるため飛ばすしかなかった。
    assert opponent_staged[0] == card_id("deals/sell")
    assert opponent_staged[1] == card_id(filler), "出品されているカード"
    assert all(c == godfield_core.CARD_EMPTY for c in opponent_staged[2:])

    # 同じ経路を使う観測ヘルパーも同じ結果になること
    helper = list(godfield_core.get_opponent_staged_cards_for_obs(g.state, 0))
    assert helper == [card_id("deals/sell"), card_id(filler)]
