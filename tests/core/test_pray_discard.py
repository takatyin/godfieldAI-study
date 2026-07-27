"""「祈る」と「捨てる」の検証。

【移行メモ】
フェイズを手で代入して合法手を読むだけの構成だったため、「その局面が実際に
発生しうるか」は検証されていませんでした。また補充ドローを制御していなかったので、
引いたカードについては「空でないこと」しか確認できていませんでした。
"""

import pytest

import godfield_core
from godfield_core import ActionType, GamePhase
from tests.core.dsl import Side, card_feature, card_id

FILLER = "armor/wood-shield"

ARMOR = "armor/leather-clothes"    # 防具：メインでは出せないが捨てられる
WEAPON = "weapons/punch"           # 武器：メインで出せるが捨てられない
AMULET = "sundries/sun-amulet"     # 使用タイミングを持たないパッシブ雑貨
THUNDER = "miracles/thunder"


def test_praying_draws_a_card_and_passes_the_turn(board):
    """「祈る」で山札から1枚引き、手番が相手に移ることを検証します。"""
    drawn = "armor/leather-cap"
    g = board(p0=Side(hp=40, mp=10, hand=[]), p1=Side(hp=40, mp=10))
    g.rng.deck_always(drawn)

    assert g.hand(0) == [], "手札が空の状態から始める前提のテスト"

    g.pray()

    g.expect(actor=1)
    assert g.state.get_true_hand(0, 0) == card_id(drawn), "空きスロットに引いたカードが入る"
    assert g.state.get_is_used(0, 0) is False, "引いたばかりのカードは未使用"


def test_only_directly_playable_cards_are_selectable_in_the_main_phase(board):
    """メインフェイズでは、そこで使えるカードだけが選択できることを検証します。"""
    g = board(
        p0=Side(hp=40, mp=10, hand=[ARMOR, WEAPON, AMULET]),
        p1=Side(hp=40, mp=10),
    )
    g.rng.deck_always(FILLER)

    g.expect_legal([WEAPON])           # 武器は攻撃に使える
    g.expect_illegal([ARMOR, AMULET])  # 防具・パッシブ雑貨はメインでは出せない
    g.expect_actions(discard=True)


def test_the_discard_phase_offers_exactly_the_cards_the_main_phase_could_not_use(board):
    """捨てるフェイズでは、メインで使えなかったカードだけが捨てられることを検証します。

    「メインで使えない」と「捨てられる」がちょうど裏返しの関係になっているという
    規則そのものが主題です。
    """
    g = board(
        p0=Side(hp=40, mp=10, hand=[ARMOR, WEAPON, AMULET]),
        p1=Side(hp=40, mp=10),
    )
    g.rng.deck_always(FILLER)

    g.step(ActionType.ACTION_DISCARD)
    g.expect(phase=GamePhase.PHASE_DISCARD)

    g.expect_legal([ARMOR])
    g.expect_illegal([WEAPON, AMULET])

    # 何も選んでいないうちは確定できない
    g.expect_actions(confirm=False)


def test_discarding_empties_the_slot_without_marking_it_used(board):
    """捨てたスロットが空になり、使用済みフラグは立たない（補充されない）ことを検証します。"""
    g = board(
        p0=Side(hp=40, mp=10, hand=[ARMOR, WEAPON]),
        p1=Side(hp=40, mp=10),
    )
    g.rng.deck_always(FILLER)

    g.step(ActionType.ACTION_DISCARD)
    g.select(ARMOR)
    g.expect_actions(confirm=True)

    g.confirm()

    assert g.state.get_true_hand(0, 0) == godfield_core.CARD_EMPTY
    assert g.state.get_is_used(0, 0) is False, (
        "使用済みにすると次のターン終了時に補充されてしまう"
    )


def test_a_deployed_miracle_can_be_discarded_and_leaves_the_field(board):
    """展開済みの奇跡しか無くても「捨てる」が選べ、捨てると場からも消えることを検証します。

    展開済みの奇跡は手札スロットを占有し続けるため、これが捨てられないと
    「使えるカードも捨てられるカードも無い」局面で手が詰まります。
    """
    g = board(
        p0=Side(hp=40, mp=20, hand=[THUNDER], deployed=[0]),
        p1=Side(hp=40, mp=20),
    )
    g.rng.deck_always(FILLER)

    assert g.state.get_is_deployed(0, 0) is True, "展開済みの状態を作れていない"
    g.expect_actions(discard=True)

    g.step(ActionType.ACTION_DISCARD)
    g.expect(phase=GamePhase.PHASE_DISCARD)
    g.expect_legal([THUNDER])

    g.select(THUNDER)
    g.confirm()

    assert g.state.get_true_hand(0, 0) == godfield_core.CARD_EMPTY
    assert g.state.get_is_deployed(0, 0) is False, "場からも消えるべきです"


@pytest.mark.parametrize(
    ("card", "playable_in_main"),
    [
        (WEAPON, True),
        (ARMOR, False),
        (AMULET, False),
    ],
    ids=["武器", "防具", "パッシブ雑貨"],
)
def test_the_main_phase_rule_matches_the_cards_usage_timing(board, card, playable_in_main):
    """メインで出せるかどうかが、カードマスタの使用タイミングと一致することを検証します。

    上のテストが前提にしている「どのカードがどちら側か」を、マスタから
    直接確かめておくためのテストです。前提が崩れたときに、上のテストが
    黙って別のことを検証し始めるのを防ぎます。
    """
    timing = card_feature(card, "usage_timing", []) or []
    main_timings = {"main_atk_phase", "main_miracle_phase", "main_sundry_phase", "main_deal_phase"}
    assert bool(main_timings & set(timing)) is playable_in_main
