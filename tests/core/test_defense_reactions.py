"""防御・リアクション（＜壁＞／＜乱気流＞／反射・弾き／虹のカーテン／閃光）の検証。

【移行メモ】
このファイルの旧テストには次の3種類の問題がありました。

1. **手で組み立てた防御フェイズ**
   `pending_attack_power` などを直接代入して防御フェイズを作っていたため、
   「その局面が実際に発生しうるか」が一切検証されていませんでした。攻撃力や属性が
   実装と食い違っていても気付けず、逆に実装のセットアップ処理が壊れても通ります。
   現在は超常現象・守護神行動を実際に発生させて同じ局面へ到達します。

2. **どちらの結果でも通るアサーション**
   `assert hp == 40 or hp == 30` のように、弾きの成否どちらでも通る書き方が
   ありました。弾き判定を固定して両分岐をそれぞれ検証します。

3. **結果の数値の直書き**
   `assert hp == 31` の 31 がどう計算されるのか読めませんでした。攻撃力・防御力は
   カードマスタから引いて式で書きます。
"""

import pytest

import godfield_core
from godfield_core import (
    ActionType,
    CurseType,
    Element,
    EventType,
    GamePhase,
    PhenomenonType,
    RollKind,
)
from tests.core.dsl import (
    Side,
    all_cards,
    card_feature,
    card_id,
    card_name,
    cards_of_element,
    cards_where,
    element_of,
)

FILLER = "armor/wood-shield"

CURTAIN = "armor/rainbow-curtain"
WALL = "miracles/wall"
TURBULENCE = "miracles/turbulence"
FLAME = "miracles/flame"
REFLECTION_SWORD = "weapons/reflection-sword"
LEATHER_CLOTHES = "armor/leather-clothes"
SUPER_MIRROR = "armor/super-mirror"

SATURN = int(godfield_core.GuardianType.SATURN)
MOON = int(godfield_core.GuardianType.MOON)


# ============================================================================
# ＜壁＞: 無属性の物理攻撃だけを阻止できる
# ============================================================================


@pytest.mark.parametrize(
    ("weapon", "wall_is_legal"),
    [
        ("weapons/punch", True),    # 無属性
        ("weapons/torch", False),   # 火属性
    ],
    ids=["無属性攻撃には出せる", "有属性攻撃には出せない"],
)
def test_wall_only_blocks_un_elemental_physical_attacks(board, weapon, wall_is_legal):
    """＜壁＞が無属性の物理攻撃にしか出せないことを検証します。"""
    assert (element_of(weapon) == Element.ELEM_NONE) is wall_is_legal, (
        "テストの前提（武器の属性）がカードマスタと食い違っています"
    )

    g = board(
        p0=Side(hp=40, mp=10, hand=[weapon]),
        p1=Side(hp=40, mp=10, hand=[WALL]),
    )
    g.rng.deck_always(FILLER)

    g.attack(weapon)
    g.expect(phase=GamePhase.PHASE_DEFENSE, actor=1)

    if wall_is_legal:
        g.expect_legal([WALL])
    else:
        g.expect_illegal([WALL])


def test_wall_blocks_the_attack_entirely(board):
    """＜壁＞が成立すると被弾が0になり、そのままターンが終わることを検証します。"""
    g = board(
        p0=Side(hp=40, mp=10, hand=["weapons/punch"]),
        p1=Side(hp=40, mp=10, hand=[WALL]),
    )
    g.rng.deck_always(FILLER)

    g.attack("weapons/punch")
    g.defend(WALL)

    assert card_feature("weapons/punch", "attack_power") > 0, (
        "攻撃力が0ならこのテストは阻止を検証していない"
    )
    g.expect(p1_hp=40, phase=GamePhase.PHASE_MAIN)


# ============================================================================
# 虹のカーテン: 攻撃を無属性化する（1枚目のみ）
# ============================================================================


def test_rainbow_curtain_unlocks_the_wall_against_an_elemental_attack(board):
    """有属性攻撃でも、虹のカーテンで無属性化すれば＜壁＞を重ねられることを検証します。"""
    torch = "weapons/torch"
    g = board(
        p0=Side(hp=40, mp=10, hand=[torch]),
        p1=Side(hp=40, mp=10, hand=[CURTAIN, WALL]),
    )
    g.rng.deck_always(FILLER)

    g.attack(torch)
    g.expect(phase=GamePhase.PHASE_DEFENSE, actor=1)

    # カーテンを置く前は、属性が合わないので＜壁＞は出せない
    g.expect_legal([CURTAIN])
    g.expect_illegal([WALL])

    g.select(CURTAIN)

    # 無属性化は合法手の判定に反映される（pending_attack_element の書き換えは解決時）
    g.expect_legal([WALL])

    g.defend(WALL)
    g.expect(p1_hp=40, phase=GamePhase.PHASE_MAIN)


def test_rainbow_curtain_can_be_stacked_any_number_of_times(board):
    """虹のカーテンを何枚でも重ねられることを検証します。

    2枚目以降に機械的な意味はありません（守0で属性を消すだけ）が、手札を回す目的で
    重ねることがあるため合法手として残っています。
    """
    torch = "weapons/torch"
    g = board(
        p0=Side(hp=40, mp=10, hand=[torch]),
        p1=Side(hp=40, mp=10, hand=[CURTAIN] * 3),
    )
    g.rng.deck_always(FILLER)

    g.attack(torch)
    for slot in range(3):
        assert g.legal_actions()[int(ActionType.ACTION_SELECT_HAND_0) + slot], (
            f"{slot + 1}枚目の虹のカーテンが置けません"
        )
        g.select_slots(slot)
    assert g.state.get_num_staged_cards(1) == 3


def test_rainbow_curtain_cannot_follow_a_plain_armor(board):
    """一般防具を置いた後には虹のカーテンを重ねられないことを検証します。

    カーテンが何枚でも置けるのは「まだ何も防御していない」あいだだけです。
    """
    torch = "weapons/torch"
    armor = "armor/aqua-shoes"  # 水属性なので火属性の武器攻撃に出せる
    g = board(
        p0=Side(hp=40, mp=10, hand=[torch]),
        p1=Side(hp=40, mp=10, hand=[armor, CURTAIN]),
    )
    g.rng.deck_always(FILLER)

    g.attack(torch)
    g.expect_legal([CURTAIN])

    g.select(armor)
    g.expect_illegal([CURTAIN])


def test_rainbow_curtain_unlocks_plain_armor_and_keeps_the_reaction(board):
    """奇跡攻撃に虹のカーテンを置くと、一般防具が解禁され、リアクションも残ることを検証します。

    無属性化によって「属性が合わないので出せなかった防具」が解禁されます。
    ＜乱気流＞のようなリアクションは1枚目にしか置けませんが、虹のカーテンの
    直後（2枚目）だけは例外的に許されます。

    以前この例外は物理防御でしか認められておらず、虹のカーテンの後に
    ＜壁＞は置けるのに＜乱気流＞は置けない、という非対称になっていました。
    """
    armor = "armor/wood-shield"
    g = board(
        p0=Side(hp=40, mp=10, hand=[FLAME]),
        p1=Side(hp=40, mp=10, hand=[CURTAIN, TURBULENCE, armor]),
    )
    g.rng.deck_always(armor)

    g.attack(FLAME)
    g.expect(phase=GamePhase.PHASE_MIRACLE_DEFENSE)

    # カーテンとリアクションは出せるが、属性の合わない一般防具はまだ出せない
    g.expect_legal([CURTAIN, TURBULENCE])
    g.expect_illegal([armor])

    g.select(CURTAIN)

    # 無属性化で一般防具が解禁され、カーテン直後なのでリアクションも置ける
    g.expect_legal([armor, TURBULENCE])

    g.defend(armor)

    damage = card_feature(FLAME, "attack_power") - card_feature(armor, "defense_power")
    g.expect(p1_hp=40 - damage, phase=GamePhase.PHASE_MAIN)


def test_a_reaction_cannot_follow_a_plain_armor(board):
    """一般防具を置いた後にはリアクションを重ねられないことを検証します。

    例外は虹のカーテンの直後だけで、他の防具を挟むと置けなくなります。
    """
    armor = "armor/aqua-shoes"   # 水属性なので火属性の奇跡に出せる
    g = board(
        p0=Side(hp=40, mp=10, hand=[FLAME]),
        p1=Side(hp=40, mp=10, hand=[armor, TURBULENCE]),
    )
    g.rng.deck_always(FILLER)

    g.attack(FLAME)
    g.expect_legal([TURBULENCE])

    g.select(armor)
    g.expect_illegal([TURBULENCE])


@pytest.mark.parametrize(
    "attack",
    [FLAME, "weapons/flare-axe"],
    ids=["火属性の奇跡攻撃", "火属性の武器攻撃"],
)
def test_rainbow_curtain_unlocks_every_element_of_armor(board, attack):
    """虹のカーテンの後は、全属性の防具が2枚目として出せることを検証します。

    防具はカードマスタから属性ごとに引くため、カードデータが増減しても
    「たまたま手札に入れた数種類」しか見ていない状態になりません。
    """
    elements = [
        Element.ELEM_NONE,
        Element.ELEM_FIRE,
        Element.ELEM_WATER,
        Element.ELEM_WOOD,
        Element.ELEM_STONE,
        Element.ELEM_LIGHT,
    ]
    # 属性ごとに「通常の防御フェイズにしか出せない素の防具」を1枚ずつ選ぶ。
    # リアクションや別フェイズ用のカードが混ざると、解禁の理由が属性以外に
    # なってしまい、何を検証しているのか分からなくなる。
    armors = []
    for elem in elements:
        plain = [
            cid
            for cid in cards_of_element(elem, "defense")
            if not card_feature(cid, "reaction_type", None)
            and card_feature(cid, "usage_timing", []) == ["atk_defence_phase"]
        ]
        assert plain, f"属性 {Element(elem).name} の素の防具がカードマスタにありません"
        armors.append(plain[0])

    g = board(
        p0=Side(hp=99, mp=20, hand=[attack]),
        p1=Side(hp=99, mp=20, hand=[CURTAIN, *armors]),
    )
    g.rng.deck_always(FILLER)
    if card_feature(attack, "accuracy", 100) < 100:
        g.rng.hits(always=True)

    g.attack(attack)
    assert g.state.pending_attack_element != Element.ELEM_NONE, (
        "無属性攻撃ではカーテンの効果を検証できない"
    )

    # カーテンを置く前は、対抗属性の防具しか出せない
    g.expect_illegal([a for a in armors if element_of(a) == Element.ELEM_NONE])

    g.select(CURTAIN)
    g.expect_legal(armors)


def test_rainbow_curtain_still_allows_a_reaction_armor(board):
    """虹のカーテンの後でも、リアクション「防具」は2枚目として出せることを検証します。

    リアクション「奇跡」（＜乱気流＞など）が封じられるのとは扱いが異なります。
    """
    meteor = "miracles/meteor"
    sky_armor = "armor/sky-armor"
    g = board(
        p0=Side(hp=40, mp=20, hand=[meteor]),
        p1=Side(hp=40, mp=20, hand=[CURTAIN, sky_armor]),
    )
    g.rng.deck_always(FILLER)
    # スカイアーマーは弾きを持つ。ここで見たいのは「2枚目として出せること」なので、
    # 弾きは失敗側に固定する（固定しないと50%で攻守が入れ替わり、被弾を見られない）。
    g.rng.bounce(success=False)

    g.attack(meteor)
    g.expect(phase=GamePhase.PHASE_MIRACLE_DEFENSE)

    g.select(CURTAIN)
    g.expect_legal([sky_armor])

    g.defend(sky_armor)

    # 弾きが発動した（そして失敗した）ので、スカイアーマーの防御力は乗らない。
    # 虹のカーテンは防御力0なので、攻撃力がそのまま通る。
    assert card_feature(CURTAIN, "defense_power") == 0
    g.expect(p1_hp=40 - card_feature(meteor, "attack_power"))


def test_countering_element_armor_is_legal_against_a_miracle_without_the_curtain(board):
    """奇跡攻撃には、カーテンなしでも対抗属性の防具だけが出せることを検証します。"""
    aqua = "armor/aqua-shoes"      # 水属性（火に対抗）
    plain = "armor/leather-cap"    # 無属性（対抗しない）
    assert element_of(aqua) == Element.ELEM_WATER
    assert element_of(plain) == Element.ELEM_NONE

    g = board(
        p0=Side(hp=40, mp=10, hand=[FLAME]),
        p1=Side(hp=40, mp=10, hand=[CURTAIN, aqua, plain]),
    )
    g.rng.deck_always(FILLER)

    g.attack(FLAME)
    g.expect(phase=GamePhase.PHASE_MIRACLE_DEFENSE)

    g.expect_legal([CURTAIN, aqua])
    g.expect_illegal([plain])

    g.defend(aqua)

    damage = card_feature(FLAME, "attack_power") - card_feature(aqua, "defense_power")
    g.expect(p1_hp=40 - damage, phase=GamePhase.PHASE_MAIN)


# ============================================================================
# 反射・弾き
# ============================================================================


def test_rainbow_curtain_enables_the_reflection_sword(board):
    """有属性の武器攻撃でも、カーテンで無属性化すれば反射剣で反射できることを検証します。"""
    torch = "weapons/torch"
    g = board(
        p0=Side(hp=40, mp=10, hand=[torch, LEATHER_CLOTHES]),
        p1=Side(hp=40, mp=10, hand=[CURTAIN, REFLECTION_SWORD]),
    )
    g.rng.deck_always(FILLER)

    g.attack(torch)
    g.expect_illegal([REFLECTION_SWORD])

    g.select(CURTAIN)
    g.expect_legal([REFLECTION_SWORD])

    g.defend(REFLECTION_SWORD)

    # 攻守が入れ替わり、無属性化されたまま元の攻撃者へ跳ね返る
    g.expect(
        attacker=1,
        defender=0,
        actor=0,
        phase=GamePhase.PHASE_DEFENSE,
        pending_element=Element.ELEM_NONE,
    )
    g.expect_legal([LEATHER_CLOTHES])

    g.defend(LEATHER_CLOTHES)

    damage = max(
        0,
        card_feature(torch, "attack_power") - card_feature(LEATHER_CLOTHES, "defense_power"),
    )
    g.expect(p0_hp=40 - damage, phase=GamePhase.PHASE_MAIN)


def test_bouncing_sword_swaps_attacker_and_defender_on_success(board):
    """乱弾武剣で弾きに成功すると攻守が交代し、元の攻撃者が被弾することを検証します。"""
    boomerang = "weapons/boomerang"
    sword = "weapons/bouncing-sword"
    g = board(
        p0=Side(hp=40, mp=10, hand=[boomerang, LEATHER_CLOTHES]),
        p1=Side(hp=40, mp=10, hand=[sword]),
    )
    g.rng.deck_always(FILLER)
    g.rng.bounce(success=True)

    g.attack(boomerang)
    g.expect(phase=GamePhase.PHASE_DEFENSE, actor=1)

    g.defend(sword)

    g.expect(attacker=1, defender=0, actor=0, phase=GamePhase.PHASE_DEFENSE, p1_hp=40)
    g.expect_legal([LEATHER_CLOTHES])

    g.defend(LEATHER_CLOTHES)

    damage = card_feature(boomerang, "attack_power") - card_feature(LEATHER_CLOTHES, "defense_power")
    assert damage > 0, "被弾0ではダメージが正しく攻撃者へ渡ったか検証できない"
    g.expect(p0_hp=40 - damage, phase=GamePhase.PHASE_MAIN)


def test_bouncing_sword_failure_leaves_the_defender_taking_the_hit(board):
    """乱弾武剣の弾きに失敗すると、そのまま自分が被弾することを検証します。"""
    boomerang = "weapons/boomerang"
    sword = "weapons/bouncing-sword"
    g = board(
        p0=Side(hp=40, mp=10, hand=[boomerang]),
        p1=Side(hp=40, mp=10, hand=[sword]),
    )
    g.rng.deck_always(FILLER)
    g.rng.bounce(success=False)

    g.attack(boomerang)
    g.defend(sword)

    # 弾きに失敗した乱弾武剣は防御力を持たないので、攻撃力がそのまま通る
    g.expect(p1_hp=40 - card_feature(boomerang, "attack_power"), phase=GamePhase.PHASE_MAIN)


def bounce_scenario(board, *, success: bool, defender_hp: int):
    """P0 の＜吸収＞を P1 が＜乱気流＞で弾く局面を解決します。

    ＜弾く＞は50%判定なので、従来はこの成否を得るために最大200回のシード探索を
    行っていました。現在は判定を直接固定します。
    """
    g = board(
        p0=Side(hp=40, mp=10, hand=["miracles/absorption"]),
        p1=Side(hp=defender_hp, mp=10, hand=[TURBULENCE]),
    )
    g.rng.deck_always(FILLER)
    g.rng.bounce(success=success)
    g.attack("miracles/absorption")
    g.defend(TURBULENCE)
    return g


def test_bounce_success_swaps_attacker_and_defender(board):
    """＜弾く＞成功時に攻守が入れ替わり、弾いた本人が無傷であることを検証します。"""
    g = bounce_scenario(board, success=True, defender_hp=5)

    g.expect(
        attacker=1,
        defender=0,
        actor=0,
        phase=GamePhase.PHASE_MIRACLE_DEFENSE,
        p1_hp=5,  # 弾いた本人は無傷
    )


def test_bounce_failure_reflects_the_attack_onto_the_defender(board):
    """＜弾く＞失敗時に攻撃が自分へ跳ね返り、自傷として解決されることを検証します。

    ＜吸収＞は与えたダメージ分だけ回復するため、自傷では損失と回復が相殺されます。
    吸収が効いていなければHPが減るので、この等価性が吸収の検証にもなっています。
    """
    power = card_feature("miracles/absorption", "attack_power")
    g = bounce_scenario(board, success=False, defender_hp=20)

    g.expect(p1_hp=20, phase=GamePhase.PHASE_MAIN)
    assert power > 0, "吸収の攻撃力が0ならこのテストは何も検証していない"


def test_bounce_failure_absorption_revives_from_zero_before_death_check(board):
    """吸収の自傷でHPが0に張り付いても、死亡判定の前に回復して生存することを検証します。

    HP5 に対して攻撃力10の吸収を自傷すると、いったん0にクランプされたあと
    同じ解決ステップ内で +10 されるため、最終HPは10になります。
    """
    power = card_feature("miracles/absorption", "attack_power")
    g = bounce_scenario(board, success=False, defender_hp=5)

    g.expect(p1_hp=power, is_done=False, phase=GamePhase.PHASE_MAIN)


@pytest.mark.parametrize("bounced", [True, False], ids=["弾きに成功", "弾きに失敗"])
def test_sky_harpoon_reacts_to_a_miracle_attack(board, bounced):
    """武器でありながら奇跡防御で弾けるスカイハープーンの、成否それぞれを検証します。

    従来は `assert hp == 40 or hp == 30` と書かれており、弾きの成否どちらでも
    通るため、リアクションが機能しなくなっても検出できませんでした。
    """
    harpoon = "weapons/sky-harpoon"
    g = board(
        p0=Side(hp=40, mp=20, hand=[FLAME, LEATHER_CLOTHES]),
        p1=Side(hp=40, mp=20, hand=[harpoon]),
    )
    g.rng.deck_always(FILLER)
    g.rng.bounce(success=bounced)

    g.attack(FLAME)
    g.expect(phase=GamePhase.PHASE_MIRACLE_DEFENSE, actor=1)
    g.expect_legal([harpoon])

    g.defend(harpoon)

    if bounced:
        # 弾いた本人は無傷で、攻撃が元の攻撃者へ渡る
        g.expect(p1_hp=40, attacker=1, defender=0, actor=0)
    else:
        g.expect(p1_hp=40 - card_feature(FLAME, "attack_power"), phase=GamePhase.PHASE_MAIN)


def test_angel_bow_blocks_a_miracle_attack(board):
    """エンゼルの弓が奇跡防御で「阻止」として働き、被弾を0にすることを検証します。"""
    bow = "weapons/angel-bow"
    g = board(
        p0=Side(hp=40, mp=20, hand=[FLAME]),
        p1=Side(hp=40, mp=20, hand=[bow]),
    )
    g.rng.deck_always(FILLER)

    g.attack(FLAME)
    g.expect_legal([bow])

    g.defend(bow)

    assert card_feature(FLAME, "attack_power") > 0, "攻撃力が0では阻止を検証できない"
    g.expect(p1_hp=40, phase=GamePhase.PHASE_MAIN)


# ============================================================================
# 守護神・超常現象による攻撃への反射
#
# 旧テストは pending_attack_* を直接代入して防御フェイズを組み立てていたため、
# 「その攻撃力・属性が本当にその発生源から出るのか」を一切検証していませんでした。
# ここでは実際に超常現象・守護神行動を発生させて同じ局面に到達します。
# ============================================================================


def test_gigantic_tub_is_a_light_attack_reflectable_through_the_curtain(board):
    """巨大なタライ（光属性）が、虹のカーテン経由で反射剣により反射できることを検証します。"""
    tub = "phenomena/gigantic-tub"
    assert element_of(tub) == Element.ELEM_LIGHT

    g = board(
        p0=Side(hp=99, mp=10, hand=["sundries/string-of-fate", LEATHER_CLOTHES]),
        p1=Side(hp=99, mp=10, hand=[CURTAIN, REFLECTION_SWORD]),
    )
    g.rng.deck_always(FILLER)
    g.rng.phenomenon(PhenomenonType.GIGANTIC_TUB)
    g.rng.force(godfield_core.RollKind.PHENOMENON_TUB_TARGET, 1)  # P1 を狙う

    g.attack("sundries/string-of-fate", to_self=True)

    g.expect(
        phase=GamePhase.PHASE_DEFENSE,
        actor=1,
        pending_element=Element.ELEM_LIGHT,
        pending_power=card_feature(tub, "attack_power"),
    )

    # 有属性なので、カーテンなしでは反射剣を置けない
    g.expect_illegal([REFLECTION_SWORD])
    g.select(CURTAIN)
    g.expect_legal([REFLECTION_SWORD])

    g.defend(REFLECTION_SWORD)
    g.expect(actor=0, phase=GamePhase.PHASE_DEFENSE, pending_element=Element.ELEM_NONE)


def test_super_mirror_reflects_the_gigantic_tub_without_a_curtain(board):
    """巨大なタライをスーパーミラーで反射できることを検証します。

    反射剣と違い、スーパーミラーは有属性攻撃でも虹のカーテンなしで置けます。
    """
    tub = "phenomena/gigantic-tub"
    power = card_feature(tub, "attack_power")

    g = board(
        p0=Side(hp=99, mp=10, hand=["sundries/string-of-fate"]),
        p1=Side(hp=99, mp=10, hand=[SUPER_MIRROR, REFLECTION_SWORD]),
    )
    g.rng.deck_always(FILLER)
    g.rng.phenomenon(PhenomenonType.GIGANTIC_TUB)
    g.rng.force(godfield_core.RollKind.PHENOMENON_TUB_TARGET, 1)  # P1 を狙う

    g.attack("sundries/string-of-fate", to_self=True)
    g.expect(phase=GamePhase.PHASE_DEFENSE, actor=1, attacker=0, defender=1)

    # 光属性なので反射剣はカーテンなしでは置けないが、スーパーミラーは置ける
    g.expect_illegal([REFLECTION_SWORD])
    g.expect_legal([SUPER_MIRROR])

    g.defend(SUPER_MIRROR)

    # 攻守が入れ替わり、攻撃力・属性はそのまま撃った側へ返る
    g.expect(
        phase=GamePhase.PHASE_DEFENSE,
        actor=0,
        attacker=1,
        defender=0,
        pending_power=power,
        pending_element=element_of(tub),
    )

    g.take_hit()
    g.expect(p0_hp=99 - power, p1_hp=99)


def test_super_mirror_reflects_the_black_hole_keeping_it_a_group_attack(board):
    """ブラックホールをスーパーミラーで反射でき、全体攻撃属性が保たれることを検証します。"""
    hole = "phenomena/black-hole"
    power = card_feature(hole, "attack_power")

    g = board(
        p0=Side(hp=99, mp=10, hand=["sundries/string-of-fate"]),
        p1=Side(hp=99, mp=10, hand=[SUPER_MIRROR, FILLER]),
    )
    g.rng.deck_always(FILLER)
    g.rng.phenomenon(PhenomenonType.BLACK_HOLE)

    g.attack("sundries/string-of-fate", to_self=True)
    g.expect(
        phase=GamePhase.PHASE_DEFENSE,
        actor=1,
        attacker=0,
        defender=1,
        pending_is_group=True,
    )

    g.expect_legal([SUPER_MIRROR])
    g.defend(SUPER_MIRROR)

    g.expect(
        phase=GamePhase.PHASE_DEFENSE,
        actor=0,
        attacker=1,
        defender=0,
        pending_power=power,
        pending_element=element_of(hole),
        pending_is_group=True,
    )

    # 闇属性なので、虹のカーテンなしで通すと防御力に関係なく即死します
    g.take_hit()
    g.expect(p0_hp=0, p1_hp=99, is_done=True)


def test_diamond_axe_is_a_stone_attack_reflectable_through_the_curtain(board):
    """土星神のダイヤモンドアクス（土属性）が、カーテン経由で反射できることを検証します。"""
    axe = "gurdians/diamond-axe"
    assert element_of(axe) == Element.ELEM_STONE

    # 反射剣を持っていると「祈る」が非合法になるため、捨て札でターンを終える
    g = board(
        p0=Side(hp=99, mp=10, hand=[CURTAIN, REFLECTION_SWORD, "armor/leather-cap"]),
        p1=Side(hp=99, mp=10, guardian=SATURN, hand=[LEATHER_CLOTHES]),
    )
    g.rng.deck_always(FILLER)
    g.rng.guardian_action_card(SATURN, axe)

    g.discard("armor/leather-cap")

    g.expect(
        phase=GamePhase.PHASE_DEFENSE,
        actor=0,
        pending_element=Element.ELEM_STONE,
        pending_power=card_feature(axe, "attack_power"),
    )

    g.expect_illegal([REFLECTION_SWORD])
    g.select(CURTAIN)
    g.expect_legal([REFLECTION_SWORD])

    g.defend(REFLECTION_SWORD)
    g.expect(actor=1, phase=GamePhase.PHASE_DEFENSE, pending_element=Element.ELEM_NONE)


def test_full_moon_blade_is_un_elemental_and_directly_reflectable(board):
    """月神の満月刀（無属性）が、カーテンなしで直接反射できることを検証します。

    満月刀は月神が＜オーラ＞を引いたときの物理攻撃として現れます。
    """
    blade = "gurdians/full-moon-blade"
    assert element_of(blade) == Element.ELEM_NONE

    g = board(
        p0=Side(hp=99, mp=10, hand=[REFLECTION_SWORD, "armor/leather-cap"]),
        p1=Side(hp=99, mp=10, guardian=MOON, hand=[LEATHER_CLOTHES]),
    )
    g.rng.deck_always(FILLER)
    g.rng.guardian_act(acts=True)
    g.rng.moon_miracle("miracles/aura")

    g.discard("armor/leather-cap")

    # ＜オーラ＞は威力2倍の奇跡なので、満月刀の攻撃力の2倍で撃たれる
    g.expect(
        phase=GamePhase.PHASE_DEFENSE,
        actor=0,
        pending_element=Element.ELEM_NONE,
        pending_power=card_feature(blade, "attack_power") * 2,
    )

    # 無属性なので、カーテンを挟まずそのまま反射剣を置ける
    g.expect_legal([REFLECTION_SWORD])
    g.defend(REFLECTION_SWORD)

    g.expect(actor=1, phase=GamePhase.PHASE_DEFENSE)


# ============================================================================
# 攻守兼用カード
# ============================================================================


def test_sword_shield_guards_with_its_defense_power(board):
    """武器であるソードシールドを防御に使うと、防御力が仮置き防御力へ加算されることを検証します。"""
    sword_shield = "weapons/sword-shield"
    attack = "weapons/plate-of-strike"
    guard = card_feature(sword_shield, "defense_power")
    power = card_feature(attack, "attack_power")
    assert guard >= power, "完全にガードできる組み合わせである前提のテスト"

    g = board(
        p0=Side(hp=40, mp=10, hand=[attack]),
        p1=Side(hp=40, mp=10, hand=[sword_shield]),
    )
    g.rng.deck_always(FILLER)

    g.attack(attack)
    g.expect(phase=GamePhase.PHASE_DEFENSE, actor=1)
    g.expect_legal([sword_shield])

    g.select(sword_shield)
    g.expect(pending_defense=guard)

    g.confirm()
    g.expect(p1_hp=40)


def test_ogre_gauntlet_adds_its_attack_power_in_the_attack_plus_phase(board):
    """防具である鬼の小手を攻撃プラスで重ねると、攻撃力が加算されることを検証します。"""
    gauntlet = "armor/ogre-s-gauntlet"
    attack = "weapons/plate-of-strike"
    total = card_feature(attack, "attack_power") + card_feature(gauntlet, "attack_power")

    g = board(
        p0=Side(hp=40, mp=10, hand=[attack, gauntlet]),
        p1=Side(hp=40, mp=10),
    )
    g.rng.deck_always(FILLER)

    g.select(attack)
    g.expect(phase=GamePhase.PHASE_ATTACK_PLUS)
    g.expect_legal([gauntlet])

    g.select(gauntlet)
    g.expect(pending_power=total)

    g.target_opp()
    g.take_hit()

    g.expect(p1_hp=40 - total)


# ============================================================================
# 精霊系カードによる MP 消費の相殺
# ============================================================================


@pytest.mark.parametrize(
    ("attack", "reaction", "spiritual", "phase"),
    [
        (FLAME, TURBULENCE, "weapons/spiritual-staff", GamePhase.PHASE_MIRACLE_DEFENSE),
        ("weapons/punch", WALL, "armor/spiritual-socks", GamePhase.PHASE_DEFENSE),
    ],
    ids=["乱気流＋精霊の杖", "＜壁＞＋精霊の足袋"],
)
def test_a_spiritual_card_lets_you_afford_a_reaction_you_could_not_pay_for(
    board, attack, reaction, spiritual, phase
):
    """MPが足りないリアクションでも、精霊系カードを重ねれば出せることを検証します。

    精霊系はリアクションを仮置きした「あと」でしか選べないため、
    仮置き前後で合法手が変わることも確認します。
    """
    cost = card_feature(reaction, "mp_cost")
    mp = cost - 1
    assert mp >= 0, "MPが足りない状況を作れる消費コストである前提のテスト"

    g = board(
        p0=Side(hp=40, mp=20, hand=[attack]),
        p1=Side(hp=40, mp=mp, hand=[reaction, spiritual]),
    )
    g.rng.deck_always(FILLER)

    g.attack(attack)
    g.expect(phase=phase, actor=1)

    g.expect_legal([reaction])

    g.select(reaction)

    # MPが足りないので、精霊を重ねるまでは確定できない
    g.expect_actions(confirm=False)
    g.expect_legal([spiritual])

    g.select(spiritual)
    g.expect_actions(confirm=True)

    g.confirm()

    g.expect(p1_mp=mp)  # 消費が0になるのでMPは減らない


# ============================================================================
# 閃光: 防具を1枚しか置けない
# ============================================================================


def test_flash_prevents_stacking_and_therefore_unaffordable_reactions(board):
    """閃光状態では防具を1枚しか置けないため、精霊で相殺する前提のカードが出せなくなることを検証します。"""
    doll = "sundries/spiritual-doll"
    cost = card_feature(WALL, "mp_cost")
    assert cost > 0, "MP消費0のカードでは閃光の制約を検証できない"

    g = board(
        p0=Side(hp=40, mp=20, hand=["weapons/punch"]),
        p1=Side(hp=40, mp=0, curses=[CurseType.CURSE_FLASH], hand=[WALL, doll, LEATHER_CLOTHES]),
    )
    g.rng.deck_always(FILLER)

    g.attack("weapons/punch")
    g.expect(phase=GamePhase.PHASE_DEFENSE, actor=1)

    # ＜壁＞は精霊を重ねられないと払えないが、閃光で重ねられないので非合法
    g.expect_illegal([WALL, doll])
    g.expect_legal([LEATHER_CLOTHES])

    g.select(LEATHER_CLOTHES)

    # 1枚置いた時点で、確定以外の選択肢が消える
    g.expect_actions(confirm=True)
    g.expect_illegal([WALL, doll])

    g.confirm()

    damage = card_feature("weapons/punch", "attack_power") - card_feature(
        LEATHER_CLOTHES, "defense_power"
    )
    g.expect(p1_hp=40 - damage)


def test_flash_still_allows_a_single_free_armor(board):
    """閃光でもMP消費のない防具1枚は問題なく出せることを検証します（制約が強すぎないこと）。"""
    g = board(
        p0=Side(hp=40, mp=20, hand=["weapons/punch"]),
        p1=Side(hp=40, mp=0, curses=[CurseType.CURSE_FLASH], hand=[FILLER, LEATHER_CLOTHES]),
    )
    g.rng.deck_always(FILLER)

    g.attack("weapons/punch")
    g.expect_legal([FILLER, LEATHER_CLOTHES])

    g.defend(FILLER)

    damage = max(
        0,
        card_feature("weapons/punch", "attack_power") - card_feature(FILLER, "defense_power"),
    )
    g.expect(p1_hp=40 - damage, phase=GamePhase.PHASE_MAIN)


# ============================================================================
# 光属性防具は対抗属性と併用できる
# ============================================================================


@pytest.mark.parametrize(
    "order",
    [
        ["armor/glittering-dress", "armor/aqua-shoes"],
        ["armor/aqua-shoes", "armor/glittering-dress"],
    ],
    ids=["ドレスが先", "シューズが先"],
)
def test_light_armor_can_be_combined_with_a_countering_element(board, order):
    """火の奇跡に対し、光属性防具と水属性防具を順序に関わらず重ねられることを検証します。

    光属性は中立なので、対抗属性（水）の防具と組み合わせても弾かれません。
    重ねている途中で勝手に自動進行せず、プレイヤーの入力を待つことも確認します。
    """
    total_defense = sum(card_feature(c, "defense_power") for c in order)
    assert total_defense >= card_feature(FLAME, "attack_power"), (
        "完全に防ぎ切れる組み合わせである前提のテスト"
    )

    g = board(
        p0=Side(hp=40, mp=20, hand=[FLAME]),
        p1=Side(hp=40, mp=20, hand=list(order)),
    )
    g.rng.deck_always(FILLER)

    g.attack(FLAME)
    g.expect(phase=GamePhase.PHASE_MIRACLE_DEFENSE, actor=1)
    g.expect_legal(order)

    g.select(order[0])

    # 1枚目を置いた後も2枚目が選べ、かつ自動進行せず入力を待っていること
    g.expect_legal([order[1]])
    assert godfield_core.get_single_legal_action(g.state) == -1, (
        "選択肢が残っているので自動進行してはいけない"
    )
    g.expect(phase=GamePhase.PHASE_MIRACLE_DEFENSE)

    g.defend(order[1])

    g.expect(p1_hp=40)  # 合計ガードが攻撃力以上なので無傷


def test_confirm_is_illegal_while_staged_cards_cost_more_mp_than_you_have(board):
    """MPが足りないカードを仮置きしている間は確定できないことを検証します。"""
    doll = "sundries/spiritual-doll"
    cost = card_feature(TURBULENCE, "mp_cost")
    mp = cost - 1

    g = board(
        p0=Side(hp=40, mp=10, hand=[FLAME]),
        p1=Side(hp=40, mp=mp, hand=[TURBULENCE, doll]),
    )
    g.rng.deck_always(FILLER)
    g.rng.bounce(success=False)

    g.attack(FLAME)

    # 精霊のぬいぐるみが手元にあるので、乱気流の仮置きそのものは合法
    g.expect_legal([TURBULENCE])
    g.select(TURBULENCE)

    g.expect_actions(confirm=False)
    g.expect_legal([doll])

    g.select(doll)
    g.expect_actions(confirm=True)

    g.confirm()
    g.expect(p1_mp=mp)


def test_the_cards_named_in_this_file_still_have_the_roles_assumed():
    """このファイルが名指ししているカードが、実在し想定どおりの種別であることを確認します。

    「反射剣が反射カードであること」のような前提が崩れると、上のテストは
    落ちずに別のことを検証し始めます。前提そのものを1箇所で押さえます。
    """
    assert card_feature(CURTAIN, "type") == "defense"
    assert card_feature(WALL, "type") == "miracle"
    assert card_feature(TURBULENCE, "type") == "miracle"
    assert card_feature(REFLECTION_SWORD, "reaction_type") == "reflect"
    assert card_feature("weapons/bouncing-sword", "reaction_type") == "bounce"
    assert card_feature("weapons/sky-harpoon", "reaction_type") == "bounce"
    assert card_feature("weapons/angel-bow", "reaction_type") == "block"
    assert card_id(CURTAIN) >= 0


# ============================================================================
# 連撃 × 反射
# ============================================================================


def test_reflection_only_bounces_the_first_hit_of_a_multi_attack(board):
    """連撃の1発目を反射しても、2発目は元の向きに戻ることを検証します。

    のこぶんぶんは2回攻撃します。1発目を反射剣で返すと攻守が入れ替わり、
    撃った側がその1発を防御します。それが解決すると向きが戻り、2発目は
    改めて元の防御側が受けます。

    反射した1発も「1回ぶんの攻撃」として数えるので、連撃の残り回数は減ります。
    """
    saw = "weapons/saw-boom-boom"
    armor = "armor/leather-clothes"
    power = card_feature(saw, "attack_power")

    g = board(
        p0=Side(hp=99, mp=30, hand=[saw]),
        p1=Side(hp=99, mp=30, hand=[REFLECTION_SWORD, armor]),
    )
    g.rng.deck_always(FILLER)

    g.attack(saw)
    g.expect(phase=GamePhase.PHASE_DEFENSE, actor=1, attacker=0, defender=1)
    assert g.state.remaining_attacks == 2, "のこぶんぶんは2回攻撃する前提"

    # 1発目を反射: 攻守が入れ替わる（残り回数はまだ減らない）
    g.defend(REFLECTION_SWORD)
    g.expect(phase=GamePhase.PHASE_DEFENSE, actor=0, attacker=1, defender=0)
    assert g.state.remaining_attacks == 2

    # 反射された1発を撃った側が受ける -> 向きが戻り、残り1回になる
    g.take_hit()
    g.expect(phase=GamePhase.PHASE_DEFENSE, actor=1, attacker=0, defender=1, p0_hp=99 - power)
    assert g.state.remaining_attacks == 1

    # 2発目は元の防御側が受ける
    g.defend(armor)
    damage = max(0, power - card_feature(armor, "defense_power"))
    g.expect(phase=GamePhase.PHASE_MAIN, p0_hp=99 - power, p1_hp=99 - damage)
    assert g.state.remaining_attacks == 0


def test_a_dead_player_can_only_confirm_in_a_defense_phase(board):
    """死亡したプレイヤーは、防御フェイズで確定しか選べないことを検証します。

    指輪の反撃は予約した側・受ける側の生死によらず解決されるため、既に死んでいる
    プレイヤーへ反撃が飛ぶことがあります。その場合、防具もスーパーミラーも出せず、
    確定を押すだけになります。

    邪神の大剣（相打ち）でちょうど死ぬHPにしておき、防御側の土星の指輪の反撃が
    死んだ攻撃側へ飛ぶ局面を作ります。
    """
    evil = "weapons/evil-broadsword"   # 相打ち: 与えたダメージを自分も受ける
    saturn = "armor/saturn-ring"       # 土属性・反撃で被ダメージ×2
    wood_armor = "armor/laurel-wreath"  # 木属性なので土属性の反撃に出せる
    power = card_feature(evil, "attack_power")

    g = board(
        p0=Side(hp=power, mp=30, hand=[evil, wood_armor, SUPER_MIRROR]),
        p1=Side(hp=99, mp=30, hand=[saturn]),
    )
    g.rng.deck_always(FILLER)

    g.attack(evil)
    g.defend(saturn)

    # 相打ちで P0 が死亡し、そのまま指輪の反撃の防御フェイズに入る
    g.expect(phase=GamePhase.PHASE_DEFENSE, actor=0, p0_hp=0, is_done=False)
    assert g.state.pending_attack_element == element_of(saturn), (
        "土星の指輪の反撃が飛んでいる前提"
    )

    # 属性も使用状況も問題ないカードを持っているが、死んでいるので出せない
    assert g.state.get_is_used(0, 1) is False and g.state.get_is_used(0, 2) is False
    g.expect_illegal([wood_armor, SUPER_MIRROR])

    actions = g.legal_actions()
    assert actions[ActionType.ACTION_CONFIRM] is True, "確定だけは選べるべきです"
    assert sum(actions) == 1, "確定以外の選択肢があってはいけません"


# ============================================================================
# ＜壁＞・＜乱気流＞: 防御専用の奇跡リアクション
# ============================================================================

SPIRIT_DOLL = "sundries/spiritual-doll"   # 精霊系（雑貨）


@pytest.mark.parametrize(
    ("reaction", "attack", "phase", "legal"),
    [
        (WALL, "weapons/punch", GamePhase.PHASE_DEFENSE, True),
        (WALL, "weapons/torch", GamePhase.PHASE_DEFENSE, False),
        (WALL, FLAME, GamePhase.PHASE_MIRACLE_DEFENSE, False),
        (TURBULENCE, FLAME, GamePhase.PHASE_MIRACLE_DEFENSE, True),
        (TURBULENCE, "miracles/meteor", GamePhase.PHASE_MIRACLE_DEFENSE, True),
        (TURBULENCE, "weapons/punch", GamePhase.PHASE_DEFENSE, False),
    ],
    ids=[
        "壁は無属性の武器攻撃に出せる",
        "壁は有属性の武器攻撃には出せない",
        "壁は奇跡攻撃には出せない",
        "乱気流は火属性の奇跡に出せる",
        "乱気流は光属性の奇跡にも出せる",
        "乱気流は武器攻撃には出せない",
    ],
)
def test_what_wall_and_turbulence_can_be_played_against(board, reaction, attack, phase, legal):
    """＜壁＞は無属性の武器攻撃だけ、＜乱気流＞は任意の奇跡だけに出せることを検証します。"""
    g = board(
        p0=Side(hp=99, mp=99, hand=[attack]),
        p1=Side(hp=99, mp=99, hand=[reaction]),
    )
    g.rng.deck_always(FILLER)
    g.rng.hits(always=True, optional=True)

    g.attack(attack)
    g.expect(phase=phase)

    if legal:
        g.expect_legal([reaction])
    else:
        g.expect_illegal([reaction])


def _reactions_for(phase_timing: str) -> list[str]:
    """指定の防御フェイズで使えるリアクションカードをマスタから集めます。"""
    return [
        c["id_str"]
        for c in all_cards()
        if c.get("reaction_type")
        and c["id_str"] != CURTAIN
        and phase_timing in (c.get("usage_timing") or [])
    ]


@pytest.mark.parametrize(
    "reaction", _reactions_for("atk_defence_phase"), ids=lambda r: r
)
def test_every_physical_reaction_can_follow_the_rainbow_curtain(board, reaction):
    """物理防御のリアクションが、すべて虹のカーテンの後に置けることを検証します。

    リアクションは本来1枚目にしか置けませんが、虹のカーテンの直後だけは
    例外的に許されます。カードを名指しせずマスタから集めるので、
    リアクションカードが増えても自動で検証対象に入ります。
    """
    attack = "weapons/torch"  # 火属性なので、カーテンなしでは属性が合わない
    g = board(
        p0=Side(hp=99, mp=99, hand=[attack]),
        p1=Side(hp=99, mp=99, hand=[CURTAIN, reaction]),
    )
    g.rng.deck_always(FILLER)
    g.rng.hits(always=True, optional=True)

    g.attack(attack)
    g.expect(phase=GamePhase.PHASE_DEFENSE)

    g.select(CURTAIN)
    g.expect_legal([reaction])


@pytest.mark.parametrize(
    "reaction", _reactions_for("miracle_defence_phase"), ids=lambda r: r
)
def test_every_miracle_reaction_can_follow_the_rainbow_curtain(board, reaction):
    """奇跡防御のリアクションが、すべて虹のカーテンの後に置けることを検証します。

    以前この例外は物理防御にしか適用されておらず、虹のカーテンの後に
    ＜乱気流＞などを置けませんでした。
    """
    g = board(
        p0=Side(hp=99, mp=99, hand=[FLAME]),
        p1=Side(hp=99, mp=99, hand=[CURTAIN, reaction]),
    )
    g.rng.deck_always(FILLER)
    g.rng.hits(always=True, optional=True)

    g.attack(FLAME)
    g.expect(phase=GamePhase.PHASE_MIRACLE_DEFENSE)

    g.select(CURTAIN)
    g.expect_legal([reaction])


@pytest.mark.parametrize(
    ("reaction", "attack", "fired"),
    [
        (TURBULENCE, FLAME, EventType.BOUNCE_ATTACK),
        ("armor/angel-armor", FLAME, EventType.BLOCK_ATTACK),
        ("armor/moonlight-armor", FLAME, EventType.REFLECT_DAMAGE),
        (SUPER_MIRROR, FLAME, EventType.REFLECT_DAMAGE),
        (WALL, "weapons/torch", EventType.BLOCK_ATTACK),
        (REFLECTION_SWORD, "weapons/torch", EventType.REFLECT_DAMAGE),
    ],
    ids=["乱気流で弾く", "エンゼルで阻止", "月光ではね返す", "ミラーではね返す",
         "壁で阻止", "反射剣ではね返す"],
)
def test_a_reaction_after_the_curtain_actually_fires(board, reaction, attack, fired):
    """虹のカーテンの後に置いたリアクションが、実際に発動することを検証します。

    合法手として置けるだけでは不十分で、2枚目に置いた場合にリアクション効果が
    発動せず防御力だけが乗る、という状態になっていないかを見ます。
    """
    g = board(
        p0=Side(hp=99, mp=99, hand=[attack]),
        p1=Side(hp=99, mp=99, hand=[CURTAIN, reaction]),
    )
    g.rng.deck_always(FILLER)
    g.rng.hits(always=True, optional=True)
    g.rng.bounce(success=True, optional=True)

    g.attack(attack)
    g.select(CURTAIN)
    g.defend(reaction)

    assert any(e.type == fired for e in g.event_log()), (
        f"{reaction} のリアクション（{fired.name}）が発動していません"
    )


@pytest.mark.parametrize(
    ("reaction", "attack"),
    [(WALL, "weapons/punch"), (TURBULENCE, FLAME)],
    ids=["＜壁＞の後", "＜乱気流＞の後"],
)
def test_a_spiritual_card_can_follow_wall_and_turbulence(board, reaction, attack):
    """＜壁＞＜乱気流＞の直後に精霊系を重ねて消費MPを0にできることを検証します。"""
    mp_cost = card_feature(reaction, "mp_cost")
    assert mp_cost > 0, "消費MPが0ならこの検証は意味がありません"

    g = board(
        p0=Side(hp=99, mp=99, hand=[attack]),
        p1=Side(hp=99, mp=mp_cost - 1, hand=[reaction, SPIRIT_DOLL]),
    )
    g.rng.deck_always(FILLER)
    g.rng.hits(always=True, optional=True)

    g.attack(attack)
    g.select(reaction)
    g.expect_legal([SPIRIT_DOLL])

    g.defend(SPIRIT_DOLL)
    g.expect(p1_mp=mp_cost - 1)  # 精霊系で相殺されるのでMPは減らない


# ============================================================================
# リアクションで使ったカードの防御力は乗らない
# ============================================================================


def _bouncing_armors_with_defense() -> list[int]:
    """弾き（bounce）を持ち、かつ防御力も持つ防具を集めます。

    「弾きに失敗して被弾する」経路を持つのはこの組み合わせだけなので、
    防御力が差し引かれるかどうかが実際の被弾量に出ます。
    """
    return [
        c
        for c in cards_where(type="defense", reaction_type="bounce")
        if card_feature(c, "defense_power", 0) > 0
    ]


BOUNCING_ARMORS = _bouncing_armors_with_defense()


@pytest.mark.parametrize("armor", BOUNCING_ARMORS, ids=[card_name(c) for c in BOUNCING_ARMORS])
def test_a_failed_bounce_does_not_apply_the_reaction_card_defense(board, armor):
    """弾きに失敗したとき、そのカードの防御力が差し引かれないことを検証します。

    リアクション効果を使ったカードは「その効果を使った」ぶん防御力を持ち込みません。
    以前は通常の防具と同じように守が合算されており、スカイアーマー（守9）で
    ＜滝＞（攻25）を弾き損ねても16ダメージしか受けませんでした。正しくは25です。

    防具として使った場合（＝リアクションが発動しない置き方）と対比することで、
    「常に0になった」わけではないことも同時に示します。
    """
    attack = "miracles/waterfall"  # 水属性 ATK25。スカイ系は無属性なので奇跡に出せる
    power = card_feature(attack, "attack_power")
    guard = card_feature(armor, "defense_power")
    assert power > guard, "防御力で受けきれる組み合わせでは差が見えない"

    g = board(
        p0=Side(hp=99, mp=99, hand=[attack]),
        p1=Side(hp=99, mp=99, hand=[armor]),
    )
    g.rng.deck_always(FILLER)
    g.rng.bounce(success=False)

    g.attack(attack)
    g.defend(armor)

    g.expect(p1_hp=99 - power)
    assert any(
        e.type == EventType.CONFIRM_DEFENSE and e.value == 0 for e in g.event_log()
    ), "確定時の防御力も0として記録されるべきです"


@pytest.mark.parametrize("armor", BOUNCING_ARMORS, ids=[card_name(c) for c in BOUNCING_ARMORS])
def test_the_same_armor_still_guards_when_its_reaction_does_not_fire(board, armor):
    """同じ防具でも、リアクションが発動しない置き方なら防御力が乗ることを検証します。

    リアクションが発動するのは仮置きの先頭（虹のカーテンは何枚並んでいてもよい）に
    置いた場合だけです。一般防具を挟めば、スカイ系も普通の無属性防具として働きます。
    上のテストと対で、「リアクションを使ったから0になる」ことを示します。

    攻撃は**奇跡**にします。スカイ系は物理防御では `is_active_reaction_card` が
    false になるため、物理攻撃で試すと「位置に関係なく発動しない」ことしか
    確認できず、対照になりません（実際、以前このテストは物理攻撃で書かれており、
    位置の規則が解決側で守られていない不具合を通してしまっていました）。
    """
    attack = "miracles/flame"        # 火属性 ATK10
    first = CURTAIN                  # 無属性化して一般防具を解禁する
    second = "armor/leather-cap"     # 無属性の一般防具（これでリアクション位置を潰す）
    power = card_feature(attack, "attack_power")
    guard = (card_feature(first, "defense_power", 0)
             + card_feature(second, "defense_power", 0)
             + card_feature(armor, "defense_power"))

    g = board(
        p0=Side(hp=99, mp=99, hand=[attack]),
        p1=Side(hp=99, mp=99, hand=[first, second, armor]),
    )
    g.rng.deck_always(FILLER)

    g.attack(attack)
    g.select(first)
    g.select(second)
    assert card_name(card_id(armor)) in g.legal_cards(), (
        "一般防具としてなら置けるはずです（この前提が崩れたら対照になりません）"
    )
    g.defend(armor)

    # 弾き判定は行われない（指示すると空振りになるので、ここでは指示しない）
    assert not any(e.type == EventType.BOUNCE_ATTACK for e in g.event_log()), (
        "一般防具を挟んだ後に置いたリアクションカードの効果が発動しています"
    )
    g.expect(p1_hp=99 - max(0, power - guard), phase=GamePhase.PHASE_MAIN)




# ============================================================================
# リアクションカード自身のステータスが跳ね返る攻撃に混ざらないこと
# ============================================================================

PHYSICAL_ATTACK = "weapons/dragon-claws"   # 無属性 ATK15
MIRACLE_ATTACK = "miracles/waterfall"      # 水属性 ATK25

_ALL_REACTIONS = sorted(
    set(_reactions_for("atk_defence_phase")) | set(_reactions_for("miracle_defence_phase"))
)

FIRED_EVENT = {
    "block": EventType.BLOCK_ATTACK,
    "reflect": EventType.REFLECT_DAMAGE,
    "bounce": EventType.BOUNCE_ATTACK,
}


def _defend_with_reaction(board, reaction, attack):
    """1枚のリアクションで防御する。発動しなかった場合は None を返します。

    同じカードでも、物理攻撃と奇跡攻撃のどちらでリアクションが発動するかは
    カードによって違います（スカイ系は物理には出せても効果は発動せず、
    ただの無属性防具として働きます）。どちらで発動するかをテスト側で決め打ちすると
    実装の規則をテストに複製することになるので、両方試して発動した方を使います。
    """
    g = board(
        p0=Side(hp=99, mp=99, hand=[attack]),
        p1=Side(hp=99, mp=99, hand=[reaction]),
    )
    g.rng.deck_always(FILLER)
    g.rng.bounce(success=True, optional=True)  # 弾きは成功側に固定（失敗すると返らない）

    g.attack(attack)
    if card_name(card_id(reaction)) not in g.legal_cards():
        return None
    before = (g.state.pending_attack_power, g.state.pending_attack_element)
    g.defend(reaction)

    fired = FIRED_EVENT[card_feature(reaction, "reaction_type")]
    if not any(e.type == fired for e in g.event_log()):
        return None
    return g, before


@pytest.mark.parametrize("reaction", _ALL_REACTIONS, ids=lambda r: r)
def test_a_reaction_does_not_change_the_attack_it_sends_back(board, reaction):
    """はね返した・弾いた攻撃の威力と属性が、元のまま変わらないことを検証します。

    リアクションカードには攻撃力を持つもの（反射剣 攻10、乱弾武剣 攻5、
    エンゼルアクス 攻15 など）と防御力を持つもの（スカイアーマー 守9 など）が
    あります。これらが跳ね返る攻撃に混ざると、返された側が受ける威力が変わって
    しまいます。阻止の場合は攻撃そのものが消えるので、誰も被弾しないことを見ます。

    カードを名指しせずマスタから全件集めるので、リアクションカードが増えても
    自動で検証対象に入ります。
    """
    result = None
    for attack in (PHYSICAL_ATTACK, MIRACLE_ATTACK):
        result = _defend_with_reaction(board, reaction, attack)
        if result is not None:
            break
    assert result is not None, (
        f"{reaction} のリアクションが物理・奇跡のどちらでも発動しませんでした"
    )
    g, (power_before, element_before) = result

    if card_feature(reaction, "reaction_type") == "block":
        g.expect(p0_hp=99, p1_hp=99)
        return

    # 攻守が入れ替わり、元の攻撃者が同じ攻撃を受ける側に立つ
    g.expect(attacker=1, defender=0, actor=0, p0_hp=99, p1_hp=99)
    assert g.state.pending_attack_power == power_before, (
        f"跳ね返った攻撃の威力が {power_before} から {g.state.pending_attack_power}"
        f" に変わっています（{reaction} 自身の"
        f"攻撃力{card_feature(reaction, 'attack_power', 0)}・"
        f"防御力{card_feature(reaction, 'defense_power', 0)}が混ざっていないか）"
    )
    assert g.state.pending_attack_element == element_before, "属性が変わっています"


REFLECT_CARDS = [r for r in _ALL_REACTIONS if card_feature(r, "reaction_type") == "reflect"]


@pytest.mark.parametrize("reaction", REFLECT_CARDS, ids=lambda r: r)
def test_reflection_never_rolls_and_always_succeeds(board, reaction):
    """はね返す（reflect）が判定なしで必ず成功することを検証します。

    50%の判定を持つのは弾く（bounce）だけです。反射に判定が混ざると
    「返せるはずが返せない」局面が生まれます。
    """
    result = None
    for attack in (PHYSICAL_ATTACK, MIRACLE_ATTACK):
        result = _defend_with_reaction(board, reaction, attack)
        if result is not None:
            break
    assert result is not None, f"{reaction} の反射が発動しませんでした"
    g, _ = result

    assert g.rng.consumed(RollKind.BOUNCE) == 0, (
        "反射で弾き判定が行われています（反射は100%成功のはず）"
    )
    g.expect(attacker=1, defender=0, actor=0, p1_hp=99)


# ============================================================================
# 精霊系として使ったカードの防御力は乗らない
# ============================================================================


def _spiritual_armors() -> list[int]:
    """精霊系のうち、防御力を持つもの（＝防御側で守が乗りうるもの）。"""
    return [
        c
        for c in godfield_core.get_spiritual_zero_mp_cards()
        if card_feature(c, "defense_power", 0) > 0
    ]


SPIRITUAL_ARMORS = _spiritual_armors()


@pytest.mark.parametrize(
    "spirit", SPIRITUAL_ARMORS, ids=[card_name(c) for c in SPIRITUAL_ARMORS]
)
def test_a_spiritual_card_used_as_spiritual_adds_no_defense(board, spirit):
    """＜乱気流＞の後ろに置いた精霊系の防御力が乗らないことを検証します。

    リアクション奇跡の後ろに置ける精霊系は、その消費MPを0にするためのものであって
    防具として出したわけではありません。攻撃側では「精霊系を奇跡に重ねた場合は
    攻撃力も属性も持ち込まない」と除外しているのに、防御側には同じ除外が無く、
    ＜乱気流＞＋精霊の帯（守12）で ＜滝＞（攻25）を弾き損ねると被弾が13でした。
    正しくは25です。
    """
    attack = "miracles/waterfall"
    power = card_feature(attack, "attack_power")
    guard = card_feature(spirit, "defense_power")
    assert guard > 0 and power > guard, "守が乗ったかどうかを被弾量で見分けられる前提"

    g = board(
        p0=Side(hp=99, mp=99, hand=[attack]),
        p1=Side(hp=99, mp=99, hand=[TURBULENCE, spirit]),
    )
    g.rng.deck_always(FILLER)
    g.rng.bounce(success=False)

    g.attack(attack)
    g.select(TURBULENCE)
    g.expect_legal([spirit])
    g.defend(spirit)

    g.expect(p1_hp=99 - power)


@pytest.mark.parametrize(
    "spirit", SPIRITUAL_ARMORS, ids=[card_name(c) for c in SPIRITUAL_ARMORS]
)
def test_a_spiritual_card_used_as_plain_armor_still_guards(board, spirit):
    """精霊系を普通の防具として使った場合は、防御力が乗ることを検証します。

    1枚目に単独で置く場合と、虹のカーテンの後ろに置く場合が該当します。
    上のテストと対で、「精霊系の守が常に0になった」わけではないことを示します。
    """
    attack = "weapons/dragon-claws"  # 無属性なので精霊系（無属性）を単独で出せる
    power = card_feature(attack, "attack_power")
    guard = card_feature(spirit, "defense_power")

    g = board(
        p0=Side(hp=99, mp=99, hand=[attack]),
        p1=Side(hp=99, mp=99, hand=[spirit]),
    )
    g.rng.deck_always(FILLER)

    g.attack(attack)
    g.defend(spirit)

    g.expect(p1_hp=99 - max(0, power - guard))


def test_spiritual_card_list_is_fully_covered():
    """C++ の精霊系カード一覧が、テストでカバーされていることを確認します。

    精霊系が追加されたときに、検証が無いまま通り過ぎるのを防ぎます。
    防御力を持たないもの（精霊の杖・精霊のぬいぐるみ）は防御側の検証対象外ですが、
    攻撃側は tests/core/test_combat_flow.py が見ています。
    """
    all_spirits = set(godfield_core.get_spiritual_zero_mp_cards())
    with_defense = set(SPIRITUAL_ARMORS)
    without_defense = all_spirits - with_defense
    assert with_defense, "防御力を持つ精霊系が1枚もありません"
    assert all(card_feature(c, "defense_power", 0) == 0 for c in without_defense), (
        "防御力を持つ精霊系が検証対象から漏れています: "
        + ", ".join(card_name(c) for c in sorted(without_defense))
    )

# ============================================================================
# 虹のカーテンの重ねがけとリアクションの位置規則
# ============================================================================

_MIRACLE_REACTION_CASES = [
    ("armor/sky-armor", EventType.BOUNCE_ATTACK),
    ("armor/moonlight-armor", EventType.REFLECT_DAMAGE),
    ("armor/angel-armor", EventType.BLOCK_ATTACK),
]


@pytest.mark.parametrize("num_curtains", [1, 2, 3], ids=["カーテン1枚", "カーテン2枚", "カーテン3枚"])
@pytest.mark.parametrize(
    ("reaction", "fired"), _MIRACLE_REACTION_CASES, ids=lambda v: getattr(v, "name", v)
)
def test_a_reaction_still_fires_after_any_number_of_curtains(board, num_curtains, reaction, fired):
    """虹のカーテンを何枚重ねた後でも、リアクションが置けて発動することを検証します。

    カーテンは属性を消すだけなので、何枚並んでいてもその後ろは「先頭」のままです。
    以前は例外が「カーテンちょうど1枚の直後」に限定されており、2枚重ねると
    リアクションを置けませんでした。
    """
    attack = "miracles/flame"  # 火属性なので、カーテンが無いと一般防具は出せない
    g = board(
        p0=Side(hp=99, mp=99, hand=[attack]),
        p1=Side(hp=99, mp=99, hand=[CURTAIN] * num_curtains + [reaction]),
    )
    g.rng.deck_always(FILLER)
    g.rng.bounce(success=True, optional=True)

    g.attack(attack)
    for slot in range(num_curtains):
        g.select_slots(slot)
    assert g.state.get_num_staged_cards(1) == num_curtains

    g.expect_legal([reaction])
    g.defend(reaction)

    assert any(e.type == fired for e in g.event_log()), (
        f"カーテン{num_curtains}枚の後に置いた {reaction} が発動していません"
    )
    # 無属性化されたうえで解決されている
    assert g.state.pending_attack_element == Element.ELEM_NONE


@pytest.mark.parametrize(
    ("reaction", "fired"), _MIRACLE_REACTION_CASES, ids=lambda v: getattr(v, "name", v)
)
def test_a_reaction_after_a_plain_armor_does_not_fire(board, reaction, fired):
    """一般防具を挟んだ後に置いたリアクションカードの効果が発動しないことを検証します。

    防御力を持つリアクションカードは「普通の防具」としてなら後ろにも置けます。
    そのときは効果を持たず、防御力だけが合算されなければいけません。

    以前は合法手の判定だけが位置を見ており、解決側は見ていませんでした。そのため
    `虹のカーテン ＋ 一般防具 ＋ スカイアーマー` と置くと弾きが発動し、
    本来ダメージ0で終わるはずの局面で攻守が入れ替わっていました。
    """
    attack = "miracles/flame"
    plain = "armor/leather-cap"   # 無属性の一般防具
    power = card_feature(attack, "attack_power")
    guard = card_feature(plain, "defense_power") + card_feature(reaction, "defense_power")
    assert card_feature(CURTAIN, "defense_power", 0) == 0

    g = board(
        p0=Side(hp=99, mp=99, hand=[attack]),
        p1=Side(hp=99, mp=99, hand=[CURTAIN, plain, reaction]),
    )
    g.rng.deck_always(FILLER)

    g.attack(attack)
    g.select(CURTAIN)
    g.select(plain)
    assert card_name(card_id(reaction)) in g.legal_cards(), (
        "一般防具としてなら置けるはずです"
    )
    g.defend(reaction)

    assert not any(e.type == fired for e in g.event_log()), (
        f"一般防具を挟んだ後の {reaction} の効果が発動しています"
    )
    # 攻守は入れ替わらず、防御力が合算されてターンが終わる
    g.expect(p1_hp=99 - max(0, power - guard), p0_hp=99, phase=GamePhase.PHASE_MAIN)


@pytest.mark.parametrize(
    ("reaction", "fired"), _MIRACLE_REACTION_CASES, ids=lambda v: getattr(v, "name", v)
)
def test_more_armor_can_follow_a_reaction_card_placed_as_plain_armor(board, reaction, fired):
    """普通の防具として置いたリアクションカードの後にも、防具を重ねられることを検証します。

    リアクションとして置いた場合は「精霊系しか続けられない」制限がかかりますが、
    一般防具として置いたのなら普通の防具と同じ扱いでなければ辻褄が合いません。
    """
    attack = "miracles/flame"
    plain = "armor/leather-cap"
    extra = "armor/wood-shield"

    g = board(
        p0=Side(hp=99, mp=99, hand=[attack]),
        p1=Side(hp=99, mp=99, hand=[CURTAIN, plain, reaction, extra]),
    )
    g.rng.deck_always(FILLER)

    g.attack(attack)
    g.select(CURTAIN)
    g.select(plain)
    g.select(reaction)

    g.expect_legal([extra])


@pytest.mark.parametrize("num_curtains", [0, 1, 2], ids=["1枚目に置く", "カーテン1枚の後", "カーテン2枚の後"])
@pytest.mark.parametrize(
    ("reaction", "fired"), _MIRACLE_REACTION_CASES, ids=lambda v: getattr(v, "name", v)
)
def test_nothing_can_follow_a_reaction_card_used_as_a_reaction(board, num_curtains, reaction, fired):
    """リアクションとして置いた後は、確定しか選べなくなることを検証します。

    仮置きの先頭に置いた時点で「リアクションカードの使用」と確定するので、そこに
    一般防具を重ねることはできません。防具として使いたいなら先に一般防具を
    置く必要があります（そちらは上のテストが見ています）。

    1枚目に置いた単体奇跡にプラス攻撃を重ねられないのと同じ構図です。
    `プラス武器 ＋ ＜火の玉＞` は合法でも `＜火の玉＞ ＋ プラス武器` は非合法、
    という順序依存がここにもあります。
    """
    attack = "miracles/flame"
    plain = "armor/leather-cap"   # 無属性なのでカーテンさえあれば置ける一般防具

    g = board(
        p0=Side(hp=99, mp=99, hand=[attack]),
        p1=Side(hp=99, mp=99, hand=[CURTAIN] * num_curtains + [reaction, plain]),
    )
    g.rng.deck_always(FILLER)

    g.attack(attack)
    for slot in range(num_curtains):
        g.select_slots(slot)
    if num_curtains:
        # カーテンだけを置いた時点では、まだ一般防具を重ねられる
        g.expect_legal([plain])

    g.select(reaction)

    assert g.legal_cards() == [], (
        f"リアクションとして置いた後は確定のみのはずですが {g.legal_cards()} が置けます"
    )
    assert g.legal_actions()[int(ActionType.ACTION_CONFIRM)], "確定すら選べません"


@pytest.mark.parametrize(
    ("plays", "why"),
    [
        (["armor/sky-armor"], "リアクションとして置いた（守は乗らない）"),
        (["armor/moonlight-armor"], "リアクションとして置いた（守は乗らない）"),
        ([TURBULENCE, "armor/spiritual-sash"], "精霊系として置いた（守は乗らない）"),
        ([CURTAIN, "armor/leather-cap", "armor/sky-armor"], "一般防具として置いた（守が乗る）"),
        ([CURTAIN, "armor/leather-cap"], "普通に重ねた（守が乗る）"),
    ],
    ids=["スカイアーマー単独", "月光のよろい単独", "乱気流+精霊の帯",
         "カーテン+一般防具+スカイアーマー", "カーテン+一般防具"],
)
def test_observed_defense_power_matches_the_defense_that_actually_applies(board, plays, why):
    """観測に載る防御力が、実際に効く防御力と一致することを検証します。

    `pending_defense_power` はエージェントが「今どれだけ防げているか」を見るための
    値です。ダメージ計算と別々に集計していたため、リアクションカードを置いたときに
    観測だけが守9を表示し、実際には0という食い違いが起きていました。
    エージェントから見ると「守9あるはずが攻撃力そのまま通った」ことになります。
    """
    attack = "miracles/waterfall"   # 水 ATK25
    g = board(
        p0=Side(hp=99, mp=99, hand=[attack]),
        p1=Side(hp=99, mp=99, hand=list(plays)),
    )
    g.rng.deck_always(FILLER)
    g.rng.bounce(success=False, optional=True)

    g.attack(attack)
    for c in plays:
        assert card_name(card_id(c)) in g.legal_cards(), f"{c} を置けません"
        g.select(c)

    observed = g.state.pending_defense_power
    g.confirm()

    applied = next(
        (int(e.value) for e in g.event_log() if e.type == EventType.CONFIRM_DEFENSE), None
    )
    assert applied is not None, "CONFIRM_DEFENSE が記録されていません"
    assert observed == applied, (
        f"観測の防御力 {observed} と実際に効いた防御力 {applied} が食い違っています"
    )
