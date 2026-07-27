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
from tests.core.dsl import Side, card_feature, card_id, ev
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
