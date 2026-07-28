"""守護神の離脱判定（自傷ダメージ経路）のテスト。

守護神は「ダメージを受けてHPが減少した」際に GUARDIAN_LEAVE_RATE の確率で離脱します。
この判定は相手からの攻撃を受けた場合だけでなく、自分自身へのダメージ
（奇跡の自己攻撃、雑貨によるHP減少、終末の時に引いた悪魔カードなど）でも
同様に行われる必要があります。

【移行メモ】
従来は「離脱するシード」「離脱しないシード」をそれぞれ最大5000回探索していました。
探索対象が2つの確率（例: ドキドキ涙の±10 と 離脱判定）の同時成立だったため、
探索が空振りするとテスト自体が例外で落ちる構造でもありました。
現在は各判定を直接指示するので、探索も同時成立の運任せも不要です。
"""

import pytest

import godfield_core
from godfield_core import GuardianType, RollKind, SicknessType
from tests.core.dsl import Side, card_feature

MARS = int(GuardianType.MARS)
NONE = int(GuardianType.NONE)

FILLER = "armor/wood-shield"


@pytest.mark.parametrize("leaves", [True, False], ids=["離脱する", "残留する"])
def test_miracle_self_attack_triggers_the_guardian_leave_roll(board, leaves):
    """奇跡を自分自身に撃ってHPが減った場合も、守護神の離脱判定が行われることを検証します。

    ＜滝＞は命中率100%・ATK25 の無属性奇跡。相手の守護神は置かず、
    相手のターン終了行動によるノイズを排除しています。
    """
    power = card_feature("miracles/waterfall", "attack_power")
    g = board(
        p0=Side(hp=40, mp=40, guardian=MARS, hand=["miracles/waterfall"]),
        p1=Side(hp=40),
    )
    g.rng.deck_always(FILLER)
    g.rng.guardian_leave(leaves=leaves)
    g.attack("miracles/waterfall", to_self=True)

    g.expect(p0_hp=40 - power, p0_guardian=NONE if leaves else MARS)
    assert g.rng.consumed(RollKind.GUARDIAN_LEAVE) == 1


@pytest.mark.parametrize("leaves", [True, False], ids=["離脱する", "残留する"])
def test_thump_thump_tear_hp_loss_triggers_the_guardian_leave_roll(board, leaves):
    """ドキドキ涙で HP-10 を引いた場合も守護神の離脱判定が行われることを検証します。

    攻撃由来でないHP減少でも「ダメージ」として扱われることの確認です。
    """
    g = board(
        p0=Side(hp=40, guardian=MARS, hand=["sundries/thump-thump-tear"]),
        p1=Side(hp=40),
    )
    g.rng.deck_always(FILLER)
    g.rng.thump_thump_tear(heals=False)  # HP-10 を引かせる
    g.rng.guardian_leave(leaves=leaves)
    g.attack("sundries/thump-thump-tear", to_self=True)
    g.confirm()

    g.expect(p0_hp=30, p0_guardian=NONE if leaves else MARS)
    assert g.rng.consumed(RollKind.GUARDIAN_LEAVE) == 1


def test_thump_thump_tear_healing_does_not_roll_for_guardian_leave(board):
    """ドキドキ涙が HP+10 を引いた場合は離脱判定そのものが行われないことを検証します。

    従来は「-10 を引いた」シードだけを探しており、+10 側は検証されていませんでした。
    """
    g = board(
        p0=Side(hp=40, guardian=MARS, hand=["sundries/thump-thump-tear"]),
        p1=Side(hp=40),
    )
    g.rng.deck_always(FILLER)
    g.rng.thump_thump_tear(heals=True)
    g.attack("sundries/thump-thump-tear", to_self=True)
    g.confirm()

    g.expect(p0_hp=50, p0_guardian=MARS)
    assert g.rng.consumed(RollKind.GUARDIAN_LEAVE) == 0


@pytest.mark.parametrize(
    ("devil", "damage"),
    [
        ("devils/small-devil", 10),
        ("devils/medium-devil", 20),
        ("devils/large-devil", 30),
    ],
    ids=["小悪魔10", "中悪魔20", "大悪魔30"],
)
@pytest.mark.parametrize("leaves", [True, False], ids=["離脱する", "残留する"])
def test_apocalypse_devil_damage_triggers_the_guardian_leave_roll(board, devil, damage, leaves):
    """終末の時に引いた悪魔の自傷ダメージでも守護神の離脱判定が行われることを検証します。

    従来は小悪魔・中悪魔・大悪魔のどれが出たかを区別せず「HPが減った」ことしか
    見ていませんでした（そもそも探索でどれが出るか制御できなかった）。
    """
    g = board(
        p0=Side(hp=90, guardian=MARS, hand=[]),  # 大悪魔30でも死なないHP
        p1=Side(hp=90),
        turn=150,  # APOCALYPSE_TURN
    )
    g.rng.deck_always(FILLER)
    # 悪魔を引くと効果適用後に再ドローされるので、最後は通常抽選で終わらせる
    g.rng.apocalypse_draws(devil, None)
    g.rng.guardian_leave(leaves=leaves)
    g.pray()

    g.expect(p0_hp=90 - damage, p0_guardian=NONE if leaves else MARS)
    assert g.rng.consumed(RollKind.GUARDIAN_LEAVE) == 1


def test_apocalypse_charity_fairy_does_not_roll_for_guardian_leave(board):
    """めぐみの妖精はHPが増えるだけなので離脱判定が行われないことを検証します。"""
    g = board(
        p0=Side(hp=90, mp=0, money=0, guardian=MARS, hand=[]),
        p1=Side(hp=90),
        turn=150,
    )
    g.rng.deck_always(FILLER)
    g.rng.apocalypse_draws("devils/charity-fairy", None)
    g.rng.force(RollKind.DEVIL_FAIRY, 0)  # HP+10 を選ばせる
    g.pray()

    g.expect(p0_hp=99, p0_guardian=MARS)  # 90+10 は上限99でクランプ
    assert g.rng.consumed(RollKind.GUARDIAN_LEAVE) == 0


def test_apocalypse_normal_draw_skips_the_devil_table(board):
    """終末の時でも悪魔の区間に入らなければ通常の山札抽選になることを検証します。"""
    g = board(p0=Side(hp=90, guardian=MARS, hand=[]), p1=Side(hp=90), turn=150)
    g.rng.deck_always(FILLER)
    g.rng.apocalypse_draws(None)
    g.pray()

    g.expect(p0_hp=90, p0_guardian=MARS, p0_hand=[FILLER])
    assert g.rng.consumed(RollKind.GUARDIAN_LEAVE) == 0


def test_apocalypse_devil_table_matches_the_cpp_thresholds():
    """悪魔の一覧と閾値が C++ から取得できていることを確認します。

    テストにインデックスや確率値を直書きすると、C++ 側の配分を変えたときに
    別の悪魔を黙って検証してしまいます。
    """
    devils = godfield_core.get_apocalypse_devils()
    percents = godfield_core.get_apocalypse_devil_percents()
    assert len(devils) == len(percents)
    assert all(p > 0 for p in percents), "出現率0の悪魔があると、その悪魔を狙えなくなります"
    assert sum(percents) <= 100, "合計が100を超えると通常ドローが起きなくなります"


@pytest.mark.parametrize("leaves", [True, False], ids=["離脱する", "残留する"])
def test_weapon_self_attack_triggers_the_guardian_leave_roll(board, leaves):
    """武器を自分自身に撃ってHPが減った場合も、守護神の離脱判定が行われることを検証します。

    奇跡の自傷は apply_damage() を通るので離脱判定が入りますが、武器の自傷は
    execute_attack_from_staged_cards() 内でHPを直接いじっており、
    try_guardian_leave() を呼んでいませんでした。同じ「自傷でHPが減った」でも
    使ったカードの種別で挙動が変わってしまいます。

    このファイルの冒頭に書いてあるとおり、離脱判定は自分自身へのダメージでも
    行われる必要があります。
    """
    weapon = "weapons/punch"  # 命中率100%・単体・状態異常なし
    power = card_feature(weapon, "attack_power")
    assert card_feature(weapon, "accuracy", 100) == 100, "自傷できる武器である前提"

    g = board(
        p0=Side(hp=40, mp=10, guardian=MARS, hand=[weapon]),
        p1=Side(hp=40),
    )
    g.rng.deck_always(FILLER)
    g.rng.guardian_leave(leaves=leaves)

    g.attack(weapon, to_self=True)

    g.expect(p0_hp=40 - power)
    assert g.rng.consumed(RollKind.GUARDIAN_LEAVE) == 1, (
        "自傷でHPが減ったので、守護神の離脱判定が行われるべきです"
    )
    g.expect(p0_guardian=NONE if leaves else MARS)


@pytest.mark.parametrize("leaves", [True, False], ids=["離脱する", "残留する"])
def test_dangerous_pestle_self_hit_triggers_the_guardian_leave_roll(board, leaves):
    """あぶないキネが自分に当たった場合も、守護神の離脱判定が行われることを検証します。

    キネの自傷はHPを直接いじっており、apply_damage() を通っていなかったため
    離脱判定が抜けていました。
    """
    g = board(
        p0=Side(hp=99, mp=10, guardian=MARS, hand=["weapons/dangerous-pestle"]),
        p1=Side(hp=99),
    )
    g.rng.deck_always(FILLER)
    g.rng.force(RollKind.PESTLE_TARGET, 0)  # 自分を対象にする
    g.rng.guardian_leave(leaves=leaves)

    g.attack("weapons/dangerous-pestle")

    assert g.rng.consumed(RollKind.GUARDIAN_LEAVE) == 1, (
        "キネの自傷でHPが減ったので、離脱判定が行われるべきです"
    )
    g.expect(p0_guardian=NONE if leaves else MARS)


@pytest.mark.parametrize("leaves", [True, False], ids=["離脱する", "残留する"])
def test_dangerous_mortar_99_damage_triggers_the_guardian_leave_roll(board, leaves):
    """あぶないウスの99ダメージでも守護神の離脱判定が行われることを検証します。

    ウスもHPを直接いじっており、離脱判定が抜けていました。
    99ダメージは即死しうるので、生き残るHPを与えて判定だけを見ます。
    """
    g = board(
        p0=Side(hp=99, mp=10, guardian=MARS,
                hand=["weapons/dangerous-pestle", "sundries/dangerous-mortar"]),
        p1=Side(hp=99),
    )
    g.rng.deck_always(FILLER)
    g.rng.force(RollKind.MORTAR_VICTIM, 0)  # ウス所持者はP0のみなのでP0が被弾
    g.rng.guardian_leave(leaves=leaves)

    g.attack("weapons/dangerous-pestle")

    assert g.rng.consumed(RollKind.GUARDIAN_LEAVE) == 1, (
        "ウスの99ダメージでHPが減ったので、離脱判定が行われるべきです"
    )
    g.expect(p0_guardian=NONE if leaves else MARS)


def test_sickness_damage_triggers_the_guardian_leave_roll(board):
    """病気のターン終了ダメージでも守護神の離脱判定が行われることを検証します。

    この経路は apply_damage() を通らず try_guardian_leave() を直接呼んでいます。
    apply_damage への集約が漏れているように見えますが、判定自体は行われており
    挙動は正しいので、そのことをテストで固定しておきます。
    """
    g = board(
        p0=Side(hp=40, mp=10, guardian=MARS, sickness=SicknessType.SICKNESS_COLD,
                hand=[FILLER]),
        p1=Side(hp=40),
    )
    g.rng.deck_always(FILLER)
    g.rng.sickness_worsen(False)
    g.rng.guardian_leave(leaves=True)

    g.pray()

    assert g.rng.consumed(RollKind.GUARDIAN_LEAVE) >= 1, (
        "病気ダメージでHPが減ったので、離脱判定が行われるべきです"
    )
    g.expect(p0_guardian=NONE)
