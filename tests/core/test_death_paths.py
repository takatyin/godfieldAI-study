"""HPが0になる経路ごとの、守護神の退散判定と太陽のお守りによる復活の扱い。

ゲームには「HPを0にする」処理が複数あり、それぞれ扱いが違います。

- **闇属性による即死**: 攻撃のダメージによる退散判定は行われますが、
  そのあと防御力を貫通してHPを0にする部分では退散判定を行いません。
- **天国病の発作による死**: 病気による死なので退散判定を行い、
  太陽のお守りによる復活も発生します。
- **竜巻**: ダメージではなくHPの強制上書きなので退散判定は行わず、
  既に死亡しているプレイヤーを蘇生させることもありません。

これらは実装上どれも「HPに0を代入する」という同じ形をしているため、区別が
コードから読み取りにくく、実際に取りこぼしが発生していました。ここで固定します。

【注意】このファイルが固定しているのは **実機での確認が取れていない仮定** です。
詳細と、実機仕様が判明した場合に見直すべき点は docs/rules.md の 8.1 節を参照して
ください。挙動を変更する際、ここのテストが落ちることは「壊した」ことの証明には
なりません。
"""

import pytest

from godfield_core import EventType, GuardianType, PhenomenonType, RollKind, SicknessType
from tests.core.dsl import Side, card_feature

MARS = int(GuardianType.MARS)
NONE = int(GuardianType.NONE)

FILLER = "armor/wood-shield"
DARKNESS = "miracles/darkness"      # ＜闇＞: 唯一の闇属性攻撃
CURTAIN = "armor/rainbow-curtain"   # 闇属性の即死を防ぐ
GALE_SWORD = "weapons/gale-sword"   # 疾風剣: ダメージを与えた対象を風邪状態にする
AMULET = "sundries/sun-amulet"
FATE = "sundries/string-of-fate"


# ============================================================================
# 闇属性による即死
# ============================================================================


@pytest.mark.parametrize("leaves", [True, False], ids=["離脱する", "残留する"])
def test_darkness_instant_death_rolls_only_for_the_damage(board, leaves):
    """闇属性で即死したとき、守護神の退散判定がダメージ分の1回だけであることを検証します。

    ＜闇＞のダメージでHPが減った時点で1回判定し、そのあとHPを0にする即死部分では
    追加の判定を行いません。
    """
    power = card_feature(DARKNESS, "attack_power")
    g = board(
        p0=Side(hp=99, mp=99, hand=[DARKNESS]),
        p1=Side(hp=99, mp=10, guardian=MARS, hand=[FILLER]),
    )
    g.rng.deck_always(FILLER)
    g.rng.guardian_leave(leaves=leaves)

    g.attack(DARKNESS)
    g.take_hit()

    assert g.rng.consumed(RollKind.GUARDIAN_LEAVE) == 1, (
        f"ダメージ{power}による判定1回のみのはずですが"
        f" {g.rng.consumed(RollKind.GUARDIAN_LEAVE)} 回行われました"
    )
    g.expect(p1_hp=0, p1_guardian=NONE if leaves else MARS, is_done=True)


def test_darkness_instant_death_is_recorded_as_an_event(board):
    """闇属性の即死が、ダメージとは別のイベントとして履歴に残ることを検証します。

    ダメージ量（防御力を引いた後の値）と実際のHP減少量は一致しないため、
    TAKE_DAMAGE だけでは「なぜHPが0になったか」を履歴から復元できません。
    """
    power = card_feature(DARKNESS, "attack_power")
    g = board(
        p0=Side(hp=99, mp=99, hand=[DARKNESS]),
        p1=Side(hp=99, mp=10, hand=[FILLER]),
    )
    g.rng.deck_always(FILLER)

    g.attack(DARKNESS)
    g.take_hit()

    log = g.event_log()
    kinds = [(e.type, e.value) for e in log]
    assert (EventType.TAKE_DAMAGE, float(power)) in kinds, (
        f"防御力を引いた後のダメージ{power}が記録されるべきです: {log}"
    )
    assert any(t == EventType.INSTANT_DEATH for t, _ in kinds), (
        f"闇属性の即死が記録されるべきです: {log}"
    )
    g.expect(p1_hp=0)


def test_rainbow_curtain_prevents_the_darkness_instant_death(board):
    """虹のカーテンがあれば闇属性でも即死せず、ダメージだけが入ることを検証します。

    即死イベントが出ないことも併せて確認し、上のテストが「常にINSTANT_DEATHが出る」
    だけを見ていないことを保証します。
    """
    power = card_feature(DARKNESS, "attack_power")
    g = board(
        p0=Side(hp=99, mp=99, hand=[DARKNESS]),
        p1=Side(hp=99, mp=10, hand=[CURTAIN]),
    )
    g.rng.deck_always(FILLER)

    g.attack(DARKNESS)
    g.defend(CURTAIN)

    assert not any(e.type == EventType.INSTANT_DEATH for e in g.event_log())
    g.expect(p1_hp=99 - power, is_done=False)


@pytest.mark.parametrize("leaves", [True, False], ids=["離脱する", "残留する"])
def test_darkness_self_attack_rolls_only_for_the_damage(board, leaves):
    """自分に闇属性を撃った場合も、退散判定がダメージ分の1回だけであることを検証します。

    防御側の経路（execute_standard_defense）と自滅の経路は別々に書かれているため、
    片方だけ扱いがずれる余地があります。両方が同じ結論になることを固定します。
    """
    g = board(
        p0=Side(hp=99, mp=99, guardian=MARS, hand=[DARKNESS]),
        p1=Side(hp=99, mp=10),
    )
    g.rng.deck_always(FILLER)
    g.rng.guardian_leave(leaves=leaves)

    g.attack(DARKNESS, to_self=True)

    assert g.rng.consumed(RollKind.GUARDIAN_LEAVE) == 1
    g.expect(p0_hp=0, p0_guardian=NONE if leaves else MARS, is_done=True)


def test_darkness_self_attack_revives_with_the_sun_amulet_only_once(board):
    """自分に闇属性を撃って即死しても、太陽のお守り1枚で復活できることを検証します。

    ダメージ適用と即死のあいだで復活処理が走ってしまうと、お守りが2枚必要に
    なってしまいます（1枚しか持たせずに復活することで、それが起きないことを示します）。
    """
    revive_hp = 10  # SUN_AMULET_REVIVE_HP
    g = board(
        p0=Side(hp=99, mp=99, hand=[DARKNESS, AMULET]),
        p1=Side(hp=99, mp=10),
    )
    g.rng.deck_always(FILLER)

    g.attack(DARKNESS, to_self=True)

    g.expect(p0_hp=revive_hp, is_done=False)


# ============================================================================
# 天国病の発作による死
# ============================================================================


@pytest.mark.parametrize(
    ("sickness", "extra_rolls", "survives"),
    [
        (SicknessType.SICKNESS_HEAVEN, 1, False),  # 発作で死亡 -> 退散判定が1回増える
        (SicknessType.SICKNESS_HELL, 0, True),     # 地獄病 -> 天国病に悪化するだけ
    ],
    ids=["天国病は発作で死ぬ", "地獄病は悪化するだけ"],
)
def test_heaven_seizure_adds_its_own_guardian_leave_roll(board, sickness, extra_rolls, survives):
    """天国病の発作による死でも守護神の退散判定が行われることを検証します。

    疾風剣は命中した相手を風邪にします。相手が既に天国病だと「同等以下の病気を
    重ねられた」ことになり、発作で即死します。同じ攻撃でも地獄病相手なら悪化する
    だけなので、増えた1回の判定が発作由来であることが分かります。
    """
    power = card_feature(GALE_SWORD, "attack_power")
    g = board(
        p0=Side(hp=99, mp=10, hand=[GALE_SWORD]),
        p1=Side(hp=99, mp=10, guardian=MARS, sickness=sickness, hand=[FILLER]),
    )
    g.rng.deck_always(FILLER)
    g.rng.guardian_leave(leaves=False)  # 判定回数だけを見るため、離脱はさせない

    g.attack(GALE_SWORD)
    g.take_hit()

    assert g.rng.consumed(RollKind.GUARDIAN_LEAVE) == 1 + extra_rolls, (
        "ダメージによる判定1回に加え、発作で死亡した場合はさらに1回行われるべきです"
    )
    g.expect(p1_hp=(99 - power) if survives else 0, p1_guardian=MARS)


def test_heaven_seizure_can_make_the_guardian_leave(board):
    """天国病の発作で守護神が実際に離脱することを検証します。"""
    g = board(
        p0=Side(hp=99, mp=10, hand=[GALE_SWORD]),
        p1=Side(hp=99, mp=10, guardian=MARS,
                sickness=SicknessType.SICKNESS_HEAVEN, hand=[AMULET]),
    )
    g.rng.deck_always(FILLER)
    g.rng.guardian_leave(leaves=True)

    g.attack(GALE_SWORD)
    g.take_hit()

    g.expect(p1_guardian=NONE)


def test_heaven_seizure_revives_with_the_sun_amulet(board):
    """天国病の発作で死んでも、太陽のお守りがあれば復活することを検証します。"""
    revive_hp = 10  # SUN_AMULET_REVIVE_HP
    g = board(
        p0=Side(hp=99, mp=10, hand=[GALE_SWORD]),
        p1=Side(hp=99, mp=10, sickness=SicknessType.SICKNESS_HEAVEN, hand=[AMULET]),
    )
    g.rng.deck_always(FILLER)

    g.attack(GALE_SWORD)
    g.take_hit()

    g.expect(p1_hp=revive_hp, is_done=False)


@pytest.mark.parametrize("leaves", [True, False], ids=["離脱する", "残留する"])
def test_turn_end_heaven_seizure_rolls_for_guardian_leave(board, leaves):
    """ターン終了時の天国病悪化による発作でも、退散判定が行われることを検証します。

    こちらは病気の悪化ロールから発作に至る別経路です。
    """
    g = board(
        p0=Side(hp=99, mp=10, guardian=MARS,
                sickness=SicknessType.SICKNESS_HEAVEN, hand=[FILLER]),
        p1=Side(hp=99, mp=10),
    )
    g.rng.deck_always(FILLER)
    g.rng.sickness_worsen(True)
    g.rng.guardian_leave(leaves=leaves)

    g.pray()

    assert g.rng.consumed(RollKind.GUARDIAN_LEAVE) == 1
    g.expect(p0_hp=0, p0_guardian=NONE if leaves else MARS, is_done=True)


def test_turn_end_heaven_seizure_revives_with_the_sun_amulet(board):
    """ターン終了時の発作でも太陽のお守りで復活することを検証します。"""
    revive_hp = 10  # SUN_AMULET_REVIVE_HP
    g = board(
        p0=Side(hp=99, mp=10, sickness=SicknessType.SICKNESS_HEAVEN, hand=[AMULET]),
        p1=Side(hp=99, mp=10),
    )
    g.rng.deck_always(FILLER)
    g.rng.sickness_worsen(True)

    g.pray()

    g.expect(p0_hp=revive_hp, is_done=False)


# ============================================================================
# 竜巻: ダメージではなくHPの強制上書き
# ============================================================================


def test_tornado_does_not_roll_for_guardian_leave(board):
    """竜巻でHPが1になっても、守護神の退散判定が行われないことを検証します。

    竜巻はダメージではなくHPの強制上書きなので、HPが大きく減っても
    守護神は離脱しません。
    """
    g = board(
        p0=Side(hp=99, mp=10, money=10, guardian=MARS, hand=[FATE]),
        p1=Side(hp=99, mp=10, money=10, guardian=MARS),
    )
    g.rng.deck_always(FILLER)
    g.rng.phenomenon(PhenomenonType.TORNADO)

    g.attack(FATE, to_self=True)

    assert g.rng.consumed(RollKind.GUARDIAN_LEAVE) == 0, (
        "竜巻はダメージではないので、退散判定は行われないはずです"
    )
    g.expect(p0_hp=1, p1_hp=1, p0_guardian=MARS, p1_guardian=MARS)
