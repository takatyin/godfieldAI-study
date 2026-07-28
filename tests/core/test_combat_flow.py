
import pytest

import godfield_core
from godfield_core import ActionType, Element, GamePhase, RollKind
from tests.core.dsl import (
    Side,
    all_cards,
    armor_of_element,
    card_feature,
    card_id,
    card_name,
    element_of,
)

# 補充ドローで盤面が動かないようにするための無害なカード。
FILLER = "armor/wood-shield"

# ==========================================
# Merged from: tests/core/test_basic.py
# ==========================================



def test_illegal_action_is_ignored_without_changing_the_board(board):
    """非合法なアクションを渡しても状態が一切変化しないことを検証します。

    非合法手を渡した際に静かに状態が壊れると、強化学習側が不正な行動を選んだときに
    盤面が破綻します。

    以前はここで PHASE_GUARDIAN を使っていましたが、この値には合法手の定義も
    フェイズハンドラも無く、実ゲームでは一度も設定されません（合法手が0件になる
    ため、現在は詰みとして例外になります）。メインフェイズで検証します。
    """
    g = board(p0=Side(hp=40, mp=10, hand=["weapons/punch"]), p1=Side(hp=40, mp=10))

    # メインフェイズでは対象選択はまだできない
    assert not g.legal_actions()[int(ActionType.ACTION_TARGET_OPP)]
    g.step(ActionType.ACTION_TARGET_OPP)

    g.expect(phase=GamePhase.PHASE_MAIN, actor=0, p0_hp=40, p1_hp=40)
    assert g.state.get_num_staged_cards(0) == 0


def test_env_pool_reset_clears_events():
    """EnvPool.reset(seed) がイベント履歴・状態異常・守護神を完全にクリアすることを確認します。"""
    pool = godfield_core.EnvPool(1)
    pool.reset(0)

    state = pool.get_state(0)
    godfield_core.step_game(state, godfield_core.ActionType.ACTION_PRAY)
    obs = godfield_core.get_observation(state, 0)
    assert len(obs.get_history()) > 0

    pool.reset(42)
    new_obs = godfield_core.get_observation(pool.get_state(0), 0)

    valid_events = [ev for ev in new_obs.get_history() if ev.event_type != 0]
    assert len(valid_events) == 0


# ==========================================
# Merged from: tests/core/test_weapon_attacks.py
# ==========================================


def test_physical_attack_opens_the_defense_phase(board):
    """武器攻撃で防御フェイズが開き、威力と属性がカードマスタどおりに載ることを検証します。"""
    weapon = "weapons/punch"
    g = board(p0=Side(hp=40, hand=[weapon]), p1=Side(hp=40))

    g.attack(weapon)

    g.expect(
        phase=GamePhase.PHASE_DEFENSE,
        attacker=0,
        defender=1,
        actor=1,
        pending_power=card_feature(weapon, "attack_power"),
        pending_element=element_of(weapon),
    )


def test_physical_defense_subtracts_armor_and_passes_the_turn(board):
    """防具で軽減されたぶんだけダメージが入り、ターンが相手へ移ることを検証します。"""
    weapon, armor = "weapons/punch", "armor/leather-clothes"
    g = board(p0=Side(hp=40, hand=[weapon]), p1=Side(hp=40, hand=[armor]))
    g.rng.deck_always("armor/wood-shield")

    g.attack(weapon)
    g.defend(armor)

    damage = card_feature(weapon, "attack_power") - card_feature(armor, "defense_power")
    g.expect(p1_hp=40 - damage, phase=GamePhase.PHASE_MAIN, actor=1)


def test_physical_self_attack_resolves_without_a_defense_phase(board):
    """自分自身への武器攻撃は防御フェイズを経ずに即座に解決されることを検証します。"""
    weapon = "weapons/punch"
    g = board(p0=Side(hp=40, hand=[weapon]), p1=Side(hp=40))
    g.rng.deck_always("armor/wood-shield")

    g.attack(weapon, to_self=True)

    g.expect(
        p0_hp=40 - card_feature(weapon, "attack_power"),
        phase=GamePhase.PHASE_MAIN,
        actor=1,
    )


def test_attack_plus_weapons_sum_their_power(board):
    """プラス武器の重ねがけで攻撃力が合計されることを検証します。"""
    main, plus1, plus2 = "weapons/punch", "weapons/boomerang", "weapons/battle-ball"
    g = board(p0=Side(hp=40, hand=[main, plus1, plus2]), p1=Side(hp=40))

    g.attack(main, plus1, plus2)

    expected = sum(card_feature(c, "attack_power") for c in (main, plus1, plus2))
    g.expect(pending_power=expected, phase=GamePhase.PHASE_DEFENSE)


def test_non_plus_weapon_cannot_be_stacked(board):
    """重ねがけフェイズでは、プラス属性を持たない武器を追加できないことを検証します。"""
    main, other = "weapons/punch", "weapons/bronze-club"
    g = board(p0=Side(hp=40, hand=[main, other]), p1=Side(hp=40))

    g.select(main)

    g.expect(phase=GamePhase.PHASE_ATTACK_PLUS)
    g.expect_illegal([other])


@pytest.mark.parametrize(
    ("stack", "expected_mp"),
    [
        # 武器 + 火の玉 + ぬいぐるみ + 火の玉: 最後の火の玉の2MPだけが残る
        (["weapons/punch", "miracles/fireball", "sundries/spiritual-doll", "miracles/fireball"], 8),
        # さらにぬいぐるみを重ねると、そのMPも相殺されて消費0になる
        (["weapons/punch", "miracles/fireball", "sundries/spiritual-doll", "miracles/fireball",
          "sundries/spiritual-doll"], 10),
    ],
    ids=["4枚: MP2消費", "5枚: MP0消費"],
)
def test_spiritual_doll_cancels_the_following_miracle_mp_cost(board, stack, expected_mp):
    """精霊のぬいぐるみが直前の奇跡のMP消費を相殺することを、枚数違いで検証します。

    従来は2つのシナリオが1つの関数に押し込まれ、どちらが失敗したのか分かりにくい
    構造でした。
    """
    g = board(p0=Side(hp=40, mp=10, hand=list(stack)), p1=Side(hp=40))

    g.select_slots(*range(len(stack)))
    g.target_opp()

    g.expect(phase=GamePhase.PHASE_DEFENSE, p0_mp=expected_mp)


@pytest.mark.parametrize(
    "card",
    ["weapons/ghost-sword", "weapons/real-ghost-sword", "weapons/vine-shoot", "miracles/absorption"],
)
def test_absorption_cards_heal_the_attacker_for_the_damage_dealt(board, card):
    """HP吸収カードが、与えたダメージと同じだけ攻撃側を回復させることを検証します。

    従来はゴーストソード2種しか検証しておらず、つるシュートと＜吸収＞は
    吸収の観点では未検証でした。
    """
    power = card_feature(card, "attack_power")
    g = board(
        p0=Side(hp=40, mp=50, hand=[card]),
        p1=Side(hp=40, mp=50),
    )
    g.rng.deck_always("armor/wood-shield")
    g.rng.hits(always=True) if card_feature(card, "accuracy", 100) < 100 else None
    g.attack(card)
    g.take_hit()

    g.expect(p1_hp=40 - power, p0_hp=40 + power)


@pytest.mark.parametrize(
    ("guardian", "action_card"),
    [
        (int(godfield_core.GuardianType.JUPITER), "gurdians/tentacles"),
        (int(godfield_core.GuardianType.URANUS), "gurdians/blessing"),
    ],
    ids=["木星神の触手", "天王神の祝福"],
)
def test_guardian_absorption_actions_heal_their_owner(board, guardian, action_card):
    """守護神の吸収行動が、持ち主のHPを与えたダメージ分だけ回復させることを検証します。

    従来この2種はまったく検証されていませんでした。
    """
    power = card_feature(action_card, "attack_power")
    g = board(
        p0=Side(hp=40, hand=["armor/leather-clothes"]),
        p1=Side(hp=30, guardian=guardian),
    )
    g.rng.deck_always("armor/wood-shield")
    g.rng.guardian_action_card(guardian, action_card)
    # 触手・祝福は命中率100%、また P0 は守護神を持たないため、
    # 命中判定も離脱判定も行われない（指示すると空振りになる）

    g.discard("armor/leather-clothes")
    g.expect(phase=GamePhase.PHASE_DEFENSE, attacker=1, defender=0)
    g.take_hit()

    g.expect(p0_hp=40 - power, p1_hp=30 + power)


def test_absorption_source_list_is_fully_covered():
    """C++ の吸収カード一覧が、このファイルのテストで全種カバーされていることを確認します。

    吸収カードが追加されたときに、テストが無いまま通り過ぎるのを防ぎます。
    """
    sources = set(godfield_core.get_absorption_sources())
    covered = {
        card_id(c) for c in (
            "weapons/ghost-sword", "weapons/real-ghost-sword", "weapons/vine-shoot",
            "miracles/absorption", "gurdians/tentacles", "gurdians/blessing",
        )
    }
    assert sources == covered, (
        "未検証の吸収カードがあります: "
        + ", ".join(card_name(c) for c in sorted(sources - covered))
    )


EVIL_BROADSWORD = "weapons/evil-broadsword"


def test_evil_broadsword_recoils_onto_the_attacker(board):
    """邪神の大剣が、与えたダメージと同じだけ攻撃者にも跳ね返ることを検証します。"""
    power = card_feature(EVIL_BROADSWORD, "attack_power")
    g = board(p0=Side(hp=40, hand=[EVIL_BROADSWORD]), p1=Side(hp=40))
    g.rng.deck_always("armor/wood-shield")

    g.attack(EVIL_BROADSWORD)
    g.take_hit()

    g.expect(p1_hp=40 - power, p0_hp=40 - power)


def test_evil_broadsword_on_self_deals_double(board):
    """邪神の大剣を自分に使うと、本体と自傷で2倍のダメージを受けることを検証します。"""
    power = card_feature(EVIL_BROADSWORD, "attack_power")
    g = board(p0=Side(hp=40, hand=[EVIL_BROADSWORD]), p1=Side(hp=40))
    g.rng.deck_always("armor/wood-shield")

    g.attack(EVIL_BROADSWORD, to_self=True)

    g.expect(p0_hp=40 - power * 2)


def test_evil_broadsword_bounce_failure_doubles_the_defender_damage(board):
    """乱弾武剣で邪神の大剣を弾き損ねた場合、防御側が本体＋自傷の2倍を受けることを検証します。"""
    power = card_feature(EVIL_BROADSWORD, "attack_power")
    g = board(
        p0=Side(hp=40, hand=[EVIL_BROADSWORD]),
        p1=Side(hp=40, hand=["weapons/bouncing-sword"]),
    )
    g.rng.deck_always("armor/wood-shield")
    g.rng.bounce(success=False)

    g.attack(EVIL_BROADSWORD)
    g.defend("weapons/bouncing-sword")

    g.expect(p1_hp=40 - power * 2, p0_hp=40)


def test_evil_broadsword_bounce_success_moves_the_recoil_to_the_bouncer(board):
    """邪神の大剣を弾き返すと、跳ね返り（自傷）の対象も弾いた側へ移ることを検証します。

    邪神の大剣の自傷は「その時点の攻撃者」に入ります。弾きに成功すると攻守が
    入れ替わるため、跳ね返りを受けるのは元の攻撃者ではなく弾いた側になります。
    結果として、両者が本体1回分ずつを受ける形になります。

    従来は seed_rng(0) が「失敗するシード」であることに依存していたため、
    成功側のこの挙動はまったく検証されていませんでした。
    """
    power = card_feature(EVIL_BROADSWORD, "attack_power")
    g = board(
        p0=Side(hp=40, hand=[EVIL_BROADSWORD]),
        p1=Side(hp=40, hand=["weapons/bouncing-sword"]),
    )
    g.rng.deck_always("armor/wood-shield")
    g.rng.bounce(success=True)

    g.attack(EVIL_BROADSWORD)
    g.defend("weapons/bouncing-sword")

    # 攻守が入れ替わり、元の攻撃者が防御側に立つ（この時点ではまだ誰も被弾していない）
    g.expect(phase=GamePhase.PHASE_DEFENSE, attacker=1, defender=0, p0_hp=40, p1_hp=40)

    g.take_hit()

    # 元の攻撃者は本体を、弾いた側は跳ね返りを受ける
    g.expect(p0_hp=40 - power, p1_hp=40 - power)


WAND_CASES = [
    # (重ねる順, 期待属性, 規則の説明)
    (["weapons/punch", "weapons/fire-crossbow", "weapons/wand-of-mystic-water"],
     Element.ELEM_WATER, "ワンドは直前までの属性を自分の属性で上書きする"),
    (["weapons/holy-sword", "weapons/fire-crossbow", "weapons/wand-of-mystic-water"],
     Element.ELEM_WATER, "ベースが光でもワンドの属性で上書きされる"),
    (["weapons/holy-sword", "weapons/fire-crossbow", "weapons/wand-of-mystic-water",
      "weapons/fire-crossbow"],
     Element.ELEM_NONE, "ワンドの後に別の通常属性を足すと打ち消し合って無属性になる"),
    (["weapons/holy-sword", "weapons/fire-crossbow", "weapons/wand-of-mystic-water",
      "weapons/piece-of-brightness"],
     Element.ELEM_WATER, "ワンドの後に光を足しても、光は中立なので水のまま"),
    (["weapons/wand-of-mystic-water", "weapons/warrior-s-bow"],
     Element.ELEM_NONE, "ワンドの後に無属性を足すと無属性になる"),
    # 発火のワンド（火）も同じ規則で働くこと。従来はテスト名に挙がっていながら
    # 一度も使われていなかった。
    (["weapons/punch", "weapons/wand-of-ignition"],
     Element.ELEM_FIRE, "発火のワンドも直前までの属性を火で上書きする"),
    # ワンド同士は打ち消し合わず、後から置いたワンドが上書きする（通常の有属性同士とは異なる）
    (["weapons/holy-sword", "weapons/wand-of-mystic-water", "weapons/wand-of-ignition"],
     Element.ELEM_FIRE, "ワンドを重ねると後のワンドが上書きする"),
]


@pytest.mark.parametrize(
    ("stack", "expected_element", "why"),
    WAND_CASES,
    ids=[c[2] for c in WAND_CASES],
)
def test_wand_element_override_rules(board, stack, expected_element, why):
    """ワンドによる属性上書きと、その後の重ねがけの解決順序を検証します。

    規則は次の3つです:
      1. ワンドは、それまでに積み上がった属性を自分の属性で「上書き」する
      2. ワンドの後に通常の有属性を足すと、通常どおり打ち消し合って無属性になる
      3. ワンド同士は打ち消し合わず、後から置いたワンドが上書きする

    従来は5つのシナリオが1つの関数に並んでおり、規則の全体像が読めませんでした。
    また「発火のワンド」はテスト名に挙がっていながら一度も使われておらず、
    ワンド同士を重ねた場合の挙動（規則3）も未検証でした。

    攻撃力の合計もカードマスタから計算して検証します。
    """
    g = board(
        p0=Side(hp=99, mp=50, money=50, hand=list(stack)),
        p1=Side(hp=99, mp=50, money=50),
    )

    g.select_slots(*range(len(stack)))
    g.target_opp()

    expected_power = sum(card_feature(c, "attack_power") for c in stack)
    g.expect(pending_element=expected_element, pending_power=expected_power)


def test_wand_cards_are_all_covered():
    """カードマスタ上のワンドがすべて上記の表で検証されていることを確認します。"""
    wands = {
        c["id_str"] for c in all_cards()
        if "ワンド" in (c.get("name") or "") and c.get("id_str")
    }
    used = {card for stack, _, _ in WAND_CASES for card in stack}
    assert wands <= used, f"未検証のワンドがあります: {sorted(wands - used)}"


MAGICAL_STICK = "weapons/magical-stick"
METEOR = "miracles/meteor"
DOLL = "sundries/spiritual-doll"


def magical_stick_power(mp_left: int) -> int:
    """マジカルステッキの攻撃力は「重ねがけ後に残るMP」の2倍になります。"""
    return mp_left * 2


@pytest.mark.parametrize(
    ("mp", "stack", "expected_power", "why"),
    [
        (10, [MAGICAL_STICK], magical_stick_power(10),
         "単体なら所持MP全額が攻撃力の元になる"),
        (10, [MAGICAL_STICK, METEOR],
         magical_stick_power(10 - card_feature(METEOR, "mp_cost"))
         + card_feature(METEOR, "attack_power"),
         "重ねた奇跡のMP消費を差し引いた残りが元になる"),
        (10, [MAGICAL_STICK, METEOR, DOLL],
         magical_stick_power(10) + card_feature(METEOR, "attack_power"),
         "精霊で奇跡のMPが相殺されると所持MP全額が元に戻る"),
        (0, [MAGICAL_STICK], 0,
         "MP0でも使用でき、攻撃力0になる"),
    ],
    ids=["単体", "流星を重ねる", "流星＋精霊", "MP0"],
)
def test_magical_stick_power_scales_with_remaining_mp(board, mp, stack, expected_power, why):
    """マジカルステッキの攻撃力が「残MPの2倍」で決まることを検証します。

    従来は 20 / 16 / 30 / 0 という結果の数値だけが直書きされており、
    どう計算されているのかがコメントを読まないと分かりませんでした。
    """
    g = board(p0=Side(hp=40, mp=mp, hand=list(stack)), p1=Side(hp=40))
    g.rng.deck_always("armor/wood-shield")

    g.select_slots(*range(len(stack)))
    g.target_opp()

    g.expect(
        phase=GamePhase.PHASE_DEFENSE,
        pending_power=expected_power,
        pending_element=Element.ELEM_NONE,
    )

    g.take_hit()
    g.expect(p0_mp=0)  # マジカルステッキは残MPを全て消費する


@pytest.mark.parametrize(
    ("mp", "has_doll", "expected_legal"),
    [
        (10, False, True),   # MPが足りるのでそのまま重ねられる
        (5, False, False),   # MP不足かつ精霊なしでは重ねられない
        (5, True, True),     # 精霊が手札にあれば重ねられる（まだ置いていなくても良い）
    ],
    ids=["MP十分", "MP不足・精霊なし", "MP不足・精霊あり"],
)
def test_meteor_stackability_depends_on_affordable_mp(board, mp, has_doll, expected_legal):
    """マジカルステッキに奇跡を重ねられるかが、MPと精霊の有無で決まることを検証します。

    精霊は「手札にあるだけ」で重ねがけが解禁されます（実際に置くのは後で良い）。
    """
    hand = [MAGICAL_STICK, METEOR] + ([DOLL] if has_doll else [])
    g = board(p0=Side(hp=40, mp=mp, hand=hand), p1=Side(hp=40))

    g.select(MAGICAL_STICK)
    g.expect(phase=GamePhase.PHASE_ATTACK_PLUS)

    if expected_legal:
        g.expect_legal([METEOR])
    else:
        g.expect_illegal([METEOR])


PESTLE = "weapons/dangerous-pestle"
MORTAR = "sundries/dangerous-mortar"
SUN_AMULET = "sundries/sun-amulet"

# あぶないウスに当たった場合の固定ダメージ（エンジン側の定数）
MORTAR_DAMAGE = 99


def count_unused_mortars(g, player: int) -> int:
    """未使用のあぶないウスの枚数を数えます。"""
    return sum(
        1
        for i in range(18)
        if g.state.get_true_hand(player, i) == card_id(MORTAR)
        and not g.state.get_is_used(player, i)
    )


@pytest.mark.parametrize("target_idx", [0, 1], ids=["自分に当たる", "相手に当たる"])
def test_dangerous_pestle_without_mortar_picks_a_living_target(board, target_idx):
    """ウスが無い場合、あぶないキネの対象が生存者から抽選されることを検証します。

    従来は100回試行して「30〜70回が自傷」という統計的アサーションでした。
    失敗しても確率の偏りなのか実装バグなのか区別できず、境界も踏めませんでした。
    """
    power = card_feature(PESTLE, "attack_power")
    g = board(
        p0=Side(hp=40, hand=[PESTLE]),
        p1=Side(hp=40, hand=["armor/super-mirror"]),
    )
    g.rng.deck_always("armor/wood-shield")
    g.rng.force(RollKind.PESTLE_TARGET, target_idx)

    g.attack(PESTLE)

    if target_idx == 0:
        # 自傷は防御フェイズを起動せず直接解決される
        g.expect(p0_hp=40 - power, p1_hp=40, phase=GamePhase.PHASE_MAIN)
    else:
        g.expect(
            phase=GamePhase.PHASE_DEFENSE,
            pending_power=power,
            pending_element=element_of(PESTLE),
        )


@pytest.mark.parametrize(
    ("victim_roll", "p0_hit"),
    [
        (0, True),   # 区間の下端
        (2, True),   # P0側の上端（P0は3枚持ち）
        (3, False),  # P1側の下端
        (4, False),  # 区間の上端
    ],
    ids=["roll=0 -> P0", "roll=2 -> P0", "roll=3 -> P1", "roll=4 -> P1"],
)
def test_dangerous_mortar_victim_is_chosen_in_proportion_to_held_mortars(
    board, victim_roll, p0_hit
):
    """あぶないウスの被弾者が、所持枚数の比で決まることを境界値で検証します。

    P0が3枚・P1が2枚なら、抽選値 0..4 のうち 0-2 がP0、3-4 がP1に対応します。
    従来は100回試行して「45〜75回がP0被弾」という統計的アサーションで、
    比率の境界（2と3の境目）は検証できていませんでした。

    被弾した側のウスだけが1枚消費され、もう一方は減らないことも確認します。
    """
    g = board(
        p0=Side(hp=100, hand=[PESTLE, MORTAR, MORTAR, MORTAR]),
        p1=Side(hp=100, hand=[MORTAR, MORTAR]),
    )
    g.rng.deck_always("armor/wood-shield")
    g.rng.force(RollKind.MORTAR_VICTIM, victim_roll)

    g.attack(PESTLE)

    # ウスがある場合は防御フェイズを介さずに自動解決される
    g.expect(phase=GamePhase.PHASE_MAIN)

    if p0_hit:
        g.expect(p0_hp=100 - MORTAR_DAMAGE, p1_hp=100)
        assert count_unused_mortars(g, 0) == 2, "被弾側のウスが1枚消費される"
        assert count_unused_mortars(g, 1) == 2, "被弾しなかった側のウスは減らない"
    else:
        g.expect(p0_hp=100, p1_hp=100 - MORTAR_DAMAGE)
        assert count_unused_mortars(g, 0) == 3
        assert count_unused_mortars(g, 1) == 1


def test_mortar_damage_consumes_one_mortar_and_amulet_per_hit(board):
    """ウス被弾でお守りが復活させ、2回目は残るウスで死亡することを検証します。

    1回目: B が99被弾 -> HP0 -> お守りで復活してHP10。ウスは1枚だけ消費される。
    2回目: B 自身がキネを撃ち、残った1枚のウスで再び99被弾。お守りはもう無いので死亡。
    """
    g = board(
        p0=Side(hp=40, hand=[PESTLE]),
        p1=Side(hp=40, hand=[PESTLE, MORTAR, MORTAR, SUN_AMULET]),
    )
    g.rng.deck_always("armor/wood-shield")
    g.rng.force(RollKind.MORTAR_VICTIM, 0)  # ウス所持者はP1のみなので必ずP1が被弾する

    g.attack(PESTLE)

    g.expect(p1_hp=10)  # お守りで復活
    assert count_unused_mortars(g, 1) == 1, "ウスは1枚だけ消費される"

    # B のターンに移して、B 自身がキネを撃つ
    g.state.current_phase = GamePhase.PHASE_MAIN
    g.state.current_actor_id = 1
    g.select(PESTLE, player=1)
    g.target_opp()

    g.expect(p1_hp=0)  # お守りが無いので死亡
    assert count_unused_mortars(g, 1) == 0


# ==========================================
# 状態異常を付与する防具 / 複数回攻撃 / ターン終了時の解決
# ==========================================

SAW = "weapons/saw-boom-boom"          # 2回攻撃
MIRAGE = "miracles/mirage"             # 攻撃回数を枚数倍する
AURA = "miracles/aura"                 # 攻撃力2倍・無属性化
FEVER_MASK = "armor/fever-mask"        # 被弾すると装備者が熱病になる
DREAMING_HAT = "armor/dreaming-hat"    # 被弾すると装備者が夢になり手札が一新される
SUN_AMULET = "sundries/sun-amulet"
ASCENSION_BOW = "weapons/ascension-bow"

SAW_HITS = godfield_core.SAW_BOOM_BOOM_ATTACK_COUNT


def test_fever_mask_inflicts_fever_on_its_wearer(board):
    """熱狂仮面で防御すると、防いだ側が熱病になることを検証します。"""
    punch = "weapons/punch"
    guard = card_feature(FEVER_MASK, "defense_power")
    assert guard >= card_feature(punch, "attack_power"), (
        "完全に防ぎ切れる組み合わせでないと「無傷でも病気になる」ことを検証できない"
    )

    g = board(
        p0=Side(hp=40, mp=10, hand=[punch]),
        p1=Side(hp=40, mp=10, hand=[FEVER_MASK]),
    )
    g.rng.deck_always(FILLER)

    g.attack(punch)
    g.defend(FEVER_MASK)

    # ターン終了時の病気による増減はターンプレイヤー(P0)にしか入らないため、P1のHPは無傷のまま
    g.expect(
        p1_hp=40,
        p1_sickness=godfield_core.SicknessType.SICKNESS_FEVER,
        phase=GamePhase.PHASE_MAIN,
    )


def test_dreaming_hat_inflicts_dream_and_replaces_the_entire_hand(board):
    """夢見る帽子で防御すると、夢がかかり手札が丸ごと引き直されることを検証します。

    従来のテストは「手札が一新されていること」を検証すると書きながら、
        assert get_true_hand(1, j) != -1
    としか確認していませんでした。手札が一切入れ替わらなくても通ってしまうため、
    一新処理が壊れても検出できません。

    ここでは補充ドローを盤面に無いカードに固定し、元の手札が本当に消えて
    そのカードに置き換わったことを確認します。
    """
    punch = "weapons/punch"
    old_card = "weapons/gale-sword"      # 一新前の手札（補充では絶対に出てこない）
    refill = "armor/leather-cap"         # 一新後に引かれるカード
    guard = card_feature(DREAMING_HAT, "defense_power")
    assert guard >= card_feature(punch, "attack_power")

    g = board(
        p0=Side(hp=40, mp=10, hand=[punch]),
        p1=Side(hp=40, mp=10, hand=[DREAMING_HAT, old_card, old_card, old_card]),
    )
    g.rng.deck_always(refill)

    g.attack(punch)
    g.select(DREAMING_HAT)

    # 確定前は元の手札のまま
    assert g.hand(1).count(card_name(card_id(old_card))) == 3

    g.confirm()

    g.expect(p1_hp=40, p1_curses={godfield_core.CurseType.CURSE_DREAM})

    hand = g.hand(1)
    assert card_name(card_id(old_card)) not in hand, "元の手札が残っています（一新されていない）"
    assert hand, "手札が空のままです（補充されていない）"
    assert all(c == card_name(card_id(refill)) for c in hand), (
        f"補充されたカード以外が残っています: {hand}"
    )
    for slot in range(godfield_core.MAX_HAND_SIZE):
        assert g.state.get_is_used(1, slot) is False
        assert g.state.get_is_deployed(1, slot) is False


def test_dreaming_hat_also_discards_deployed_miracles(board):
    """夢見る帽子の手札一新が、場に展開済みの奇跡も破棄することを検証します。"""
    punch = "weapons/punch"
    fireball = "miracles/fireball"
    refill = "armor/leather-cap"

    g = board(
        p0=Side(hp=40, mp=20, hand=[punch]),
        p1=Side(hp=40, mp=20, hand=[DREAMING_HAT, fireball], deployed=[1]),
    )
    g.rng.deck_always(refill)

    assert g.state.get_is_deployed(1, 1) is True, "展開済みの状態を作れていない"

    g.attack(punch)
    g.defend(DREAMING_HAT)

    g.expect(p1_curses={godfield_core.CurseType.CURSE_DREAM})
    assert card_name(card_id(fireball)) not in g.hand(1), "展開済みの奇跡が残っています"
    for slot in range(godfield_core.MAX_HAND_SIZE):
        assert g.state.get_is_deployed(1, slot) is False


def test_saw_boom_boom_attacks_twice_with_a_defense_phase_each_time(board):
    """のこぶんぶんが2回攻撃になり、1回ごとに防御の機会があることを検証します。"""
    armor = "armor/leather-clothes"
    power = card_feature(SAW, "attack_power")
    guard = card_feature(armor, "defense_power")
    assert power > guard, "防具で完全に防げてしまうと2回分の差が見えない"

    g = board(
        p0=Side(hp=40, mp=10, hand=[SAW]),
        p1=Side(hp=40, mp=10, hand=[armor]),
    )
    g.rng.deck_always(FILLER)

    g.attack(SAW)
    g.expect(phase=GamePhase.PHASE_DEFENSE, actor=1)
    assert g.state.remaining_attacks == SAW_HITS

    # 1回目は防具で受ける
    g.defend(armor)

    g.expect(phase=GamePhase.PHASE_DEFENSE, actor=1, p1_hp=40 - (power - guard))
    assert g.state.remaining_attacks == SAW_HITS - 1
    assert g.state.get_num_staged_cards(1) == 0, "1回目の仮置きが残っています"

    # 2回目は素で受ける
    g.take_hit()

    g.expect(p1_hp=40 - (power - guard) - power, phase=GamePhase.PHASE_MAIN)
    assert g.state.remaining_attacks == 0


@pytest.mark.parametrize("mirages", [1, 2, 3], ids=["蜃気楼1枚", "蜃気楼2枚", "蜃気楼3枚"])
def test_mirage_multiplies_the_saw_attack_count(board, mirages):
    """＜蜃気楼＞の枚数が、のこぶんぶんの攻撃回数に掛かることを検証します。"""
    meteor = "miracles/meteor"
    power = card_feature(SAW, "attack_power") + card_feature(meteor, "attack_power")
    expected_hits = SAW_HITS * mirages
    start_hp = 99

    g = board(
        p0=Side(hp=40, mp=40, hand=[SAW, meteor, *([MIRAGE] * mirages)]),
        p1=Side(hp=start_hp, mp=40),
    )
    g.rng.deck_always(FILLER)

    g.select_slots(*range(1 + 1 + mirages))
    g.expect(phase=GamePhase.PHASE_GROUP_WEAPON)
    g.target_opp()

    assert g.state.remaining_attacks == expected_hits
    g.expect(phase=GamePhase.PHASE_DEFENSE, pending_power=power)

    for i in range(expected_hits - 1):
        g.take_hit()
        g.expect(phase=GamePhase.PHASE_DEFENSE, p1_hp=start_hp - power * (i + 1))
        assert g.state.remaining_attacks == expected_hits - (i + 1)

    g.take_hit()

    g.expect(p1_hp=start_hp - power * expected_hits, phase=GamePhase.PHASE_MAIN)
    assert g.state.remaining_attacks == 0


def test_saw_boom_boom_restores_the_original_direction_after_a_reflection(board):
    """連撃の途中で反射されても、次の一撃が元の向きに戻ることを検証します。"""
    g = board(
        p0=Side(hp=40, mp=10, hand=[SAW]),
        p1=Side(hp=40, mp=10, hand=["weapons/reflection-sword"]),
    )
    g.rng.deck_always(FILLER)

    g.attack(SAW)
    assert g.state.remaining_attacks == SAW_HITS

    # 1回目を反射 → 攻守が入れ替わる
    g.defend("weapons/reflection-sword")
    g.expect(phase=GamePhase.PHASE_DEFENSE, actor=0)

    g.take_hit()

    # 2回目は本来の向き（P0 → P1）で再開する
    g.expect(phase=GamePhase.PHASE_DEFENSE, actor=1)
    assert g.state.remaining_attacks == SAW_HITS - 1


# ==========================================
# ＜オーラ＞: 攻撃力2倍・無属性化
#
# 旧テストは docstring に「パンチ(ATK10)」「合計20」などと書かれていましたが、
# 実際のパンチは ATK3 で、アサーションも 6 でした。数値を直書きすると
# 説明とコードが食い違ったまま誰も気付かない状態になります。
# ==========================================


def aura_power(base_cards, aura_count: int) -> int:
    """＜オーラ＞を重ねる前の合計攻撃力に、オーラの2倍を掛けた値を返します。"""
    total = sum(card_feature(c, "attack_power") for c in base_cards)
    return total * (2 ** aura_count)


def test_aura_doubles_the_power_and_clears_the_element(board):
    """＜オーラ＞が攻撃力を2倍にし、属性を無属性にすることを検証します。"""
    punch = "weapons/punch"
    mp = 20
    g = board(p0=Side(hp=40, mp=mp, hand=[punch, AURA]), p1=Side(hp=40, mp=20))
    g.rng.deck_always(FILLER)

    g.select(punch)
    g.attack(AURA)

    g.expect(
        pending_power=aura_power([punch], 1),
        pending_element=Element.ELEM_NONE,
        p0_mp=mp - card_feature(AURA, "mp_cost"),
    )


def test_aura_does_not_double_what_is_stacked_after_it(board):
    """＜オーラ＞より後ろに置いた攻撃は倍化されないことを検証します（評価順序の維持）。"""
    punch = "weapons/punch"
    blowgun = "weapons/blowgun"
    g = board(p0=Side(hp=40, mp=20, hand=[punch, AURA, blowgun]), p1=Side(hp=40, mp=20))
    g.rng.deck_always(FILLER)

    g.select(punch, AURA)
    g.attack(blowgun)

    expected = aura_power([punch], 1) + card_feature(blowgun, "attack_power")
    g.expect(pending_power=expected, pending_element=Element.ELEM_NONE)


def test_aura_clears_even_an_elemental_attack(board):
    """光属性の＜流星＞を重ねた攻撃でも、＜オーラ＞が無属性化することを検証します。"""
    punch = "weapons/punch"
    meteor = "miracles/meteor"
    assert element_of(meteor) != Element.ELEM_NONE, "有属性でないと上書きを検証できない"

    mp = 20
    g = board(p0=Side(hp=40, mp=mp, hand=[punch, meteor, AURA]), p1=Side(hp=40, mp=20))
    g.rng.deck_always(FILLER)

    g.select(punch, meteor)
    g.attack(AURA)

    cost = card_feature(meteor, "mp_cost") + card_feature(AURA, "mp_cost")
    g.expect(
        pending_power=aura_power([punch, meteor], 1),
        pending_element=Element.ELEM_NONE,
        p0_mp=mp - cost,
    )


def test_stacked_auras_multiply(board):
    """＜オーラ＞を2枚重ねると攻撃力が4倍になることを検証します。"""
    punch = "weapons/punch"
    mp = 20
    g = board(p0=Side(hp=40, mp=mp, hand=[punch, AURA, AURA]), p1=Side(hp=40, mp=20))
    g.rng.deck_always(FILLER)

    g.select_slots(0, 1)
    g.attack_slots(2)

    g.expect(
        pending_power=aura_power([punch], 2),
        p0_mp=mp - card_feature(AURA, "mp_cost") * 2,
    )


def test_magical_stick_consumes_the_leftover_mp_and_is_then_doubled(board):
    """マジカルステッキが「他のカードを払った残りMP」ぶんの攻撃力になり、その後オーラで倍化されることを検証します。"""
    stick = "weapons/magical-stick"
    meteor = "miracles/meteor"
    mp = 15

    other_cost = card_feature(meteor, "mp_cost") + card_feature(AURA, "mp_cost")
    leftover = mp - other_cost
    assert leftover > 0, "残りMPが0だとステッキの寄与を検証できない"

    # ステッキは残りMP1につき攻撃力2を生む
    stick_power = leftover * 2
    expected = (stick_power + card_feature(meteor, "attack_power")) * 2

    g = board(p0=Side(hp=40, mp=mp, hand=[stick, meteor, AURA]), p1=Side(hp=40, mp=15))
    g.rng.deck_always(FILLER)

    g.select(stick, meteor)
    g.attack(AURA)

    g.expect(pending_power=expected, pending_element=Element.ELEM_NONE, p0_mp=0)


# ==========================================
# 攻撃発生源の観測
# ==========================================


def test_the_attack_source_is_exposed_to_the_defender_observation(board):
    """攻撃発生源のカードIDが防御側の観測に載り、解決後にクリアされることを検証します。"""
    punch = "weapons/punch"
    g = board(
        p0=Side(hp=40, mp=10, hand=[punch, "armor/ice-shield"]),
        p1=Side(hp=40, mp=10),
    )
    g.rng.deck_always(FILLER)

    g.attack(punch)

    g.expect(phase=GamePhase.PHASE_DEFENSE)
    assert g.state.pending_attack_source_id == card_id(punch)

    obs = godfield_core.get_opponent_staged_cards_for_obs(g.state, 1)
    assert obs[0] == card_id(punch), "防御側から見て、攻撃元のカードが観測できるべきです"

    g.take_hit()

    g.expect(phase=GamePhase.PHASE_MAIN)
    assert g.state.pending_attack_source_id == -1, "解決後は発生源がクリアされるべきです"


def test_a_guardian_attack_source_is_exposed_as_a_virtual_card(board):
    """守護神の攻撃でも、その仮想カードが防御側の観測に載ることを検証します。

    従来は pending_attack_source_id に手で値を代入して観測だけを見ていました。
    それでは「守護神攻撃が本当にその仮想カードを発生源として設定するか」が
    検証されないため、実際に火星神を行動させて確認します。
    """
    roar = "gurdians/fire-roar"
    mars = int(godfield_core.GuardianType.MARS)

    g = board(
        p0=Side(hp=99, mp=10, hand=[FILLER]),
        p1=Side(hp=99, mp=10, guardian=mars, hand=[FILLER]),
    )
    g.rng.deck_always(FILLER)
    g.rng.guardian_action_card(mars, roar)
    g.rng.hits(always=True)

    g.pray()

    g.expect(phase=GamePhase.PHASE_DEFENSE, actor=0)
    assert g.state.pending_attack_source_id == card_id(roar)

    obs = godfield_core.get_opponent_staged_cards_for_obs(g.state, 0)
    assert obs[0] == card_id(roar), "守護神の仮想カードが観測に統合されるべきです"


# ==========================================
# 死亡・復活・昇天弓とターン終了処理
# ==========================================


def test_a_dead_player_can_only_confirm_through_the_remaining_attacks(board):
    """HP0の相手への連撃が最後まで消化され、防御側は確定しか選べないことを検証します。"""
    armor = "armor/leather-clothes"
    g = board(
        p0=Side(hp=40, mp=10, hand=[SAW]),
        p1=Side(hp=0, mp=10, hand=[armor]),
    )
    g.rng.deck_always(FILLER)

    g.attack(SAW)

    for _ in range(SAW_HITS):
        g.expect(phase=GamePhase.PHASE_DEFENSE, actor=1)
        g.expect_illegal([armor])          # 死亡しているので防具は出せない
        g.expect_actions(confirm=True)
        g.take_hit()

    g.expect(p1_hp=0, is_done=True)


def test_the_sun_amulet_revives_between_hits_of_a_multi_attack(board):
    """連撃の途中でHP0になっても、太陽のお守りが即座に復活させることを検証します。"""
    power = card_feature(SAW, "attack_power")
    revive_hp = godfield_core.SUN_AMULET_REVIVE_HP
    start_hp = power  # 1発でちょうど0になる

    g = board(
        p0=Side(hp=40, mp=10, hand=[SAW]),
        p1=Side(hp=start_hp, mp=10, hand=[SUN_AMULET]),
    )
    g.rng.deck_always(FILLER)

    g.attack(SAW)
    g.take_hit()

    # 復活したうえで、次の一撃の防御フェイズが立ち上がっている
    g.expect(p1_hp=revive_hp, phase=GamePhase.PHASE_DEFENSE, actor=1)
    assert g.state.remaining_attacks == SAW_HITS - 1

    g.take_hit()

    # お守りは使い切ったので2度目の復活はないが、まだ生きている
    g.expect(p1_hp=revive_hp - power, is_done=False, phase=GamePhase.PHASE_MAIN)


def test_the_ascension_bow_fires_only_after_every_attack_is_resolved(board):
    """昇天弓が連撃の途中では発射されず、ターン終了処理まで持ち越されることを検証します。

    従来は「発射確率75%が成功するシード」としてシード42を使っていましたが、
    それが本当に成功するのかはコードから読めず、外れれば前提が崩れます。
    """
    power = card_feature(SAW, "attack_power")
    g = board(
        p0=Side(hp=40, mp=10, hand=[SAW]),
        p1=Side(hp=power, mp=10, hand=[ASCENSION_BOW]),
    )
    g.rng.deck_always(FILLER)
    g.rng.ascension_bow(True)

    g.attack(SAW)
    g.take_hit()

    # HP0になったが昇天弓はまだ発射されず、2発目の防御フェイズが続く
    g.expect(p1_hp=0, phase=GamePhase.PHASE_DEFENSE, actor=1)
    assert g.rng.consumed(RollKind.ASCENSION_BOW_HIT) == 0, (
        "この時点で発射判定が行われてはいけません"
    )

    g.take_hit()

    # すべての攻撃が終わってから、ターン終了処理で発射される
    g.expect(
        phase=GamePhase.PHASE_DEFENSE,
        actor=0,
        pending_power=godfield_core.ASCENSION_BOW_TRIGGERED_POWER,
        pending_element=Element.ELEM_LIGHT,
    )
    assert g.state.pending_attack_source_id == card_id(ASCENSION_BOW)
    assert g.rng.consumed(RollKind.ASCENSION_BOW_HIT) == 1


def test_the_fired_ascension_bow_keeps_the_group_attack_flag_from_the_master(board):
    """発射された昇天弓が、カードマスタどおり全体攻撃として扱われることを検証します。

    昇天弓は攻撃力と命中率が手札から撃つ場合と意図的に異なる（ATK1・命中25% ではなく
    30・75%）ため、実装は pending_attack_* を個別に組み立てています。その際に
    全体攻撃フラグだけが取りこぼされ、単体攻撃に落ちていました。

    2人対戦では観測できる差が出ないので（全体攻撃フラグを読むのは攻撃側の
    対象選択だけで、昇天弓の発射はそこを通らない）、状態を直接確認します。
    """
    assert card_feature(ASCENSION_BOW, "is_group_attack") is True, (
        "マスタ上で全体攻撃でないなら、このテストは前提から成り立たない"
    )

    power = card_feature(SAW, "attack_power")
    g = board(
        p0=Side(hp=40, mp=10, hand=[SAW]),
        p1=Side(hp=power, mp=10, hand=[ASCENSION_BOW]),
    )
    g.rng.deck_always(FILLER)
    g.rng.ascension_bow(True)

    g.attack(SAW)
    g.take_hit()
    g.take_hit()

    g.expect(phase=GamePhase.PHASE_DEFENSE, actor=0)
    assert g.state.pending_is_group_attack is True, (
        "マスタが全体攻撃なら、発射された昇天弓も全体攻撃であるべきです"
    )


@pytest.mark.parametrize(
    "roll",
    [godfield_core.ROLL_MIN, godfield_core.ROLL_MAX],
    ids=["抽選値の下端", "抽選値の上端"],
)
def test_dangerous_pestle_never_targets_a_dead_player(board, roll):
    """あぶないキネの対象が、生存しているプレイヤーだけから選ばれることを検証します。

    従来は100回試行して「一度も相手が対象にならなかった」ことを確認していました。
    これは「たまたま選ばれなかっただけ」の可能性を排除できません。

    生存者が1人しかいない場合、抽選の候補も1つしかないはずです。抽選値を範囲の
    下端・上端の両方に振っても同じ結果になることを確認すれば、候補が1つしかない
    ことを直接示せます（死者が候補に入っていれば、どちらかで選ばれてしまう）。
    """
    power = card_feature(PESTLE, "attack_power")
    g = board(
        p0=Side(hp=40, mp=10, hand=[PESTLE]),
        # P1 は死亡している。ウスを持っているが、死者のウスは無視されるべき
        p1=Side(hp=0, mp=10, hand=[MORTAR]),
    )
    g.rng.deck_always("armor/wood-shield")
    g.rng.force(RollKind.PESTLE_TARGET, roll)

    g.attack(PESTLE)

    # 唯一の生存者である自分自身が対象になり、自傷が適用される
    g.expect(p0_hp=40 - power, p1_hp=0, phase=GamePhase.PHASE_END)
    assert g.rng.consumed(RollKind.PESTLE_TARGET) == 1, "対象抽選が行われているべきです"


def test_attack_and_defense_work_from_any_hand_slot(board):
    """スロット0以外に置いたカードでも、重ねがけ攻撃・重ねがけ防御が成立することを検証します。

    実装がスロット0を特別扱いしていないかを確認するテストです。
    """
    gale = "weapons/gale-sword"       # 通常武器
    boomerang = "weapons/boomerang"   # プラス武器
    shield = "armor/wood-shield"
    clothes = "armor/leather-clothes"

    power = card_feature(gale, "attack_power") + card_feature(boomerang, "attack_power")
    guard = card_feature(shield, "defense_power") + card_feature(clothes, "defense_power")
    assert power > guard, "被弾0では加算されたかどうか分からない"

    # 手札の前方を空けて、スロット2/4 と 3/5 に置く
    g = board(
        p0=Side(hp=40, mp=10, hand=[None, None, gale, None, boomerang]),
        p1=Side(hp=40, mp=10, hand=[None, None, None, shield, None, clothes]),
    )
    g.rng.deck_always(FILLER)

    g.attack_slots(2, 4)
    g.expect(pending_power=power)

    g.select_slots(3, 5)
    g.confirm()

    g.expect(p1_hp=40 - (power - guard))


def test_a_normal_weapon_cannot_be_stacked_onto_a_plus_weapon(board):
    """プラス武器を先に置くと、あとから通常武器を重ねられないことを検証します。"""
    gale = "weapons/gale-sword"
    boomerang = "weapons/boomerang"

    g = board(
        p0=Side(hp=40, mp=10, hand=[None, None, gale, None, boomerang]),
        p1=Side(hp=40, mp=10),
    )
    g.rng.deck_always(FILLER)

    g.select_slots(4)  # 先にプラス武器
    g.expect_illegal([gale])

    g.target_opp()
    g.expect(pending_power=card_feature(boomerang, "attack_power"))


# ==========================================
# Merged from: tests/core/test_elemental_attacks.py
# ==========================================



ELEMENT_RULE_CASES = [
    # (ベース武器, プラス武器, 期待属性, 規則の説明)
    ("weapons/holy-sword", "weapons/piece-of-brightness", Element.ELEM_LIGHT,
     "光＋光は光のまま"),
    ("weapons/holy-sword", "weapons/fire-crossbow", Element.ELEM_FIRE,
     "光は中立なので他の属性が混ざるとその属性になる"),
    ("weapons/blaze-blade", "weapons/piece-of-brightness", Element.ELEM_FIRE,
     "光は中立なのでベースの火属性が維持される"),
    ("weapons/blaze-blade", "weapons/neolithic-tomahawk", Element.ELEM_NONE,
     "異なる通常属性同士（火＋土）は打ち消し合って無属性になる"),
    ("weapons/blaze-blade", "weapons/boomerang", Element.ELEM_NONE,
     "無属性が混ざると無属性になる"),
    ("weapons/boomerang", "weapons/fire-crossbow", Element.ELEM_NONE,
     "無属性ベースに有属性を足しても無属性のまま"),
    ("weapons/boomerang", "weapons/piece-of-brightness", Element.ELEM_NONE,
     "無属性ベースに光を足しても無属性のまま"),
    ("weapons/death-s-scythe", "weapons/piece-of-brightness", Element.ELEM_NONE,
     "光は闇の代わりになれないので無属性になる"),
    ("weapons/death-s-scythe", "weapons/abyss-dart", Element.ELEM_DARKNESS,
     "闇＋闇は闇のまま"),
    ("weapons/holy-sword", "weapons/abyss-dart", Element.ELEM_NONE,
     "光ベースに闇を足しても光は代わりになれず無属性になる"),
]


@pytest.mark.parametrize(
    ("base", "plus", "expected_element", "why"),
    ELEMENT_RULE_CASES,
    ids=[c[3] for c in ELEMENT_RULE_CASES],
)
def test_element_mixing_rules(board, base, plus, expected_element, why):
    """武器の重ねがけによる属性の混成規則を、10通りの組み合わせで検証します。

    従来は同じ手順を10個の関数にコピーして書いていたため、規則の全体像が見えず、
    抜けている組み合わせにも気付けませんでした。表にすることで
    「光は中立」「異なる通常属性は打ち消し合う」「無属性は伝播する」
    「光は闇の代わりにならない」という4つの規則が一望できます。

    攻撃力の合計もカードマスタから計算して検証します（従来は 11 や 15 といった
    数値がテストに直書きされており、マスタを変更しても追従しませんでした）。
    """
    g = board(
        p0=Side(hp=99, mp=50, money=50, hand=[base, plus]),
        p1=Side(hp=99, mp=50, money=50),
    )
    g.attack(base, plus)

    expected_power = card_feature(base, "attack_power") + card_feature(plus, "attack_power")
    g.expect(pending_element=expected_element, pending_power=expected_power)


def test_element_rule_table_covers_every_required_pair():
    """属性規則の表が主要な組み合わせを覆っていることを確認します。

    表から漏れた組み合わせが静かに未検証にならないよう、母集団側を固定します。
    """
    seen = {(element_of(base), element_of(plus)) for base, plus, _, _ in ELEMENT_RULE_CASES}
    required = {
        (Element.ELEM_LIGHT, Element.ELEM_LIGHT),
        (Element.ELEM_LIGHT, Element.ELEM_FIRE),
        (Element.ELEM_FIRE, Element.ELEM_LIGHT),
        (Element.ELEM_FIRE, Element.ELEM_STONE),
        (Element.ELEM_FIRE, Element.ELEM_NONE),
        (Element.ELEM_NONE, Element.ELEM_FIRE),
        (Element.ELEM_NONE, Element.ELEM_LIGHT),
        (Element.ELEM_DARKNESS, Element.ELEM_LIGHT),
        (Element.ELEM_DARKNESS, Element.ELEM_DARKNESS),
        (Element.ELEM_LIGHT, Element.ELEM_DARKNESS),
    }
    assert required <= seen, f"未検証の組み合わせがあります: {required - seen}"


def test_wand_of_mystic_water_overrides_the_base_element(board):
    """魔水のワンドが、ベース武器の属性（闇）を水属性に上書きすることを検証します。"""
    base = "weapons/pri-pri-pricker"  # ちくりんちょ（闇属性）
    wand = "weapons/wand-of-mystic-water"
    g = board(
        p0=Side(hp=99, mp=50, money=50, hand=[base, wand]),
        p1=Side(hp=50, mp=50, money=50),
    )
    g.rng.deck_always("armor/wood-shield")
    g.attack(base, wand)

    expected_power = card_feature(base, "attack_power") + card_feature(wand, "attack_power")
    g.expect(pending_element=Element.ELEM_WATER, pending_power=expected_power)

    g.take_hit()
    g.expect(p1_hp=50 - expected_power)


# ============================================================================
# 属性による防具のマスク規則
# ============================================================================


def test_elemental_defense_masks_same_element_armor(board):
    """火属性の攻撃には火属性防具を出せず、水属性防具と虹のカーテンが出せることを検証します。"""
    g = board(
        p0=Side(hp=40, hand=["weapons/blaze-blade"]),
        p1=Side(hp=40, mp=20,
                hand=["armor/flame-boots", "armor/ice-boots", "armor/rainbow-curtain"]),
    )
    g.attack("weapons/blaze-blade")

    g.expect_illegal(["armor/flame-boots"])
    g.expect_legal(["armor/ice-boots", "armor/rainbow-curtain"])


def test_rainbow_curtain_unmasks_every_armor(board):
    """虹のカーテンを1枚目に置くと、本来マスクされていた同属性防具も重ねられることを検証します。"""
    g = board(
        p0=Side(hp=40, hand=["weapons/blaze-blade"]),
        p1=Side(hp=40, mp=20,
                hand=["armor/flame-boots", "armor/ice-boots", "armor/rainbow-curtain"]),
    )
    g.attack("weapons/blaze-blade")
    g.select("armor/rainbow-curtain")

    g.expect_legal(["armor/flame-boots", "armor/ice-boots"])


def test_light_attack_only_allows_the_rainbow_curtain(board):
    """光属性の攻撃には通常の防具が一切出せず、虹のカーテンだけが出せることを検証します。

    防具は無・火・水・木・土の各属性から1枚ずつカードマスタで選び、属性ごとの網羅を保ちます。
    """
    armors = [
        armor_of_element(elem)
        for elem in (Element.ELEM_NONE, Element.ELEM_FIRE, Element.ELEM_WATER,
                     Element.ELEM_WOOD, Element.ELEM_STONE)
    ]
    g = board(
        p0=Side(hp=40, hand=["weapons/holy-sword"]),
        p1=Side(hp=40, mp=20, hand=[*armors, "armor/rainbow-curtain"]),
    )
    g.attack("weapons/holy-sword")

    g.expect_illegal(armors)
    g.expect_legal(["armor/rainbow-curtain"])

    # カーテンを置けば無属性防具が重ねられるようになる
    g.select("armor/rainbow-curtain")
    g.expect_legal([armors[0]])


# ============================================================================
# 闇属性の即死
# ============================================================================


def setup_incoming_darkness(g, power: int = 10):
    """闇属性攻撃を受けている防御フェイズを組み立てます（攻撃元は死神のカマ）。"""
    g.state.current_actor_id = 0
    g.state.current_phase = GamePhase.PHASE_DEFENSE
    g.state.attacker_id = 1
    g.state.defender_id = 0
    g.state.pending_attack_element = Element.ELEM_DARKNESS
    g.state.pending_attack_power = power
    g.state.pending_attack_source_id = card_id("weapons/death-s-scythe")
    return g


def test_darkness_attack_kills_instantly_when_undefended(board):
    """闇属性攻撃を防御せずに受けると、ダメージ量に関わらず即死することを検証します。"""
    g = setup_incoming_darkness(board(p0=Side(hp=40), p1=Side(hp=40)))
    g.take_hit()

    g.expect(p0_hp=0, is_done=True)


def test_darkness_attack_is_survivable_after_the_rainbow_curtain(board):
    """闇属性攻撃も虹のカーテンで無属性化すれば即死を免れることを検証します。"""
    g = setup_incoming_darkness(
        board(
            p0=Side(hp=40, mp=20, hand=["armor/rainbow-curtain", "armor/iron-shield"]),
            p1=Side(hp=40),
        )
    )
    g.rng.deck_always("armor/wood-shield")
    g.defend("armor/rainbow-curtain", "armor/iron-shield")

    g.expect(is_done=False)
    assert g.hp(0) > 0, "無属性化されていれば即死しないはずです"

# ==========================================
# Merged from: tests/core/test_group_attacks.py
# ==========================================



def test_mirage_turns_a_single_weapon_into_a_group_attack(board):
    """＜蜃気楼＞を重ねると単体武器攻撃が全体攻撃フェイズへ移り、重ねがけが制限されることを検証します。

    全体化後は他の物理武器を追加できず、自傷も選べなくなります。
    精霊のぬいぐるみだけは蜃気楼のMPを相殺するために追加できます。
    """
    g = board(
        p0=Side(hp=40, mp=10,
                hand=["weapons/bronze-club", "miracles/mirage",
                      "sundries/spiritual-doll", "weapons/blowgun"]),
        p1=Side(hp=40),
    )

    g.select("weapons/bronze-club")
    g.expect(phase=GamePhase.PHASE_ATTACK_PLUS)

    g.select("miracles/mirage")
    g.expect(phase=GamePhase.PHASE_GROUP_WEAPON, pending_is_group=True)

    # 全体化後は他の武器も自傷も選べず、精霊のぬいぐるみだけが重ねられる
    g.expect_illegal(["weapons/blowgun"])
    g.expect_legal(["sundries/spiritual-doll"])
    g.expect_actions(target_self=False, target_opp=True)

    g.attack("sundries/spiritual-doll")

    # ぬいぐるみが蜃気楼のMPを相殺するので消費0
    g.expect(phase=GamePhase.PHASE_DEFENSE, p0_mp=10)


def test_native_group_weapon_allows_no_stacking(board):
    """生来の全体攻撃武器は重ねがけを一切受け付けず、相手を狙うことしかできないことを検証します。"""
    g = board(
        p0=Side(hp=40, mp=20, hand=["weapons/spark-bag", "miracles/mirage", "weapons/blowgun"]),
        p1=Side(hp=40),
    )

    g.select("weapons/spark-bag")
    g.expect(phase=GamePhase.PHASE_GROUP_WEAPON)

    # 手札のどのスロットも選択できない
    legal = g.legal_actions()
    for idx in range(18):
        assert legal[int(ActionType.ACTION_SELECT_HAND_0) + idx] is False, (
            f"スロット{idx} は重ねられないべきです"
        )
    g.expect_actions(target_opp=True, target_self=False)

    g.target_opp()
    g.expect(phase=GamePhase.PHASE_DEFENSE)


def test_native_group_miracle_opens_the_miracle_defense_phase(board):
    """生来の全体奇跡は全体奇跡フェイズを経て、奇跡防御フェイズへ遷移することを検証します。"""
    g = board(p0=Side(hp=40, mp=20, hand=["miracles/smoke"]), p1=Side(hp=40))

    g.select("miracles/smoke")
    g.expect(phase=GamePhase.PHASE_GROUP_MIRACLE_PLUS)
    g.expect_actions(target_opp=True, target_self=False)

    g.target_opp()
    g.expect(phase=GamePhase.PHASE_MIRACLE_DEFENSE)


def test_miracle_plus_then_mirage_keeps_the_miracle_mp_cost(board):
    """武器＋奇跡プラス＋蜃気楼＋ぬいぐるみで、奇跡のMPだけが消費されることを検証します。

    ぬいぐるみは直前の蜃気楼のMPを相殺しますが、その前の火の玉のMPは残ります。
    """
    g = board(
        p0=Side(hp=40, mp=20,
                hand=["weapons/punch", "miracles/fireball",
                      "miracles/mirage", "sundries/spiritual-doll"]),
        p1=Side(hp=40),
    )

    g.select("weapons/punch")
    g.expect(phase=GamePhase.PHASE_ATTACK_PLUS)
    g.select("miracles/fireball")
    g.expect(phase=GamePhase.PHASE_ATTACK_PLUS)
    g.select("miracles/mirage")
    g.expect(phase=GamePhase.PHASE_GROUP_WEAPON)

    g.attack("sundries/spiritual-doll")

    fireball_mp = card_feature("miracles/fireball", "mp_cost")
    g.expect(phase=GamePhase.PHASE_DEFENSE, p0_mp=20 - fireball_mp)


def test_mirage_disables_self_targeting(board):
    """蜃気楼を重ねた時点で自傷が選べなくなることを、重ねる前後で比較して検証します。"""
    g = board(p0=Side(hp=40, mp=10, hand=["weapons/punch", "miracles/mirage"]), p1=Side(hp=40))

    g.select("weapons/punch")
    g.expect(phase=GamePhase.PHASE_ATTACK_PLUS, pending_is_group=False)
    g.expect_actions(target_self=True)  # 蜃気楼を重ねる前は自傷できる

    g.select("miracles/mirage")

    g.expect(pending_is_group=True)
    g.expect_actions(target_self=False)


def test_stacked_mirages_multiply_the_attack_count(board):
    """蜃気楼を3枚重ねると攻撃回数が3回になり、MPは相殺分を除いて消費されることを検証します。

    パンチ → 蜃気楼 → 蜃気楼 → 精霊 → 蜃気楼 の順で、精霊は直前の蜃気楼を相殺します。
    """
    mirage_mp = card_feature("miracles/mirage", "mp_cost")
    g = board(
        p0=Side(hp=40, mp=30,
                hand=["weapons/punch", "miracles/mirage", "miracles/mirage",
                      "sundries/spiritual-doll", "miracles/mirage"]),
        p1=Side(hp=40),
    )

    g.select_slots(0)
    g.expect(phase=GamePhase.PHASE_ATTACK_PLUS)
    for slot in (1, 2, 3, 4):
        g.select_slots(slot)
        g.expect(phase=GamePhase.PHASE_GROUP_WEAPON)

    g.target_opp()

    # 蜃気楼1枚目=消費、2枚目=消費、精霊が3枚目を相殺 -> 合計 2 枚分
    g.expect(phase=GamePhase.PHASE_DEFENSE, p0_mp=30 - mirage_mp * 2)
    assert g.state.remaining_attacks == 3


def test_native_group_weapon_cannot_be_boosted_by_mirage(board):
    """生来の全体攻撃武器に蜃気楼を重ねられないことを検証します。"""
    g = board(
        p0=Side(hp=40, mp=20, hand=["weapons/spark-bag", "miracles/mirage"]),
        p1=Side(hp=40),
    )

    g.select("weapons/spark-bag")
    g.expect(phase=GamePhase.PHASE_GROUP_WEAPON)
    g.expect_illegal(["miracles/mirage"])


# ==========================================
# Merged from: tests/core/test_spiritual_stacking.py
# ==========================================



# 奇跡のMP消費を0にする「精霊の神器」5種。C++ の is_spiritual_zero_mp_card と対応する。
# 従来はぬいぐるみと足袋の2種しか検証されておらず、杖・頭巾・帯は未検証だった。
SPIRITUAL_CARDS = [
    "weapons/spiritual-staff",
    "armor/spiritual-socks",
    "armor/spiritual-hood",
    "armor/spiritual-sash",
    "sundries/spiritual-doll",
]


@pytest.mark.parametrize("spirit", SPIRITUAL_CARDS)
def test_spiritual_card_zeroes_the_miracle_mp_cost(board, spirit):
    """精霊の神器5種すべてが、直前の奇跡のMP消費を0にすることを検証します。

    重ねた後も奇跡防御フェイズへ遷移する（武器攻撃にはならない）ことも確認します。
    """
    mp_before = card_feature("miracles/fireball", "mp_cost")
    g = board(
        p0=Side(hp=40, mp=mp_before, hand=["miracles/fireball", spirit]),
        p1=Side(hp=40),
    )

    g.select("miracles/fireball")
    g.expect(phase=GamePhase.PHASE_MIRACLE_PLUS)
    g.expect_legal([spirit])

    g.select(spirit)
    g.target_opp()

    g.expect(phase=GamePhase.PHASE_MIRACLE_DEFENSE, p0_mp=mp_before)


@pytest.mark.parametrize("has_spirit", [True, False], ids=["精霊あり", "精霊なし"])
def test_high_cost_miracle_is_selectable_only_with_a_spiritual_card(board, has_spirit):
    """MPが足りない高コスト奇跡は、精霊の神器を手札に持つ場合のみ選択できることを検証します。"""
    miracle = "miracles/darkness"
    mp = card_feature(miracle, "mp_cost") - 3  # 明確に不足させる
    hand = [miracle] + (["sundries/spiritual-doll"] if has_spirit else [])
    g = board(p0=Side(hp=40, mp=mp, hand=hand), p1=Side(hp=40))

    if has_spirit:
        g.expect_legal([miracle])
    else:
        g.expect_illegal([miracle])


def test_high_cost_miracle_cannot_be_confirmed_before_adding_the_spirit(board):
    """高コスト奇跡を仮置きしただけでは、精霊を重ねるまで対象を決められないことを検証します。"""
    miracle = "miracles/darkness"
    mp = card_feature(miracle, "mp_cost") - 3
    g = board(
        p0=Side(hp=40, mp=mp, hand=[miracle, "sundries/spiritual-doll"]),
        p1=Side(hp=40),
    )

    g.select(miracle)
    # MPが足りないままなので対象決定は不可
    g.expect_actions(target_opp=False)

    g.select("sundries/spiritual-doll")
    # 精霊で相殺されたので対象決定が解禁される
    g.expect_actions(target_opp=True)

    g.target_opp()
    g.expect(phase=GamePhase.PHASE_MIRACLE_DEFENSE, p0_mp=mp)


def test_spiritual_card_list_matches_the_cpp_predicate(board):
    """精霊の神器の一覧が C++ の判定と一致していることを、実際の相殺挙動で確認します。

    テストの母集団が実装からずれると、増えた精霊カードが黙って未検証になります。
    ここでは「名前に精霊を含むカード」を母集団にして、全件が相殺することを確かめます。
    """
    named_spiritual = [
        c["id_str"]
        for c in all_cards()
        if "精霊" in (c.get("name") or "") and c.get("id_str")
    ]
    assert set(named_spiritual) == set(SPIRITUAL_CARDS), (
        f"精霊カードの一覧がずれています: {sorted(set(named_spiritual) ^ set(SPIRITUAL_CARDS))}"
    )


# ==========================================
# 全体攻撃カードの状態異常付与
# ==========================================


def _group_attack_cards_with_curse() -> list[dict]:
    """全体攻撃かつ状態異常を与えるカード（守護神の行動を除く）をマスタから集めます。

    守護神の行動は setup_guardian_attack_defense() が set_pending_attack() で
    全フィールドを設定する別経路なので、ここでは除きます。
    """
    return [
        c
        for c in all_cards()
        if c.get("is_group_attack")
        and c.get("hit_curse")
        and not (c.get("id_str") or "").startswith("gurdians/")
    ]


_HIT_CURSE_TO_STATE = {
    "fog": godfield_core.CurseType.CURSE_FOG,
    "flash": godfield_core.CurseType.CURSE_FLASH,
    "dark_cloud": godfield_core.CurseType.CURSE_DARK_CLOUD,
    "dream": godfield_core.CurseType.CURSE_DREAM,
}

_HIT_CURSE_TO_SICKNESS = {
    "cold": godfield_core.SicknessType.SICKNESS_COLD,
    "fever": godfield_core.SicknessType.SICKNESS_FEVER,
    "hell": godfield_core.SicknessType.SICKNESS_HELL,
    "heaven": godfield_core.SicknessType.SICKNESS_HEAVEN,
}


@pytest.mark.parametrize(
    "card_data",
    _group_attack_cards_with_curse(),
    ids=lambda c: c["id_str"],
)
def test_group_attack_applies_its_hit_curse(board, card_data):
    """全体攻撃カードでも、命中した相手に状態異常が付くことを検証します。

    全体攻撃には専用の解決経路（step_phase_group_attack）があり、通常攻撃・
    奇跡攻撃の経路が設定している pending_attack_curse だけが漏れていました。
    そのため霧の扇（霧）も＜閃光＞（閃光）も、当たっても状態異常が一切
    付きませんでした。既存テストは1件も落ちなかったため、誰も見ていませんでした。

    カードを名指しせずマスタから集めるので、全体攻撃かつ状態異常を持つカードが
    増えても自動で検証対象に入ります。
    """
    card = card_data["id_str"]
    curse = card_data["hit_curse"]

    g = board(
        p0=Side(hp=99, mp=99, hand=[card]),
        p1=Side(hp=99, mp=99, hand=[]),
    )
    g.rng.deck_always(FILLER)
    g.rng.hits(always=True, optional=True)

    g.attack(card)
    g.take_hit()

    if curse in _HIT_CURSE_TO_STATE:
        g.expect(p1_curses={_HIT_CURSE_TO_STATE[curse]})
    else:
        g.expect(p1_sickness=_HIT_CURSE_TO_SICKNESS[curse])
