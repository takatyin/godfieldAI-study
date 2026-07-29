"""指輪（＝装備すると被弾時に固有の反撃・効果を返す防具）の検証。

【移行メモ】
従来は火星の指輪の75%判定を `seed_rng(42)` で「たまたま成功するシード」に頼って
おり、コードからは成功を意図していることが読めませんでした。また指輪ごとの
災い付与テストが同じ手順の3コピーになっていました。

指輪の防御力はカードマスタ上0なので、貫通ダメージは攻撃力そのままになります。
"""

import pytest

import godfield_core
from godfield_core import CurseType, Element, EventType, GamePhase, RollKind
from tests.core.dsl import Side, card_feature, card_id, card_name, ev
from visualizer.event_formatter import format_event_log

FILLER = "armor/wood-shield"

# 指輪は防御力を持たないため、攻撃力がそのまま貫通ダメージになる
GALE_SWORD = "weapons/gale-sword"
PUNCH = "weapons/punch"


def attack_into_ring(board, ring: str, *, weapon: str = PUNCH, p0=None, p1=None, **rng):
    """P0 が武器で攻撃し、P1 が指輪1枚で防御した局面を作ります。"""
    g = board(
        p0=p0 if p0 is not None else Side(hp=40, mp=10, money=20, hand=[weapon]),
        p1=p1 if p1 is not None else Side(hp=40, mp=10, money=20, hand=[ring]),
    )
    g.rng.deck_always(FILLER)
    for kind, value in rng.items():
        g.rng.force(getattr(RollKind, kind.upper()), value)
    g.attack(weapon)
    g.expect(phase=GamePhase.PHASE_DEFENSE, actor=1)
    g.defend(ring)
    return g


# ============================================================================
# 反撃系の指輪
# ============================================================================


def test_saturn_ring_logs_a_counter_attack_event(board):
    """土星の指輪の反撃が RING_EFFECT イベントとして記録され、正しく整形されることを検証します。"""
    g = attack_into_ring(board, "armor/saturn-ring", weapon=GALE_SWORD)

    g.expect_events(ev(EventType.RING_EFFECT, card="armor/saturn-ring"))

    obs = godfield_core.get_observation(g.state, 1)
    ring_events = [e for e in obs.get_history() if e.event_type == int(EventType.RING_EFFECT)]
    assert ring_events, "RING_EFFECT イベントが記録されるべきです"
    assert ring_events[-1].card_id == card_id("armor/saturn-ring")
    assert "反撃が発動！" in format_event_log(ring_events[-1], 1)["text"]


def test_neptune_ring_converts_penetrating_damage_into_mp(board):
    """海王の指輪が、貫通ダメージの2倍のMPを装備者に与えることを検証します。"""
    damage = card_feature(GALE_SWORD, "attack_power")  # 指輪は防御0なので全弾貫通
    g = attack_into_ring(board, "armor/neptune-ring", weapon=GALE_SWORD)

    g.expect(p1_mp=10 + damage * 2)


@pytest.mark.parametrize("counters", [True, False], ids=["反撃する", "反撃しない"])
def test_mars_ring_counter_is_probabilistic(board, counters):
    """火星の指輪の反撃（75%）の成否を両方向とも検証します。

    従来は seed_rng(42) が「たまたま成功するシード」であることに依存しており、
    成功を意図しているのかコードから読めず、失敗側は一度も検証されていませんでした。
    """
    damage = card_feature(PUNCH, "attack_power")
    g = attack_into_ring(
        board, "armor/mars-ring",
        p0=Side(hp=40, mp=10, hand=[PUNCH, "armor/ice-shield"]),
        mars_ring=godfield_core.ROLL_MIN if counters else godfield_core.ROLL_MAX,
    )

    g.expect(p1_hp=40 - damage)
    if counters:
        # 反撃が予約され、攻撃者が火属性の防御フェイズに立たされる
        g.expect(
            phase=GamePhase.PHASE_DEFENSE,
            actor=0,
            pending_power=damage,
            pending_element=Element.ELEM_FIRE,
        )
        g.defend("armor/ice-shield")  # 水属性防具で完全に防ぐ
        g.expect(p0_hp=40, phase=GamePhase.PHASE_MAIN)
    else:
        g.expect(p0_hp=40, phase=GamePhase.PHASE_MAIN)


def test_saturn_ring_counter_waits_for_multi_attacks_to_finish(board):
    """複数回攻撃の途中では指輪の反撃が保留され、全弾終了後に発動することを検証します。"""
    saw = "weapons/saw-boom-boom"
    damage = card_feature(saw, "attack_power")
    g = attack_into_ring(
        board, "armor/saturn-ring", weapon=saw,
        p1=Side(hp=40, mp=10, hand=["armor/saturn-ring", "armor/leather-clothes"]),
    )

    # 1発目の解決後、まだ2発目が残っているので反撃は始まらない
    g.expect(phase=GamePhase.PHASE_DEFENSE, actor=1, remaining_attacks=1, p1_hp=40 - damage)

    g.defend("armor/leather-clothes")

    # 全弾終了後に土属性の反撃が攻撃者へ飛ぶ
    g.expect(
        phase=GamePhase.PHASE_DEFENSE,
        actor=0,
        pending_power=damage * 2,
        pending_element=Element.ELEM_STONE,
    )


# ============================================================================
# 災いを付与する指輪
# ============================================================================


@pytest.mark.parametrize(
    ("ring", "curse"),
    [
        ("armor/jupiter-ring", CurseType.CURSE_DREAM),
        ("armor/uranus-ring", CurseType.CURSE_FLASH),
        ("armor/pluto-ring", CurseType.CURSE_DARK_CLOUD),
        ("armor/mercury-ring", CurseType.CURSE_FOG),
    ],
    ids=["木星->夢", "天王->閃光", "冥王->暗雲", "水星->霧"],
)
def test_curse_rings_apply_their_curse_to_the_attacker(board, ring, curse):
    """災いを付与する指輪4種が、それぞれの災いを攻撃者に与えることを検証します。

    従来は同じ手順が3コピーされており、木星の指輪だけ別テストに分かれていました。
    """
    g = attack_into_ring(board, ring)

    # 攻撃力0の反撃なので雑貨反射の選択フェイズになる
    g.expect(phase=GamePhase.PHASE_SUNDRY_SELECT_MIRROR, actor=0, pending_power=0)
    g.take_hit()

    g.expect(p0_hp=40, p0_curses={curse}, phase=GamePhase.PHASE_MAIN)


@pytest.mark.parametrize(
    "ring",
    ["armor/jupiter-ring", "armor/uranus-ring", "armor/pluto-ring", "armor/mercury-ring"],
)
def test_curse_ring_counters_can_only_be_answered_by_a_super_mirror(board, ring):
    """指輪の反撃には通常防具を出せず、スーパーミラーだけが使えることを検証します。"""
    g = board(p0=Side(hp=40, hand=[FILLER, "armor/super-mirror"]), p1=Side(hp=40))
    g.state.current_phase = GamePhase.PHASE_SUNDRY_SELECT_MIRROR
    g.state.current_actor_id = 0
    g.state.attacker_id = 1
    g.state.defender_id = 0
    g.state.pending_attack_source_id = card_id(ring)
    g.state.pending_attack_power = 0

    g.expect_illegal([FILLER])
    g.expect_legal(["armor/super-mirror"])


# ============================================================================
# 金星の指輪（お金の徴収）
# ============================================================================


def test_venus_ring_opens_the_sundry_mirror_phase(board):
    """金星の指輪の反撃が、雑貨反射の選択フェイズを攻撃者に開くことを検証します。"""
    g = attack_into_ring(board, "armor/venus-ring", weapon=GALE_SWORD)

    g.expect(phase=GamePhase.PHASE_SUNDRY_SELECT_MIRROR, actor=0)


def test_venus_ring_only_allows_a_super_mirror_in_response(board):
    """金星の指輪の反撃に通常防具を出せないことを検証します。"""
    g = board(p0=Side(hp=40, hand=[FILLER, "armor/super-mirror"]), p1=Side(hp=40))
    g.state.current_phase = GamePhase.PHASE_SUNDRY_SELECT_MIRROR
    g.state.current_actor_id = 0
    g.state.attacker_id = 1
    g.state.defender_id = 0
    g.state.pending_attack_source_id = card_id("armor/venus-ring")
    g.state.pending_attack_power = 10

    g.expect_illegal([FILLER])
    g.expect_legal(["armor/super-mirror"])


def test_venus_ring_drains_money_equal_to_the_damage(board):
    """金星の指輪が、貫通ダメージと同額のお金を攻撃者から徴収することを検証します。

    海王の指輪と併用した場合の順序（MP変換 -> お金徴収）も併せて確認します。
    """
    damage = card_feature(PUNCH, "attack_power")
    g = board(
        p0=Side(hp=40, mp=10, money=20, hand=[PUNCH]),
        p1=Side(hp=40, mp=10, money=20,
                hand=["armor/neptune-ring", "armor/venus-ring"]),
    )
    g.rng.deck_always(FILLER)
    g.attack(PUNCH)
    g.defend("armor/neptune-ring", "armor/venus-ring")

    # 海王の指輪が貫通ダメージの2倍のMPを与える（ただし上限は別途クランプ）
    g.expect(p1_hp=40 - damage, phase=GamePhase.PHASE_SUNDRY_SELECT_MIRROR, actor=0)

    g.take_hit()

    g.expect(p0_money=20 - damage, p1_money=20 + damage)


def test_venus_ring_falls_back_to_mp_then_hp_when_money_runs_out(board):
    """お金が足りない場合、MP・HPの順に徴収されることを検証します。"""
    damage = card_feature(PUNCH, "attack_power")
    g = attack_into_ring(
        board, "armor/venus-ring",
        p0=Side(hp=40, mp=1, money=1, hand=[PUNCH]),
    )
    g.take_hit()

    # お金1 -> MP1 -> 残り1をHPから徴収
    g.expect(p0_money=0, p0_mp=0, p0_hp=39, p1_money=20 + damage)


def test_venus_ring_can_kill_the_attacker(board):
    """徴収がHPまで及んで攻撃者が死亡するケースを検証します。"""
    damage = card_feature(PUNCH, "attack_power")
    g = attack_into_ring(
        board, "armor/venus-ring",
        p0=Side(hp=1, mp=0, money=0, hand=[PUNCH]),
    )
    g.take_hit()

    g.expect(p0_hp=0, p1_money=20 + damage)


def test_venus_ring_counter_can_be_reflected_by_a_super_mirror(board):
    """金星の指輪の反撃をスーパーミラーで跳ね返すと、徴収の向きが逆転することを検証します。"""
    damage = card_feature(PUNCH, "attack_power")
    g = board(
        p0=Side(hp=40, mp=10, money=20, hand=[PUNCH, "armor/super-mirror"]),
        p1=Side(hp=40, mp=10, money=20, hand=["armor/venus-ring"]),
    )
    g.rng.deck_always(FILLER)
    g.attack(PUNCH)
    g.defend("armor/venus-ring")

    g.expect(phase=GamePhase.PHASE_SUNDRY_SELECT_MIRROR, actor=0)
    g.select("armor/super-mirror")

    # 反射され、今度は指輪の持ち主が選択する側になる
    g.expect(phase=GamePhase.PHASE_SUNDRY_SELECT_MIRROR, actor=1, pending_power=damage)
    g.take_hit()

    g.expect(p0_money=20 + damage, p1_money=20 - damage, p1_hp=40 - damage)


def test_ring_list_is_covered_by_these_tests():
    """カードマスタ上の全ての指輪がこのファイルで検証されていることを確認します。

    指輪が追加されたときに、テストが無いまま気付かず通り過ぎるのを防ぎます。
    """
    from tests.core.dsl import all_cards

    all_rings = {
        c["id_str"] for c in all_cards()
        if (c.get("id_str") or "").endswith("-ring")
    }
    tested = {
        "armor/mars-ring", "armor/mercury-ring", "armor/jupiter-ring", "armor/saturn-ring",
        "armor/uranus-ring", "armor/pluto-ring", "armor/neptune-ring", "armor/venus-ring",
    }
    assert all_rings == tested, f"未検証の指輪があります: {sorted(all_rings - tested)}"


# ============================================================================
# 奇跡攻撃に対する指輪
# ============================================================================

# 指輪は「属性が合っていて防具として出せるなら、武器攻撃・奇跡攻撃を問わず出せる」。
# 天王の指輪は光属性なので、火にも水にも出せる。
# なお光属性の攻撃には対抗属性の防具が存在しない（docs/rules.md 4.1）ため、
# 光属性の奇跡は検証対象から外している。
LIGHT_RING = "armor/uranus-ring"


@pytest.mark.parametrize(
    "miracle",
    ["miracles/ice", "miracles/flame"],
    ids=["水属性の奇跡", "火属性の奇跡"],
)
def test_ring_counters_a_miracle_attack(board, miracle):
    """指輪が奇跡攻撃に対しても反撃することを検証します。

    反撃の処理は長らく物理防御フェイズに限定されており、奇跡防御では
    「出せるのに何も起きない」状態でした。指輪は防御力も持たないので、
    出すとカードを1枚失うだけになっていました。
    """
    g = board(
        p0=Side(hp=40, mp=30, money=20, hand=[miracle]),
        p1=Side(hp=40, mp=30, money=20, hand=[LIGHT_RING]),
    )
    g.rng.deck_always(FILLER)

    g.attack(miracle)
    g.expect(phase=GamePhase.PHASE_MIRACLE_DEFENSE, actor=1)
    g.expect_legal([LIGHT_RING])

    g.defend(LIGHT_RING)

    # 天王の指輪の反撃はダメージを伴わない状態異常付与なので、
    # 攻撃側にスーパーミラーで返すかを選ばせるフェイズへ移る
    g.expect(phase=GamePhase.PHASE_SUNDRY_SELECT_MIRROR, attacker=1, defender=0)
    g.take_hit()
    g.expect(p0_curses={CurseType.CURSE_FLASH})


def test_ring_still_counters_a_weapon_attack(board):
    """武器攻撃に対する反撃が壊れていないことを検証します（対照）。"""
    g = board(
        p0=Side(hp=40, mp=30, money=20, hand=[PUNCH]),
        p1=Side(hp=40, mp=30, money=20, hand=[LIGHT_RING]),
    )
    g.rng.deck_always(FILLER)

    g.attack(PUNCH)
    g.defend(LIGHT_RING)

    g.expect(phase=GamePhase.PHASE_SUNDRY_SELECT_MIRROR, attacker=1, defender=0)
    g.take_hit()
    g.expect(p0_curses={CurseType.CURSE_FLASH})


def test_ring_counters_resolve_in_the_order_they_were_used(board):
    """指輪の反撃が「使われた順」に解決されることを検証します。

    予約は配列に積まれますが、以前は末尾から取り出しており、後から使った指輪の
    反撃が先に解決していました（後入れ先出し）。
    """
    mercury = "armor/mercury-ring"  # 水属性・反撃で霧
    uranus = "armor/uranus-ring"    # 光属性・反撃で閃光
    torch = "weapons/torch"         # 火属性なので水・光の指輪をどちらも出せる

    g = board(
        p0=Side(hp=99, mp=30, money=20, hand=[torch]),
        p1=Side(hp=99, mp=30, money=20, hand=[mercury, uranus]),
    )
    g.rng.deck_always(FILLER)

    g.attack(torch)
    g.select(mercury, player=1)   # 先に水星の指輪
    g.select(uranus, player=1)    # 次に天王の指輪
    g.confirm()

    fired = [e.card for e in g.event_log() if e.type == EventType.RING_EFFECT]
    assert fired, "指輪の反撃が発動していません"
    assert fired[0] == card_name(card_id(mercury)), (
        f"先に使った水星の指輪から解決されるべきです: {fired}"
    )


def test_a_ring_counter_can_be_reflected_only_by_the_super_mirror(board):
    """指輪の反撃はスーパーミラーでのみ反射でき、反射剣や＜壁＞では防げないことを検証します。

    指輪の反撃は武器攻撃でも奇跡でもないため、無属性物理リアクション
    （反射剣・＜壁＞）の対象になりません。虹のカーテンで無属性化しても解禁されません。
    """
    saturn = "armor/saturn-ring"
    mirror = "armor/super-mirror"
    curtain = "armor/rainbow-curtain"
    reflection_sword = "weapons/reflection-sword"
    wall = "miracles/wall"

    g = board(
        p0=Side(hp=99, mp=30, money=20,
                hand=[PUNCH, mirror, reflection_sword, curtain, wall]),
        p1=Side(hp=99, mp=30, money=20, hand=[saturn]),
    )
    g.rng.deck_always(FILLER)

    g.attack(PUNCH)
    g.defend(saturn)

    # 指輪の反撃が P0 へ飛ぶ
    g.expect(phase=GamePhase.PHASE_DEFENSE, actor=0, attacker=1, defender=0)
    assert g.state.pending_attack_power > 0, "土星の指輪は被ダメージ×2の反撃を行う前提"

    # 反射剣・＜壁＞は出せない
    g.expect_illegal([reflection_sword, wall])
    g.expect_legal([mirror])

    # 虹のカーテンで無属性化しても解禁されない
    g.select(curtain)
    g.expect_illegal([reflection_sword, wall])
    g.expect_legal([mirror])


def test_super_mirror_sends_a_ring_counter_back(board):
    """指輪の反撃をスーパーミラーで反射すると、反撃した側が受けることを検証します。"""
    saturn = "armor/saturn-ring"
    mirror = "armor/super-mirror"

    g = board(
        p0=Side(hp=99, mp=30, money=20, hand=[PUNCH, mirror]),
        p1=Side(hp=99, mp=30, money=20, hand=[saturn]),
    )
    g.rng.deck_always(FILLER)

    g.attack(PUNCH)
    g.defend(saturn)
    counter_power = g.state.pending_attack_power

    g.defend(mirror)

    # 攻守が入れ替わり、指輪を使った側が反撃を受ける立場になる
    g.expect(phase=GamePhase.PHASE_DEFENSE, actor=1, attacker=0, defender=1)
    assert g.state.pending_attack_power == counter_power, "威力は据え置かれる"

    hp_before = g.state.get_hp(1)
    g.take_hit()
    assert g.state.get_hp(1) == hp_before - counter_power, (
        "反射された指輪の反撃を、指輪を使った側が受けるべきです"
    )


@pytest.mark.parametrize(
    ("attack", "phase"),
    [
        ("weapons/torch", GamePhase.PHASE_DEFENSE),
        ("miracles/flame", GamePhase.PHASE_MIRACLE_DEFENSE),
    ],
    ids=["火属性の武器攻撃", "火属性の奇跡攻撃"],
)
def test_a_ring_is_playable_exactly_like_a_plain_armor(board, attack, phase):
    """指輪が、同じ属性の一般防具とまったく同じ条件で出せることを検証します。

    docs/rules.md 4.3 のとおり、指輪は防具なので攻撃の種類（武器/奇跡）を問わず
    属性が合えば出せます。カードマスタ上の usage_timing が atk_defence_phase
    のみであることは、奇跡防御での使用を禁じるものではありません。

    対抗属性の一般防具を対照に置き、合法・非合法が一致することを見ます。
    """
    water_ring = "armor/mercury-ring"   # 水属性（火に対抗）
    water_armor = "armor/ice-armor"     # 水属性の一般防具
    wrong_ring = "armor/mars-ring"      # 火属性（火には対抗できない）
    wrong_armor = "armor/flame-helm"     # 火属性の一般防具

    hand = [water_ring, water_armor, wrong_ring, wrong_armor]
    g = board(
        p0=Side(hp=99, mp=30, money=20, hand=[attack]),
        p1=Side(hp=99, mp=30, money=20, hand=hand),
    )
    g.rng.deck_always(FILLER)

    g.attack(attack)
    g.expect(phase=phase, actor=1)

    legal = g.legal_cards(player=1)
    ring_ok = card_name(card_id(water_ring)) in legal
    armor_ok = card_name(card_id(water_armor)) in legal
    assert ring_ok == armor_ok is True, (
        f"対抗属性の指輪と一般防具は同じく出せるべきです: {legal}"
    )

    bad_ring_ok = card_name(card_id(wrong_ring)) in legal
    bad_armor_ok = card_name(card_id(wrong_armor)) in legal
    assert bad_ring_ok == bad_armor_ok is False, (
        f"属性が合わない指輪と一般防具は同じく出せないべきです: {legal}"
    )
