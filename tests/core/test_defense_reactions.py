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
from godfield_core import ActionType, CurseType, Element, GamePhase, PhenomenonType
from tests.core.dsl import Side, card_feature, card_id, cards_of_element, element_of

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


def test_rainbow_curtain_can_only_be_the_first_card(board):
    """虹のカーテンを2枚目以降に重ねられないことを検証します。"""
    torch = "weapons/torch"
    g = board(
        p0=Side(hp=40, mp=10, hand=[torch]),
        p1=Side(hp=40, mp=10, hand=[CURTAIN, CURTAIN]),
    )
    g.rng.deck_always(FILLER)

    g.attack(torch)
    g.select_slots(0)  # 1枚目のカーテン

    actions = g.legal_actions()
    assert actions[ActionType.ACTION_SELECT_HAND_1] is False, (
        "2枚目の虹のカーテンは重ねられないべきです"
    )


def test_rainbow_curtain_locks_out_reactions_but_unlocks_plain_armor(board):
    """奇跡攻撃に虹のカーテンを置くと、リアクションは封じられる代わりに一般防具が使えるようになることを検証します。

    無属性化によって「属性が合わないので出せなかった防具」が解禁される一方、
    ＜乱気流＞のようなリアクションはカーテンの後には重ねられません。
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

    # 無属性化で一般防具が解禁される一方、リアクションは重ねられなくなる
    g.expect_legal([armor])
    g.expect_illegal([TURBULENCE])

    g.defend(armor)

    damage = card_feature(FLAME, "attack_power") - card_feature(armor, "defense_power")
    g.expect(p1_hp=40 - damage, phase=GamePhase.PHASE_MAIN)


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
    # スカイアーマーは弾きを持つ。ここで見たいのは「2枚目として出せること」と
    # その防御力が乗ることなので、弾きは起こさない側に固定する
    # （固定しないと50%で攻守が入れ替わり、被弾の検証が成立しない）。
    g.rng.bounce(success=False)

    g.attack(meteor)
    g.expect(phase=GamePhase.PHASE_MIRACLE_DEFENSE)

    g.select(CURTAIN)
    g.expect_legal([sky_armor])

    g.defend(sky_armor)

    guard = card_feature(CURTAIN, "defense_power") + card_feature(sky_armor, "defense_power")
    damage = max(0, card_feature(meteor, "attack_power") - guard)
    g.expect(p1_hp=40 - damage)


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
