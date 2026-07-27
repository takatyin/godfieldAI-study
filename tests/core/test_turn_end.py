"""ターン終了処理（死亡判定・昇天弓・病気・守護神の行動・守護神の離脱）の検証。

【移行メモ】
このファイルは 500〜1000 回のシード総当たり探索を14箇所抱えていた。さらに
確率そのものを検証したいテストは「200回試して10〜40回なら合格」のような
統計的アサーションになっており、
  - 失敗しても原因が確率の偏りなのか実装バグなのか区別できない
  - 境界（0回・全回）を踏まないので分岐の抜けを検出できない
  - たまたま範囲に入って通ってしまう
という問題があった。

現在は RollKind で判定結果を直接指示するため、成功・失敗の両分岐を決定的に
検証できる。さらに「その判定が何回行われたか」を rng.consumed() で見られるので、
「暗雲下では命中判定そのものが行われない」のように *乱数を消費しないこと* まで
検証できる（統計テストでは原理的に書けなかった）。
"""

import pytest

import godfield_core
from godfield_core import (
    ActionType,
    CurseType,
    Element,
    EventType,
    GamePhase,
    GuardianType,
    RollKind,
    SicknessType,
)
from tests.core.dsl import Game, Side, card_feature, card_id, element_of, ev

# ターン終了を起こすために捨てる無害な防具。
DISCARD_CARD = "armor/leather-clothes"
# 手札補充で盤面が動かないようにするための無害なカード。
FILLER = "armor/wood-shield"

MARS = int(GuardianType.MARS)
JUPITER = int(GuardianType.JUPITER)
URANUS = int(GuardianType.URANUS)
PLUTO = int(GuardianType.PLUTO)
NEPTUNE = int(GuardianType.NEPTUNE)
VENUS = int(GuardianType.VENUS)

# 昇天弓の死亡時反撃は、カードマスタの攻撃力ではなくエンジン側の固定値で撃たれる。
BOW_POWER = 30


# ============================================================================
# 死亡時処理: 太陽のお守り・昇天弓・同時死亡
# ============================================================================


def test_sun_amulet_revives_at_hp10_and_is_consumed(board):
    """太陽のお守りが死亡時に自動消費され、HP10で復活することを検証します。"""
    g = board(
        p0=Side(hp=0, hand=["sundries/sun-amulet", DISCARD_CARD]),
        p1=Side(hp=40),
    )
    g.rng.deck_always(FILLER)
    g.discard(DISCARD_CARD)

    g.expect(p0_hp=10, phase=GamePhase.PHASE_MAIN, actor=1, is_done=False)
    # お守りは消費され、そのスロットには補充カードが入る
    assert g.state.get_true_hand(0, 0) == card_id(FILLER)
    assert card_id("sundries/sun-amulet") not in [
        g.state.get_true_hand(0, i) for i in range(18)
    ]


def test_ascension_bow_hit_opens_defense_then_owner_still_loses(board):
    """昇天弓が命中した場合、相手の防御フェイズを経てから撃った本人の敗北が確定します。"""
    g = board(
        p0=Side(hp=0, hand=["weapons/ascension-bow", DISCARD_CARD]),
        p1=Side(hp=40),
    )
    g.rng.deck_always(FILLER)
    g.rng.ascension_bow(True)
    g.discard(DISCARD_CARD)

    g.expect(
        phase=GamePhase.PHASE_DEFENSE,
        actor=1,
        attacker=0,
        defender=1,
        pending_power=BOW_POWER,
        pending_element=Element.ELEM_LIGHT,
    )

    g.confirm()  # 相手が被弾
    g.expect(is_done=True, p0_reward=-1.0, p1_reward=1.0)


def test_ascension_bow_miss_ends_the_game_without_a_defense_phase(board):
    """昇天弓が外れた場合、防御フェイズを起動せずそのまま敗北が確定することを検証します。

    従来は「命中するシード」しか使っておらず、外れ側は一度も検証されていなかった。
    """
    g = board(
        p0=Side(hp=0, hand=["weapons/ascension-bow", DISCARD_CARD]),
        p1=Side(hp=40),
    )
    g.rng.deck_always(FILLER)
    g.rng.ascension_bow(False)
    g.discard(DISCARD_CARD)

    g.expect(is_done=True, p0_reward=-1.0, p1_reward=1.0, p1_hp=40)
    g.expect_events(ev(EventType.ATTACK_MISS, card="weapons/ascension-bow"))


def test_ascension_bow_second_shot_fires_after_the_first_misses(board):
    """昇天弓を2枚持つ場合、1発目が外れても2発目が自動的に処理されることを検証します。"""
    g = board(
        p0=Side(hp=0, hand=["weapons/ascension-bow", "weapons/ascension-bow", DISCARD_CARD]),
        p1=Side(hp=40),
    )
    g.rng.deck_always(FILLER)
    g.rng.ascension_bow(False, True)  # 1発目ミス、2発目命中
    g.discard(DISCARD_CARD)

    g.expect(
        phase=GamePhase.PHASE_DEFENSE,
        actor=1,
        attacker=0,
        defender=1,
        pending_power=BOW_POWER,
        pending_element=Element.ELEM_LIGHT,
        p0_bows=0,
    )
    assert g.rng.consumed(RollKind.ASCENSION_BOW_HIT) == 2


def test_simultaneous_death_is_a_draw(board):
    """両者が同時にHP0になった場合、引き分けで終了することを検証します。"""
    g = board(p0=Side(hp=0, hand=[DISCARD_CARD]), p1=Side(hp=0))
    g.discard(DISCARD_CARD)
    g.expect(is_done=True, p0_reward=0.0, p1_reward=0.0)


def test_simultaneous_death_skips_the_ascension_bow(board):
    """同時死亡でどちらもお守りを持たない場合、昇天弓を持っていても反撃せず即引き分けになります。"""
    g = board(
        p0=Side(hp=0, hand=[DISCARD_CARD, "weapons/ascension-bow"]),
        p1=Side(hp=0, hand=[DISCARD_CARD]),
    )
    g.discard(DISCARD_CARD)

    g.expect(is_done=True, phase=GamePhase.PHASE_END, p0_reward=0.0, p1_reward=0.0)
    assert g.rng.consumed(RollKind.ASCENSION_BOW_HIT) == 0, (
        "同時死亡は昇天弓の判定より先に解決されるべきです"
    )


def test_normal_attack_kill_then_amulet_revive(board):
    """通常攻撃で相手が死亡し、お守りでHP10復活することを検証します。"""
    punch_power = card_feature("weapons/punch", "attack_power")
    g = board(
        p0=Side(hp=40, hand=["weapons/punch"]),
        p1=Side(hp=punch_power - 1, hand=["sundries/sun-amulet", DISCARD_CARD]),
    )
    g.rng.deck_always(FILLER)
    g.attack("weapons/punch")
    g.expect(phase=GamePhase.PHASE_DEFENSE, actor=1)
    g.take_hit()

    g.expect(p1_hp=10, phase=GamePhase.PHASE_MAIN, actor=1, is_done=False)


def test_kill_opponent_then_bow_counter_then_own_amulet_revive_wins(board):
    """相手を倒し、相手の昇天弓を被弾して死亡し、お守りで復活して勝利することを検証します。

    復活した時点で相手は既に死亡しているため、相手の守護神行動は発生しません。
    """
    g = board(
        p0=Side(hp=20, hand=["weapons/punch", "sundries/sun-amulet"]),
        p1=Side(hp=3, guardian=MARS, hand=["weapons/ascension-bow", DISCARD_CARD]),
    )
    g.rng.deck_always(FILLER)
    g.rng.ascension_bow(True)
    g.rng.guardian_leave(leaves=False)

    g.attack("weapons/punch")
    g.take_hit()  # P1 が死亡し、昇天弓が起動

    g.expect(phase=GamePhase.PHASE_DEFENSE, actor=0, attacker=1, defender=0)
    g.take_hit()  # P0 が 30 被弾 -> HP0 -> お守りで復活

    g.expect(p0_hp=10, p1_hp=0, is_done=True, p0_reward=1.0, p1_reward=-1.0)
    assert g.rng.consumed(RollKind.GUARDIAN_ACT) == 0, (
        "死亡した相手の守護神は行動しないべきです"
    )


def test_kill_opponent_then_bow_counter_kills_us_is_a_draw(board):
    """相手を倒したが昇天弓で自分も死亡し、引き分けになることを検証します。"""
    g = board(
        p0=Side(hp=15, hand=["weapons/punch"]),
        p1=Side(hp=3, hand=["weapons/ascension-bow", DISCARD_CARD]),
    )
    g.rng.deck_always(FILLER)
    g.rng.ascension_bow(True)

    g.attack("weapons/punch")
    g.take_hit()
    g.expect(phase=GamePhase.PHASE_DEFENSE, actor=0)
    g.take_hit()

    g.expect(p0_hp=0, p1_hp=0, is_done=True, p0_reward=0.0, p1_reward=0.0)


def test_bow_counter_survived_but_sickness_damage_kills_is_a_draw(board):
    """昇天弓をHP1で耐えた後、風邪の1ダメージで死亡し引き分けになることを検証します。"""
    g = board(
        p0=Side(hp=BOW_POWER + 1, sickness=SicknessType.SICKNESS_COLD, hand=["weapons/punch"]),
        p1=Side(hp=3, hand=["weapons/ascension-bow", DISCARD_CARD]),
    )
    g.rng.deck_always(FILLER)
    g.rng.ascension_bow(True)
    g.rng.sickness_worsen(False)  # 悪化ではなく通常の風邪ダメージで死ぬ経路を固定する

    g.attack("weapons/punch")
    g.take_hit()
    g.expect(phase=GamePhase.PHASE_DEFENSE, actor=0)
    g.take_hit()

    g.expect(p0_hp=0, p1_hp=0, is_done=True, p0_reward=0.0, p1_reward=0.0)


# ============================================================================
# 病気: 悪化判定・ダメージ・回復
# ============================================================================


@pytest.mark.parametrize(
    ("before", "after"),
    [
        (SicknessType.SICKNESS_COLD, SicknessType.SICKNESS_FEVER),
        (SicknessType.SICKNESS_FEVER, SicknessType.SICKNESS_HELL),
        (SicknessType.SICKNESS_HELL, SicknessType.SICKNESS_HEAVEN),
    ],
    ids=["風邪->熱病", "熱病->地獄病", "地獄病->天国病"],
)
def test_sickness_worsens_one_stage(board, before, after):
    """病気の悪化（5%）が1段階ずつ進むことを、全段階について検証します。

    従来は地獄病→天国病だけを500シード探索で検証しており、
    風邪→熱病・熱病→地獄病は一度も検証されていなかった。
    """
    g = board(p0=Side(hp=40, sickness=before, hand=[DISCARD_CARD]))
    g.rng.deck_always(FILLER)
    g.rng.sickness_worsen(True)
    g.discard(DISCARD_CARD)

    g.expect(p0_sickness=after)


def test_sickness_does_not_worsen_when_the_roll_fails(board):
    """悪化判定が失敗した場合、病気が進行しないことを検証します。"""
    g = board(p0=Side(hp=40, sickness=SicknessType.SICKNESS_COLD, hand=[DISCARD_CARD]))
    g.rng.deck_always(FILLER)
    g.rng.sickness_worsen(False)
    g.discard(DISCARD_CARD)

    g.expect(p0_sickness=SicknessType.SICKNESS_COLD, p0_hp=39)  # 風邪の1ダメージのみ


def test_heaven_sickness_worsening_is_instant_death(board):
    """天国病の悪化は発作による即死であることを検証します。"""
    g = board(p0=Side(hp=40, sickness=SicknessType.SICKNESS_HEAVEN, hand=[DISCARD_CARD]))
    g.rng.sickness_worsen(True)
    g.discard(DISCARD_CARD)

    g.expect(p0_hp=0, is_done=True)
    g.expect_events(
        ev(
            EventType.EFFECT_SICKNESS,
            value=float(
                godfield_core.SicknessEvent.TYPE_HEAVEN
                | godfield_core.SicknessEvent.FLAG_SEIZURE
            ),
        )
    )


def test_heaven_seizure_death_revived_by_amulet_skips_the_heal(board):
    """発作死→お守り復活では、天国病のターン終了時回復(+5)がスキップされHP10になることを検証します。"""
    g = board(
        p0=Side(
            hp=40,
            sickness=SicknessType.SICKNESS_HEAVEN,
            hand=["sundries/sun-amulet", DISCARD_CARD],
        ),
    )
    g.rng.deck_always(FILLER)
    g.rng.sickness_worsen(True)
    g.discard(DISCARD_CARD)

    g.expect(p0_hp=10, p0_sickness=SicknessType.SICKNESS_HEAVEN, is_done=False)


@pytest.mark.parametrize(
    ("sickness", "hp_before", "hp_after"),
    [
        (SicknessType.SICKNESS_COLD, 10, 9),      # 風邪: 1ダメージ
        (SicknessType.SICKNESS_HELL, 10, 5),      # 地獄病: 5ダメージ
        (SicknessType.SICKNESS_HEAVEN, 50, 55),   # 天国病: 5回復
        (SicknessType.SICKNESS_HEAVEN, 97, 99),   # 天国病: 上限99でクランプ
    ],
    ids=["風邪1ダメージ", "地獄病5ダメージ", "天国病5回復", "天国病99クランプ"],
)
def test_sickness_damage_and_healing_at_turn_end(board, sickness, hp_before, hp_after):
    """各病気のターン終了時ダメージ・回復量を検証します。"""
    g = board(p0=Side(hp=hp_before, sickness=sickness, hand=[DISCARD_CARD]))
    g.rng.deck_always(FILLER)
    g.rng.sickness_worsen(False)
    g.discard(DISCARD_CARD)

    g.expect(p0_hp=hp_after)


def test_sickness_only_applies_to_the_turn_player(board):
    """病気のダメージ・悪化判定が手番プレイヤーにのみ適用されることを検証します。"""
    g = board(
        p0=Side(hp=40, hand=[DISCARD_CARD]),
        p1=Side(hp=40, sickness=SicknessType.SICKNESS_HELL),  # 待機側が地獄病
    )
    g.rng.deck_always(FILLER)
    g.discard(DISCARD_CARD)

    g.expect(p0_hp=40, p1_hp=40)
    assert g.rng.consumed(RollKind.SICKNESS_WORSEN) == 0, (
        "待機側の病気では悪化判定すら行われないべきです"
    )


def test_sickness_applies_to_the_attacker_after_combat(board):
    """戦闘解決後のターン終了でも、病気ダメージは攻撃側（手番プレイヤー）に入ることを検証します。"""
    g = board(
        p0=Side(hp=40, sickness=SicknessType.SICKNESS_COLD, hand=["weapons/bronze-club"]),
        p1=Side(hp=40, hand=["armor/leather-cap"]),
    )
    g.rng.deck_always(FILLER)
    g.rng.sickness_worsen(False)

    g.attack("weapons/bronze-club")
    g.defend("armor/leather-cap")

    g.expect(phase=GamePhase.PHASE_MAIN, actor=1, p0_hp=39, p1_hp=40)


def test_heaven_wind_mutual_seizure_is_a_draw(board):
    """互いに天国病の状態で＜天国風＞→昇天弓→自分の発作死、という連鎖が引き分けになることを検証します。

    従来は「昇天弓が命中し、かつ自分の天国病が悪化死する」という2つの確率が同時に
    成立するシードを1000回探索していた。
    """
    g = board(
        p0=Side(
            hp=BOW_POWER + 1, mp=20,
            sickness=SicknessType.SICKNESS_HEAVEN,
            hand=["miracles/heaven-wind"],
        ),
        p1=Side(
            hp=40,
            sickness=SicknessType.SICKNESS_HEAVEN,
            hand=["weapons/ascension-bow", DISCARD_CARD],
        ),
    )
    g.rng.deck_always(FILLER)
    g.rng.ascension_bow(True)
    g.rng.sickness_worsen(True)  # P0 のターン終了時に発作を起こさせる

    g.attack("miracles/heaven-wind")
    g.expect(phase=GamePhase.PHASE_MIRACLE_DEFENSE, actor=1)
    g.take_hit()  # 天国病の重ねがけで P1 が発作即死

    g.expect(p1_hp=0, phase=GamePhase.PHASE_DEFENSE, actor=0)
    g.take_hit()  # 昇天弓で P0 は HP1 になり、ターン終了の発作で死亡

    g.expect(p0_hp=0, p1_hp=0, is_done=True, p0_reward=0.0, p1_reward=0.0)


def test_heaven_wind_on_self_seizure_revive_then_heals(board):
    """自分に＜天国風＞を撃って発作死→お守り復活した場合、ターン終了の+5回復が適用されHP15になることを検証します。

    メインフェイズ中の発作なので、ターン終了時の悪化は起きていない扱いになります。
    """
    g = board(
        p0=Side(
            hp=40, mp=20,
            sickness=SicknessType.SICKNESS_HEAVEN,
            hand=["miracles/heaven-wind", "sundries/sun-amulet", DISCARD_CARD],
        ),
    )
    g.rng.deck_always(FILLER)
    g.rng.sickness_worsen(False)  # ターン終了時の悪化は起こさない

    g.attack("miracles/heaven-wind", to_self=True)

    g.expect(
        p0_hp=15,
        p0_sickness=SicknessType.SICKNESS_HEAVEN,
        is_done=False,
        actor=1,
        phase=GamePhase.PHASE_MAIN,
    )


# ============================================================================
# 守護神の行動
# ============================================================================


def end_turn_with_guardian(
    board,
    guardian: int,
    action_card: str,
    *,
    p0: Side | None = None,
    p1: Side | None = None,
    hits: bool | None = None,
) -> Game:
    """P1 に守護神を憑依させ、P0 がターンを終え、指定した行動が発動した局面を作ります。

    `hits` は命中率100%未満の行動（火星神など）を必中／必ず外すに固定します。
    命中判定はターン終了の解決中に行われるため、必ずここで先に指示すること。
    """
    g = board(
        p0=p0 if p0 is not None else Side(hp=40, hand=[DISCARD_CARD]),
        p1=p1 if p1 is not None else Side(hp=40, guardian=guardian),
    )
    g.rng.deck_always(FILLER)
    g.rng.guardian_action_card(guardian, action_card)
    if hits is not None:
        g.rng.hits(always=hits)
    g.discard(DISCARD_CARD)
    return g


@pytest.mark.parametrize(
    "action_card",
    [
        "gurdians/fire-shout",
        "gurdians/fire-roar",
        "gurdians/fire-buzz",
        "gurdians/fire-tweet",
        "gurdians/fire-whisper",
    ],
)
def test_mars_guardian_attacks_with_each_of_its_five_actions(board, action_card):
    """火星神の5行動すべてが、そのカードの威力・属性で攻撃を組むことを検証します。

    従来は500シード探索で「たまたま選ばれた1つ」しか検証していなかった。
    """
    g = end_turn_with_guardian(board, MARS, action_card, hits=True)

    g.expect(
        phase=GamePhase.PHASE_DEFENSE,
        actor=0,
        attacker=1,
        defender=0,
        pending_power=card_feature(action_card, "attack_power"),
        pending_element=element_of(action_card),
    )
    assert g.state.pending_attack_source_id == card_id(action_card)


def test_guardian_attack_can_miss(board):
    """命中率75%の守護神攻撃が外れた場合、防御フェイズを起動せずターンが進むことを検証します。"""
    g = board(p0=Side(hp=40, hand=[DISCARD_CARD]), p1=Side(hp=40, guardian=MARS))
    g.rng.deck_always(FILLER)
    g.rng.guardian_action_card(MARS, "gurdians/fire-shout")
    g.rng.hits(always=False)
    g.discard(DISCARD_CARD)

    g.expect(phase=GamePhase.PHASE_MAIN, actor=1, p0_hp=40)
    g.expect_events(ev(EventType.ATTACK_MISS, card="gurdians/fire-shout"))


def test_guardian_attack_kills_the_turn_player(board):
    """守護神の攻撃で手番プレイヤーが死亡し、敗北が確定することを検証します。"""
    weakest = "gurdians/fire-whisper"
    power = card_feature(weakest, "attack_power")
    g = board(
        p0=Side(hp=power, hand=[DISCARD_CARD]),
        p1=Side(hp=40, guardian=MARS),
    )
    g.rng.deck_always(FILLER)
    g.rng.guardian_action_card(MARS, weakest)
    g.rng.hits(always=True)
    # P0 は守護神を持たないので離脱判定は行われない（指示すると空振りになる）
    g.discard(DISCARD_CARD)

    g.expect(phase=GamePhase.PHASE_DEFENSE, actor=0)
    g.take_hit()

    g.expect(p0_hp=0, is_done=True, p0_reward=-1.0, p1_reward=1.0)


def test_venus_fine_drains_money_from_the_turn_player(board):
    """金星神の罰金が、手番プレイヤーからお金3を没収して持ち主に加算することを検証します。"""
    g = end_turn_with_guardian(
        board, VENUS, "gurdians/fine",
        p0=Side(hp=40, money=10, hand=[DISCARD_CARD]),
        p1=Side(hp=40, money=10, guardian=VENUS),
    )

    g.expect(phase=GamePhase.PHASE_SUNDRY_SELECT_MIRROR)
    g.take_hit()
    g.expect(p0_money=7, p1_money=13)


def test_venus_bribe_gives_money_to_the_turn_player(board):
    """金星神のわいろが、手番プレイヤーにお金+5を与えることを検証します（従来未検証）。"""
    g = end_turn_with_guardian(
        board, VENUS, "gurdians/bribe",
        p0=Side(hp=40, money=10, hand=[DISCARD_CARD]),
        p1=Side(hp=40, money=10, guardian=VENUS),
    )

    g.expect(phase=GamePhase.PHASE_SUNDRY_SELECT_MIRROR)
    g.take_hit()
    g.expect(p0_money=15)


@pytest.mark.parametrize(
    ("action_card", "expected_money"),
    [
        ("gurdians/luxury-accessory", 30),  # 持ち主にお金+20
        ("gurdians/little-something", 18),  # 持ち主にお金+8
    ],
    ids=["豪華なアクセサリー+20", "つまらない物+8"],
)
def test_venus_self_buffs_target_the_owner(board, action_card, expected_money):
    """金星神の自己バフが持ち主のお金のみを増やすことを検証します。

    従来は `money in (18, 30)` という曖昧なアサーションで、どちらの行動が
    発動したのか区別できていなかった。
    """
    g = end_turn_with_guardian(
        board, VENUS, action_card,
        p0=Side(hp=40, money=10, hand=[DISCARD_CARD]),
        p1=Side(hp=40, money=10, guardian=VENUS),
    )

    g.expect(p0_money=10, p1_money=expected_money)


def test_venus_coin_scattering_gives_money_to_both(board):
    """金星神の小銭ばらまきが両者にお金+1することを検証します（従来未検証）。"""
    g = end_turn_with_guardian(
        board, VENUS, "gurdians/coin-scattering",
        p0=Side(hp=40, money=10, hand=[DISCARD_CARD]),
        p1=Side(hp=40, money=10, guardian=VENUS),
    )

    g.expect(p0_money=11, p1_money=11)


def test_venus_fine_kills_turn_player_and_bow_counter_resolves(board):
    """金星神の罰金で手番プレイヤーが死亡し、昇天弓反撃を経て決着することを検証します。"""
    g = board(
        p0=Side(hp=2, money=0, hand=[DISCARD_CARD, "weapons/ascension-bow"]),
        p1=Side(hp=40, guardian=VENUS),
    )
    g.rng.deck_always(FILLER)
    g.rng.guardian_action_card(VENUS, "gurdians/fine")
    g.rng.ascension_bow(True)
    g.rng.guardian_leave(leaves=False)
    g.discard(DISCARD_CARD)

    g.expect(phase=GamePhase.PHASE_SUNDRY_SELECT_MIRROR, actor=0)
    g.take_hit()  # お金0なので没収3が直接HPに入りP0が死亡 -> 昇天弓起動

    g.expect(phase=GamePhase.PHASE_DEFENSE, actor=1, p0_hp=0)
    g.take_hit()

    g.expect(is_done=True, p0_reward=-1.0, p1_reward=1.0)


@pytest.mark.parametrize(
    ("action_card", "expect"),
    [
        ("gurdians/healthy-seafood-soup", {"p1_hp": 30}),   # HP+10
        ("gurdians/seafood-soup", {"p1_hp": 25}),           # HP+5
        ("gurdians/fresh-beach-aroma", {"p1_mp": 20}),      # MP+10
        ("gurdians/beach-aroma", {"p1_mp": 15}),            # MP+5
        ("gurdians/sound-of-ripples", {"p1_sickness": SicknessType.SICKNESS_NONE}),
    ],
    ids=["HP+10", "HP+5", "MP+10", "MP+5", "状態異常全解除"],
)
def test_neptune_guardian_supports_its_owner(board, action_card, expect):
    """海王神の5行動すべてが持ち主自身への支援効果であることを個別に検証します。

    従来は「HPまたはMPが増えた」という曖昧な OR 条件で、どの行動かも量も
    検証していなかった。
    """
    g = end_turn_with_guardian(
        board, NEPTUNE, action_card,
        p0=Side(hp=40, hand=[DISCARD_CARD]),
        p1=Side(hp=20, mp=10, guardian=NEPTUNE, sickness=SicknessType.SICKNESS_COLD),
    )

    g.expect(**expect)


@pytest.mark.parametrize(
    ("guardian", "action_card", "curse"),
    [
        (JUPITER, "gurdians/colored-leaves", CurseType.CURSE_DREAM),
        (URANUS, "gurdians/halo", CurseType.CURSE_FLASH),
        (PLUTO, "gurdians/ominous-premonition", CurseType.CURSE_DARK_CLOUD),
    ],
    ids=["木星神の紅葉->夢", "天王神の後光->閃光", "冥王神の不吉な予感->暗雲"],
)
def test_zero_power_guardian_curses_can_be_reflected(board, guardian, action_card, curse):
    """攻撃力0の状態異常付与（雑貨扱い）がスーパーミラーで反射できることを検証します。"""
    g = board(
        p0=Side(hp=40, mp=40, hand=["armor/super-mirror", DISCARD_CARD]),
        p1=Side(hp=40, mp=40, guardian=guardian),
    )
    g.rng.deck_always(FILLER)
    g.rng.guardian_action_card(guardian, action_card)
    # 攻撃力0の状態異常付与なのでダメージが発生せず、離脱判定も行われない
    g.discard(DISCARD_CARD)

    g.expect(phase=GamePhase.PHASE_SUNDRY_SELECT_MIRROR, actor=0)
    g.select("armor/super-mirror")
    # 反射されて元の攻撃者（守護神の持ち主）側の選択に移る
    g.expect(phase=GamePhase.PHASE_SUNDRY_SELECT_MIRROR, actor=1)
    g.take_hit()

    g.expect(p0_curses=set(), p1_curses={curse})


@pytest.mark.parametrize(
    ("guardian", "action_card", "curse"),
    [
        (JUPITER, "gurdians/colored-leaves", CurseType.CURSE_DREAM),
        (URANUS, "gurdians/halo", CurseType.CURSE_FLASH),
        (PLUTO, "gurdians/ominous-premonition", CurseType.CURSE_DARK_CLOUD),
    ],
    ids=["木星神の紅葉->夢", "天王神の後光->閃光", "冥王神の不吉な予感->暗雲"],
)
def test_zero_power_guardian_curses_apply_when_not_reflected(board, guardian, action_card, curse):
    """反射しなかった場合は手番プレイヤーが状態異常になることを検証します（従来未検証）。"""
    g = board(
        p0=Side(hp=40, mp=40, hand=[DISCARD_CARD]),
        p1=Side(hp=40, mp=40, guardian=guardian),
    )
    g.rng.deck_always(FILLER)
    g.rng.guardian_action_card(guardian, action_card)
    # 攻撃力0の状態異常付与なのでダメージが発生せず、離脱判定も行われない
    g.discard(DISCARD_CARD)

    g.expect(phase=GamePhase.PHASE_SUNDRY_SELECT_MIRROR, actor=0)
    g.take_hit()

    g.expect(p0_curses={curse}, p1_curses=set())


@pytest.mark.parametrize("acts", [True, False], ids=["行動する", "行動しない"])
def test_guardian_action_roll_gates_the_whole_behaviour(board, acts):
    """守護神の行動判定（25%）が成立しなければ何も起きないことを検証します。"""
    g = board(p0=Side(hp=40, hand=[DISCARD_CARD]), p1=Side(hp=40, guardian=MARS))
    g.rng.deck_always(FILLER)
    if acts:
        # 行動する場合のみ、どの行動を選ぶかと命中判定が行われる
        g.rng.guardian_action_card(MARS, "gurdians/fire-shout")
        g.rng.hits(always=True)
    else:
        g.rng.guardian_act(acts=False)
    g.discard(DISCARD_CARD)

    if acts:
        g.expect(phase=GamePhase.PHASE_DEFENSE, attacker=1, defender=0)
    else:
        g.expect(phase=GamePhase.PHASE_MAIN, actor=1, p0_hp=40)
        # 行動しないと決まった時点で、行動選択も命中判定も行われない
        assert g.rng.consumed(RollKind.GUARDIAN_ACT_CHOICE) == 0
        assert g.rng.consumed(RollKind.ACCURACY) == 0


# ============================================================================
# 守護神の離脱条件
# ============================================================================


@pytest.mark.parametrize("leaves", [True, False], ids=["離脱する", "残留する"])
def test_guardian_leaves_on_combat_damage(board, leaves):
    """戦闘ダメージを受けたときの守護神離脱判定（10%）の両分岐を検証します。

    従来は200回試して「10〜40回なら合格」という統計的アサーションだったため、
    分岐そのものは検証できていなかった。
    """
    g = board(
        p0=Side(hp=40, hand=["weapons/bronze-club"]),
        p1=Side(hp=40, guardian=MARS),
    )
    g.rng.deck_always(FILLER)
    g.rng.guardian_leave(leaves=leaves)
    g.attack("weapons/bronze-club")
    g.take_hit()

    g.expect(p1_guardian=0 if leaves else MARS)
    assert g.rng.consumed(RollKind.GUARDIAN_LEAVE) >= 1


def test_guardian_does_not_roll_when_damage_is_fully_blocked(board):
    """ダメージ0のときは離脱判定そのものが行われないことを検証します。

    「離脱しなかった」ではなく「判定していない」ことを検証できるのは、
    乱数の消費回数を観測できるようになったため。
    """
    g = board(
        p0=Side(hp=40, hand=["weapons/bronze-club"]),
        p1=Side(hp=40, guardian=MARS, hand=["armor/iron-shield"]),
    )
    g.rng.deck_always(FILLER)
    g.attack("weapons/bronze-club")
    g.defend("armor/iron-shield")  # 防御力4 > 攻撃力1 なので無傷

    g.expect(p1_guardian=MARS, p1_hp=40)
    assert g.rng.consumed(RollKind.GUARDIAN_LEAVE) == 0


@pytest.mark.parametrize("leaves", [True, False], ids=["離脱する", "残留する"])
def test_guardian_leaves_on_sickness_damage(board, leaves):
    """病気ダメージでも守護神の離脱判定が行われることを検証します。"""
    g = board(
        p0=Side(hp=40, sickness=SicknessType.SICKNESS_COLD, guardian=MARS, hand=[]),
    )
    g.rng.deck_always(FILLER)
    g.rng.sickness_worsen(False)
    g.rng.guardian_leave(leaves=leaves)
    g.pray()

    g.expect(p0_guardian=0 if leaves else MARS, p0_hp=39)


def test_guardian_does_not_roll_on_heaven_sickness_healing(board):
    """天国病の回復（HP増加）では離脱判定が行われないことを検証します。"""
    g = board(
        p0=Side(hp=30, sickness=SicknessType.SICKNESS_HEAVEN, guardian=MARS, hand=[]),
    )
    g.rng.deck_always(FILLER)
    g.rng.sickness_worsen(False)
    g.pray()

    g.expect(p0_guardian=MARS, p0_hp=35)
    assert g.rng.consumed(RollKind.GUARDIAN_LEAVE) == 0


def test_guardian_does_not_leave_on_exchange_hp_reduction(board):
    """両替によるHP減少は「ダメージ」ではないため離脱判定が行われないことを検証します。"""
    g = board(p0=Side(hp=40, mp=10, money=20, guardian=MARS, hand=["deals/exchange"]))
    g.select("deals/exchange")
    g.num(20)  # HP を 20 にする
    g.num(10)  # MP を 10 にする

    g.expect(p0_hp=20, p0_guardian=MARS)
    assert g.rng.consumed(RollKind.GUARDIAN_LEAVE) == 0


def test_guardian_does_not_leave_on_fine_hp_deduction(board):
    """罰金でHPから引き落とされても離脱判定が行われないことを検証します。

    罰金は apply_damage ではなく execute_money_deduction（お金→MP→HPの順で徴収）
    を通るため、HPが減っても「ダメージ」ではありません。

    【重要】このテストは以前、PHASE_DEFENSE を手で組み立てて
    pending_attack_source_id に罰金を置く方式で書かれていた。しかしその経路では
    罰金の効果分岐に到達せず、単なる威力3の汎用ダメージとして処理されていた
    （実測でお金が1円も動いていないことを確認）。つまり罰金の実装を全く
    検証していないうえ、apply_damage 経由なので離脱判定も走っており、
    「守護神が去らない」というアサーションは偶然通っていただけだった。
    実際の金星神の経路で組み直している。
    """
    g = board(
        p0=Side(hp=40, mp=0, money=0, guardian=MARS, hand=[DISCARD_CARD]),
        p1=Side(hp=40, money=10, guardian=VENUS),
    )
    g.rng.deck_always(FILLER)
    g.rng.guardian_action_card(VENUS, "gurdians/fine")
    g.discard(DISCARD_CARD)

    g.expect(phase=GamePhase.PHASE_SUNDRY_SELECT_MIRROR, actor=0)
    g.take_hit()

    # お金もMPも0なので3はHPから引かれるが、ダメージ扱いではない
    g.expect(p0_hp=37, p0_money=0, p1_money=13, p0_guardian=MARS)
    assert g.rng.consumed(RollKind.GUARDIAN_LEAVE) == 0, (
        "罰金のHP引き落としは apply_damage を通らないので離脱判定は行われないべきです"
    )


# ============================================================================
# 暗雲と命中率
# ============================================================================


def test_dark_cloud_skips_the_accuracy_roll_entirely(board):
    """暗雲状態の相手への攻撃では、命中判定そのものが行われないことを検証します。

    従来は100回試して「100回全部命中したか」を数える統計テストだった。
    乱数の消費回数を観測できるようになったので、「必中」ではなく
    「判定していない」という実装の意図そのものを検証できる。
    """
    g = board(
        p0=Side(hp=40, hand=["weapons/vine-shoot"]),
        p1=Side(hp=40, curses=[CurseType.CURSE_DARK_CLOUD]),
    )
    # 外れる側に固定しても、暗雲下では判定が行われないので命中する
    g.rng.hits(always=False)
    g.attack("weapons/vine-shoot")

    g.expect(phase=GamePhase.PHASE_DEFENSE, attacker=0, defender=1)
    assert g.rng.consumed(RollKind.ACCURACY) == 0, "暗雲下では命中判定を行わないべきです"
    # 指示が空振りするので autouse 検査用に破棄する
    godfield_core.rng_clear_script()


@pytest.mark.parametrize("hits", [True, False], ids=["命中", "命中失敗"])
def test_accuracy_roll_decides_the_hit_without_dark_cloud(board, hits):
    """暗雲がない場合、命中率75%の武器の命中・失敗が判定どおりになることを検証します。"""
    g = board(p0=Side(hp=40, hand=["weapons/vine-shoot"]), p1=Side(hp=40))
    g.rng.hits(always=hits)
    g.attack("weapons/vine-shoot")

    if hits:
        g.expect(phase=GamePhase.PHASE_DEFENSE, attacker=0, defender=1)
    else:
        g.expect(p1_hp=40)
        g.expect_events(ev(EventType.ATTACK_MISS, card="weapons/vine-shoot"))

    # 命中判定は1回の攻撃につきちょうど1回。以前は仮置き時の情報更新
    # （update_staged_pending_info）でも判定が行われて結果が捨てられており、
    # 仮置き・解除の回数だけ乱数が余分に消費されていた。
    # roll_staged_attack_hits を分離して解決時のみ判定するようにした回帰防止。
    assert g.rng.consumed(RollKind.ACCURACY) == 1


@pytest.mark.parametrize("success", [True, False], ids=["弾き成功", "弾き失敗"])
def test_dark_cloud_does_not_affect_the_bounce_roll(board, success):
    """暗雲状態でも＜弾く＞の50%判定は行われ、結果が判定どおりになることを検証します。"""
    g = board(
        p0=Side(hp=40, mp=10, hand=["miracles/fireball"]),
        p1=Side(hp=40, mp=10, curses=[CurseType.CURSE_DARK_CLOUD],
                hand=["miracles/turbulence"]),
    )
    g.rng.deck_always(FILLER)
    g.rng.bounce(success=success)
    g.attack("miracles/fireball")
    g.defend("miracles/turbulence")

    assert g.rng.consumed(RollKind.BOUNCE) == 1, "暗雲は弾き判定の実行有無に影響しないべきです"
    if success:
        # 弾き成功で攻守交代し、元の攻撃者が奇跡防御側になる
        g.expect(phase=GamePhase.PHASE_MIRACLE_DEFENSE, actor=0, attacker=1, defender=0)
    else:
        g.expect_events(ev(EventType.BOUNCE_ATTACK, value=0.0))


# ============================================================================
# 防御カードの合法性（攻撃元の種別による差）
# ============================================================================


def setup_incoming_attack(g: Game, source: str, power: int, element: Element) -> Game:
    """任意の攻撃元による P1 の防御フェイズを直接組み立てます。

    守護神の固有攻撃・超常現象・指輪の反撃など、通常の手札からは作れない
    攻撃元を検証するために使います。
    """
    g.state.current_actor_id = 1
    g.state.current_phase = GamePhase.PHASE_DEFENSE
    g.state.attacker_id = 0
    g.state.defender_id = 1
    g.state.pending_attack_power = power
    g.state.pending_attack_element = element
    g.state.pending_attack_source_id = card_id(source)
    return g


@pytest.mark.parametrize(
    ("source", "power", "element", "wall_legal"),
    [
        # 武器・武器扱いの攻撃元には、虹のカーテンで無属性化してから＜壁＞を重ねられる
        ("phenomena/gigantic-tub", 50, Element.ELEM_LIGHT, True),
        ("gurdians/diamond-axe", 15, Element.ELEM_STONE, True),
        # 守護神固有の非武器攻撃には重ねられない
        ("gurdians/twinkle", 2, Element.ELEM_LIGHT, False),
    ],
    ids=["巨大なタライは武器扱い", "ダイヤモンドアクスは武器扱い", "点滅は非武器"],
)
def test_rainbow_curtain_then_wall_depends_on_the_source_being_a_weapon(
    board, source, power, element, wall_legal
):
    """虹のカーテンで無属性化した後に＜壁＞を重ねられるかが、攻撃元の種別で決まることを検証します。"""
    g = board(p1=Side(hp=40, mp=10, hand=["armor/rainbow-curtain", "miracles/wall"]))
    setup_incoming_attack(g, source, power, element)

    g.select("armor/rainbow-curtain")
    if wall_legal:
        g.expect_legal(["miracles/wall"])
    else:
        g.expect_illegal(["miracles/wall"])


def test_wall_is_legal_against_a_weapon_attack_after_the_curtain(board):
    """有属性の武器攻撃でも、虹のカーテンで無属性化すれば＜壁＞が使えることを検証します。"""
    g = board(
        p0=Side(hp=40, mp=10, hand=["weapons/blaze-blade"]),
        p1=Side(hp=40, mp=10, hand=["armor/rainbow-curtain", "miracles/wall"]),
    )
    g.attack("weapons/blaze-blade")
    g.expect(phase=GamePhase.PHASE_DEFENSE)
    g.expect_illegal(["miracles/wall"])  # 有属性のままでは不可

    g.select("armor/rainbow-curtain")
    g.expect_legal(["miracles/wall"])


def test_full_moon_blade_allows_wall_without_the_curtain(board):
    """満月刀は無属性の武器扱いなので、虹のカーテンなしで＜壁＞が使えることを検証します。"""
    g = board(p1=Side(hp=40, mp=10, hand=["armor/rainbow-curtain", "miracles/wall"]))
    setup_incoming_attack(g, "gurdians/full-moon-blade", 10, Element.ELEM_NONE)

    g.expect_legal(["miracles/wall"])


def test_zero_power_weapon_still_allows_defense_gear(board):
    """攻撃力0でも武器による攻撃なら防具を出せることを検証します。

    合法判定は「威力 > 0 または攻撃元が武器」なので、武器であれば威力0でも通ります。
    """
    g = board(
        p0=Side(hp=40, mp=0, hand=["weapons/magical-stick"]),
        p1=Side(hp=40, hand=["armor/iron-shield"]),
    )
    g.attack("weapons/magical-stick")

    g.expect(phase=GamePhase.PHASE_DEFENSE, pending_power=0)
    g.expect_legal(["armor/iron-shield"])


@pytest.mark.parametrize(
    "miracle",
    # ＜閃光＞も威力0の状態異常奇跡だが全体攻撃なので PHASE_GROUP_MIRACLE_PLUS を
    # 経由する別経路になる。ここでは単体対象のものだけを対象にする。
    ["miracles/fog", "miracles/dream", "miracles/dark-cloud", "miracles/wind"],
)
def test_zero_power_status_miracle_forbids_defense_gear(board, miracle):
    """攻撃力0の状態異常奇跡には一般防具を出せず、反射のみ可能であることを検証します。

    【監査メモ】このテストは以前、PHASE_DEFENSE を手で組み立てて「点滅（守護神）の
    威力を0にした状態」で書かれていた。しかし
      - 点滅の実際の威力は2で、威力0の状態は実経路では発生しない
      - 威力を0にしても2にしても防具は非合法（光属性攻撃に無属性防具を出せない
        という属性ルールが理由）
    だったため、「威力0だから防具を出せない」という規則を一切検証できていなかった。

    威力0かつ非武器という条件が実際に成立するのは、状態異常だけを与える奇跡が
    奇跡防御フェイズを起動したときなので、そちらで検証する。
    """
    g = board(
        p0=Side(hp=40, mp=50, hand=[miracle]),
        p1=Side(hp=40, mp=50, hand=["armor/iron-shield", "armor/super-mirror"]),
    )
    g.attack(miracle)

    g.expect(phase=GamePhase.PHASE_MIRACLE_DEFENSE, pending_power=0)
    g.expect_illegal(["armor/iron-shield"])
    g.expect_legal(["armor/super-mirror"])


# ============================================================================
# 低レベルAPI経路の確認
# ============================================================================


def test_raw_action_path_still_works(board):
    """DSL を経由せず ActionType を直接渡す経路が壊れていないことを確認します。"""
    g = board(p0=Side(hp=40, hand=[DISCARD_CARD]), p1=Side(hp=40))
    g.rng.deck_always(FILLER)
    godfield_core.step_game(g.state, ActionType.ACTION_DISCARD)
    g.expect(phase=GamePhase.PHASE_DISCARD, actor=0)
