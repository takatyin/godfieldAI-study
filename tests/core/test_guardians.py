"""守護神（地球神・月神）の行動検証。

【移行メモ】
以前はここが最も重いシード総当たり探索を抱えていました（地球神があぶないキネを
引くシードを探すために最大 100,000 回のシミュレーション）。探索が空振りしても
テストが通ってしまうため、`test_earth_dangerous_pestle_mortar` は
「シードが見つかった」以外に何も検証しない空のテストに退化していました。

現在は RollKind で
  - 守護神が行動するか（GUARDIAN_ACT）
  - 地球神が山札から何を引くか（DECK_DRAW）
  - 月神がどの奇跡を発動するか（MOON_MIRACLE）
を直接指示するため、探索は不要で、どの分岐を検証しているかがコードから読めます。
"""

import pytest

import godfield_core
from godfield_core import ActionType, Element, GamePhase, RollKind, SicknessType
from tests.core.dsl import (
    Game,
    Side,
    card_feature,
    card_id,
    card_name,
    element_of,
    ev,
)

EARTH = int(godfield_core.GuardianType.EARTH)
MOON = int(godfield_core.GuardianType.MOON)
JUPITER = int(godfield_core.GuardianType.JUPITER)

# 補充ドローで盤面が動かないようにするための無害なカード。
# 木の盾は防具なので手札に加わるだけで、フェイズ遷移も状態異常も起こさない。
FILLER = "armor/wood-shield"


def earth_turn(
    drawn: str,
    *,
    p0: Side | None = None,
    p1: Side | None = None,
    exchange_hp: int | None = None,
    exchange_mp: int | None = None,
    filler: str = FILLER,
) -> Game:
    """P1 に地球神を憑依させ、P0 が祈ってターンを終え、地球神が `drawn` を引いた局面を作ります。

    山札は「P0 の祈るドロー」「地球神のドロー」の順に消費されるため、
    先頭に無害なカードを1枚置いてから目的のカードを指定します（実測で確認済み）。
    ターン終了時のクリーンアップでも補充ドローが走るので、以降は `filler` で埋めます。
    破棄されたスロットが補充で埋まると検証が誤魔化されるため、破棄を検証する
    テストは盤面に無いカードを `filler` に指定してください。
    """
    g = Game(
        p0=p0 if p0 is not None else Side(hp=99, mp=10, money=10, hand=[FILLER]),
        p1=p1 if p1 is not None else Side(hp=40, mp=10, money=10, guardian=EARTH, hand=[FILLER]),
    )
    g.rng.guardian_act(acts=True)
    g.rng.next_draws(filler, drawn, then=filler)
    if exchange_hp is not None:
        g.rng.force(RollKind.EARTH_EXCHANGE_HP, exchange_hp)
    if exchange_mp is not None:
        g.rng.force(RollKind.EARTH_EXCHANGE_MP, exchange_mp)
    g.pray()
    return g


def moon_turn(miracle: str, *, p0: Side | None = None, p1: Side | None = None) -> Game:
    """P1 に月神を憑依させ、P0 が祈ってターンを終え、月神が `miracle` を発動した局面を作ります。"""
    g = Game(
        p0=p0 if p0 is not None else Side(hp=99, mp=10, money=10, hand=[FILLER]),
        p1=p1 if p1 is not None else Side(hp=40, mp=10, money=10, guardian=MOON, hand=[FILLER]),
    )
    g.rng.guardian_act(acts=True)
    g.rng.moon_miracle(miracle)
    g.rng.deck_always(FILLER)
    g.pray()
    return g


# ============================================================================
# 守護神が行動するかどうかの判定そのもの
# ============================================================================


@pytest.mark.parametrize("acts", [True, False], ids=["行動する", "行動しない"])
def test_guardian_acts_only_when_the_roll_succeeds(board, acts):
    """守護神の行動判定（25%）の成功・失敗の両分岐を検証します。

    従来は成功側だけを偶然のシードで引き当てており、「行動しない」側は
    どのテストも踏んでいませんでした。
    """
    g = board(
        p0=Side(hp=99, hand=[FILLER]),
        p1=Side(hp=40, guardian=MOON, hand=[FILLER]),
    )
    g.rng.guardian_act(acts=acts)
    g.rng.deck_always(FILLER)
    if acts:
        g.rng.moon_miracle("miracles/spring")  # HP+10 で発動を観測する
    g.pray()

    g.expect(p1_hp=50 if acts else 40)
    assert g.rng.consumed(RollKind.GUARDIAN_ACT) == 1


def test_guardian_does_not_act_when_owner_is_dead(board):
    """守護神の持ち主が死亡している場合は行動判定自体が行われないことを検証します。"""
    g = board(
        p0=Side(hp=99, hand=["weapons/dangerous-pestle"]),
        p1=Side(hp=1, guardian=MOON, hand=[]),
    )
    # 決着するので手札補充のドローは発生しない（DECK_DRAW を指示すると空振りになる）
    g.rng.guardian_leave(leaves=False)
    g.attack("weapons/dangerous-pestle")
    g.take_hit()  # P1 は防御せず 30 ダメージで死亡

    g.expect(p1_hp=0, is_done=True)
    assert g.rng.consumed(RollKind.GUARDIAN_ACT) == 0


# ============================================================================
# 地球神 (Earth): 引いたカードの種類ごとの分岐
# ============================================================================


def test_earth_exchange_redistributes_stats_keeping_the_sum(board):
    """地球神: 両替。HP/MP/お金の合計が保存され、指示した配分になることを検証します。"""
    g = earth_turn("deals/exchange", exchange_hp=25, exchange_mp=20)

    # 合計 40+10+10 = 60 を保ったまま、指示どおり HP25 / MP20 / お金15 に分配される
    g.expect(p1_hp=25, p1_mp=20, p1_money=15, phase=GamePhase.PHASE_MAIN)
    assert g.hp(1) + g.mp(1) + g.money(1) == 60


def test_earth_exchange_clamps_each_stat_to_99(board):
    """地球神: 合計が99を超える両替でも各値が99以下に収まることを検証します。"""
    g = earth_turn(
        "deals/exchange",
        p0=Side(hp=99, hand=[FILLER]),
        p1=Side(hp=90, mp=90, money=90, guardian=EARTH, hand=[FILLER]),
        exchange_hp=godfield_core.ROLL_MAX,  # 取りうる最大のHPを選ばせる
        exchange_mp=godfield_core.ROLL_MAX,
    )

    assert g.hp(1) + g.mp(1) + g.money(1) == 270
    assert g.hp(1) <= 99 and g.mp(1) <= 99 and g.money(1) <= 99


def test_earth_sell_settles_at_the_offered_card_price(board):
    """地球神: 売る。出品カードの価格で決済されることを検証します。"""
    price = card_feature(FILLER, "price")
    g = earth_turn(
        "deals/sell",
        p0=Side(hp=99, money=100, hand=[FILLER]),   # 買い手
        p1=Side(hp=99, money=10, guardian=EARTH, hand=[FILLER]),  # 売り手
    )

    g.expect(phase=GamePhase.PHASE_SELL_SELECT_MIRROR, attacker=1, defender=0)
    g.confirm()  # 買い手が受諾

    g.expect(p0_money=100 - price, p1_money=10 + price)


def test_earth_sell_offer_slot_is_recorded_with_sentinel(board):
    """地球神: 「売る」は売るカード自体を持たないため、番兵 -1 と出品スロットが記録されます。

    execute_sell_resolution が staged_cards[p][1] を ID_SELL(=1) と比較していた頃は、
    出品スロットが偶然 1 のときだけ成立し、反射時に売り手を取り違えていました。
    スロット5に置いて、番兵方式が正しく効いていることを固定します。
    """
    offer_slot = 5
    g = earth_turn(
        "deals/sell",
        p0=Side(hp=99, money=50, hand=["armor/super-mirror"]),
        p1=Side(
            hp=40, money=50, guardian=EARTH,
            hand=[None] * offer_slot + [FILLER],
        ),
    )

    g.expect(phase=GamePhase.PHASE_SELL_SELECT_MIRROR, attacker=1)
    assert g.state.get_staged_card(1, 0) == -1, "地球神の番兵が置かれているべきです"
    assert g.state.get_staged_card(1, 1) == offer_slot


def test_earth_sell_reflected_settles_the_offered_item_not_the_mirror(board):
    """地球神: 「売る」をスーパーミラーで反射しても、決済対象は出品カードのままであることを検証します。

    反射で attacker/defender が入れ替わったときに出品者を取り違え、反射側の
    スーパーミラー自身が売られてしまう不具合の再発防止。
    """
    offer_slot = 5
    price = card_feature(FILLER, "price")
    g = earth_turn(
        "deals/sell",
        p0=Side(hp=99, money=50, hand=["armor/super-mirror"]),
        p1=Side(
            hp=40, money=50, guardian=EARTH,
            hand=[None] * offer_slot + [FILLER],
        ),
    )

    # P0 がスーパーミラーで反射 → 売り手と買い手が入れ替わる
    g.select("armor/super-mirror")
    g.expect(attacker=0, defender=1)
    g.confirm()

    # 出品カードは元のスロットから取り除かれ、代金は出品カードの価格
    assert g.state.get_true_hand(1, offer_slot) == godfield_core.CARD_EMPTY
    assert card_name(card_id("armor/super-mirror")) not in g.hand(1), (
        "反射側のスーパーミラーが売られてはいけません"
    )
    assert card_name(card_id(FILLER)) in g.hand(1), "買い戻しで出品カードが戻るべきです"
    g.expect(p0_money=50 + price, p1_money=50 - price)


def test_earth_buy_settles_symmetrically(board):
    """地球神: 買う。売り手の増額と買い手の減額が一致することを検証します。"""
    price = card_feature(FILLER, "price")
    g = earth_turn(
        "deals/buy",
        p0=Side(hp=99, money=10, hand=[FILLER]),  # 売り手
        p1=Side(hp=99, money=100, guardian=EARTH, hand=[FILLER]),  # 買い手（地球神）
    )

    g.expect(phase=GamePhase.PHASE_BUY_SELECT_MIRROR, attacker=1, defender=0)
    g.confirm()
    g.expect(phase=GamePhase.PHASE_BUY, actor=1)
    g.deal_yes()

    g.expect(p0_money=10 + price, p1_money=100 - price)


def test_earth_buy_can_be_reflected_by_super_mirror(board):
    """地球神: 買う をスーパーミラーで反射すると、買い手が入れ替わることを検証します。"""
    g = earth_turn(
        "deals/buy",
        p0=Side(hp=99, money=100, hand=["armor/super-mirror"]),
        p1=Side(hp=99, money=100, guardian=EARTH, hand=[FILLER]),
    )

    g.expect(phase=GamePhase.PHASE_BUY_SELECT_MIRROR, actor=0)
    g.select("armor/super-mirror")
    # 反射により地球神の持ち主が標的になる
    g.expect(phase=GamePhase.PHASE_BUY_SELECT_MIRROR, actor=1)
    g.confirm()
    # 反射した P0 が買い手として判断する
    g.expect(phase=GamePhase.PHASE_BUY, actor=0)


def test_earth_weapon_attacks_with_that_weapons_own_power(board):
    """地球神: 武器。引いた武器そのものの攻撃力・属性で攻撃が組まれることを検証します。

    以前は引いたカードIDを staged_cards（本来は手札スロット番号を入れる配列）へ
    書き込んでいたため、下流がスロット番号として解釈して攻撃元が失われ、
    威力0の攻撃になっていました。
    """
    weapon = "weapons/wooden-sword"
    g = earth_turn(weapon)

    g.expect(
        phase=GamePhase.PHASE_DEFENSE,
        attacker=1,
        defender=0,
        # 威力・属性はカードマスタから引く（テストに直書きするとマスタ変更に追従できない）
        pending_power=card_feature(weapon, "attack_power"),
        pending_element=element_of(weapon),
    )
    assert g.state.pending_attack_source_id == card_id(weapon)
    g.expect_events(ev(godfield_core.EventType.EFFECT_GUARDIAN, card=weapon))


def test_earth_defense_card_is_added_to_hand(board):
    """地球神: 防具。引いた防具が持ち主の手札に加わることを検証します。"""
    g = earth_turn(
        "armor/iron-shield",
        p0=Side(hp=99, hand=[FILLER]),
        p1=Side(hp=99, guardian=EARTH, hand=[FILLER]),
    )

    g.expect(phase=GamePhase.PHASE_MAIN, p1_hand=[FILLER, "armor/iron-shield"])


def test_earth_defense_card_replaces_a_named_slot_when_hand_is_full(board):
    """地球神: 手札18枚満杯で防具を引いた場合、指定スロットが上書きされることを検証します。

    従来はどのスロットが潰れるかを制御できず「18枚のままで、木の盾以外が1枚以上ある」
    という緩い検証しかできませんでした。
    """
    g = Game(
        p0=Side(hp=99, hand=[FILLER]),
        p1=Side(hp=99, guardian=EARTH, hand=[FILLER] * 18),
    )
    g.rng.guardian_act(acts=True)
    g.rng.next_draws(FILLER, "armor/iron-shield", then=FILLER)
    g.rng.force(RollKind.EARTH_DISCARD_SLOT, 7)  # 候補リストの先頭から7番目を潰す
    g.pray()

    hand = g.hand(1)
    assert len(hand) == 18, "手札は18枚に保たれるべきです"
    assert hand.count(card_name(card_id("armor/iron-shield"))) == 1
    assert g.state.get_true_hand(1, 7) == card_id("armor/iron-shield"), (
        "指示したスロットが上書きされるべきです"
    )


def test_earth_broom_discards_named_slots_and_spares_used_ones(board):
    """地球神: 夜空のホウキ。破棄されるスロットを名指しし、使用済みスロットが守られることを検証します。

    破棄候補を全て別のカードにしてあるのは、ターン終了時の補充ドローが破棄跡を
    埋めて検証を誤魔化すのを防ぐためです（補充は盤面に無い FILLER2 で行われます）。
    """
    filler2 = "weapons/punch"  # 盤面に存在しないカードで補充させる
    g = earth_turn(
        "sundries/nocturnal-broom",
        p0=Side(
            hp=99,
            # スロット0は使用済みの奇跡（破棄対象外）、1〜4が破棄候補
            hand=[
                "miracles/fireball",
                "armor/iron-shield",
                "armor/wood-shield",
                "armor/leather-clothes",
                "armor/super-mirror",
            ],
            used=[0],
        ),
        p1=Side(hp=99, guardian=EARTH, hand=[FILLER]),
        filler=filler2,
    )

    g.rng.discard_order(4, 3, 2)  # 破棄される3枚を名指しする
    g.expect(phase=GamePhase.PHASE_SUNDRY_SELECT_MIRROR, actor=0)
    g.confirm()  # 反射せず受け入れる

    hand = g.hand(0)
    # 使用済み奇跡（スロット0）と、指示しなかったスロット1（アイアンシールド）は残る
    assert card_name(card_id("miracles/fireball")) in hand
    assert card_name(card_id("armor/iron-shield")) in hand
    # 指示した3枚は破棄されている
    for discarded in ("armor/super-mirror", "armor/leather-clothes", "armor/wood-shield"):
        assert card_name(card_id(discarded)) not in hand, f"{discarded} は破棄されるべきです"


def test_earth_broom_can_be_reflected_back_at_the_owner(board):
    """地球神: 夜空のホウキを反射すると、地球神の持ち主の手札が削られることを検証します。

    地球神が引いた雑貨も、通常プレイと同様に相手へ反射の機会が与えられます。
    以前は仮置き場を経由せず即座に効果を適用していたため跳ね返せませんでした。
    """
    g = earth_turn(
        "sundries/nocturnal-broom",
        p0=Side(hp=99, hand=["armor/super-mirror"]),
        p1=Side(
            hp=99, guardian=EARTH,
            hand=["armor/iron-shield", "armor/wood-shield",
                  "armor/leather-clothes", "armor/forest-shield"],
        ),
        filler="weapons/punch",  # 破棄跡を補充で埋めても検証がぶれないようにする
    )

    g.expect(phase=GamePhase.PHASE_SUNDRY_SELECT_MIRROR)
    g.rng.discard_order(0, 1, 2)
    g.select("armor/super-mirror")
    g.expect(defender=1)  # 効果は地球神の持ち主へ向かう
    g.confirm()

    hand = g.hand(1)
    for discarded in ("armor/iron-shield", "armor/wood-shield", "armor/leather-clothes"):
        assert card_name(card_id(discarded)) not in hand, f"{discarded} は破棄されるべきです"
    assert card_name(card_id("armor/forest-shield")) in hand, "指示しなかった1枚は残るべきです"


def test_earth_soap_discards_deployed_miracles(board):
    """地球神: 女神の石けん。相手の展開済み奇跡が破棄されることを検証します。"""
    g = earth_turn(
        "sundries/goddess-s-soap",
        p0=Side(hp=99, mp=50, hand=["miracles/fireball"], deployed=[0]),
        p1=Side(hp=99, guardian=EARTH, hand=[FILLER]),
    )

    g.expect(phase=GamePhase.PHASE_SUNDRY_SELECT_MIRROR, actor=0)
    g.confirm()

    assert not g.state.get_is_deployed(0, 0)
    assert g.state.get_true_hand(0, 0) == godfield_core.CARD_EMPTY


def test_earth_self_targeted_sundry_heals_the_owner(board):
    """地球神: 自分に使う雑貨（天の川のおいしい水）で持ち主が回復することを検証します。"""
    heal = 20  # 下の assert でマスタ値と突き合わせる
    g = earth_turn(
        "sundries/galaxy-geyser",
        p0=Side(hp=99, hand=[FILLER]),
        p1=Side(hp=30, guardian=EARTH, hand=[FILLER]),
    )

    g.expect(p1_hp=30 + heal, phase=GamePhase.PHASE_MAIN)


def test_earth_dangerous_pestle_hits_the_opponent(board):
    """地球神: あぶないキネ。ウスが無ければ通常の物理攻撃として飛んでくることを検証します。"""
    pestle = "weapons/dangerous-pestle"
    g = earth_turn(pestle)

    g.expect(
        phase=GamePhase.PHASE_DEFENSE,
        attacker=1,
        defender=0,
        pending_power=card_feature(pestle, "attack_power"),
    )
    assert g.state.pending_attack_source_id == card_id(pestle)


def test_earth_dangerous_pestle_with_mortar_deals_99_and_consumes_one(board):
    """地球神: あぶないキネ ＋ あぶないウス。99ダメージが入り、ウスが1枚消費されることを検証します。

    このテストは以前 100,000 シードの探索の末に「シードが見つかった」ことだけを
    確認する空のテストでした（99ダメージもウスの消費も検証していなかった）。
    """
    g = Game(
        p0=Side(hp=99, hand=["sundries/dangerous-mortar", FILLER]),
        p1=Side(hp=99, guardian=EARTH, hand=[FILLER]),
    )
    g.rng.guardian_act(acts=True)
    g.rng.next_draws(FILLER, "weapons/dangerous-pestle", then=FILLER)
    g.rng.force(RollKind.MORTAR_VICTIM, 0)  # ウス所持者のうち先頭（=P0）が被弾する
    g.pray()

    # 99ダメージで HP は 0 になり、ウスは消費済み（is_used）になる
    g.expect(p0_hp=0)
    assert g.state.get_is_used(0, 0) is True, "あぶないウスが1枚消費されるべきです"
    assert g.state.get_true_hand(0, 1) == card_id(FILLER), "他のカードは消費されません"
    assert g.rng.consumed(RollKind.MORTAR_VICTIM) == 1


# ============================================================================
# 月神 (Moon): 発動する奇跡ごとの分岐
# ============================================================================


def test_moon_aura_is_converted_to_a_physical_attack(board):
    """月神: ＜オーラ＞は攻撃奇跡ではないため、満月刀の物理攻撃 ATK20 に読み替えられます。"""
    g = moon_turn("miracles/aura")

    g.expect(
        phase=GamePhase.PHASE_DEFENSE,
        attacker=1,
        defender=0,
        pending_power=20,
        pending_element=Element.ELEM_NONE,
    )
    assert g.state.pending_attack_source_id == card_id("gurdians/full-moon-blade")
    assert not g.state.pending_is_group_attack


def test_moon_mirage_becomes_a_group_physical_attack(board):
    """月神: ＜蜃気楼＞は満月刀の ATK10 全体攻撃に読み替えられます。"""
    g = moon_turn("miracles/mirage")

    g.expect(phase=GamePhase.PHASE_DEFENSE, attacker=1, defender=0, pending_power=10)
    assert g.state.pending_attack_source_id == card_id("gurdians/full-moon-blade")
    assert g.state.pending_is_group_attack


def test_moon_spring_heals_the_owner(board):
    """月神: ＜泉＞は持ち主自身のHPを回復します（攻撃にならない）。"""
    g = moon_turn("miracles/spring")
    g.expect(p1_hp=50, phase=GamePhase.PHASE_MAIN)


def test_moon_treasure_gives_money_to_the_owner(board):
    """月神: ＜財宝＞は持ち主のお金を増やします。"""
    g = moon_turn("miracles/treasure")
    g.expect(p1_money=20, phase=GamePhase.PHASE_MAIN)


def test_moon_release_clears_both_guardians(board):
    """月神: ＜解放＞は両者の守護神を解除します（自分の月神も消える）。"""
    g = moon_turn(
        "miracles/release",
        p0=Side(hp=99, guardian=JUPITER, hand=[FILLER]),
        p1=Side(hp=40, guardian=MOON, hand=[FILLER]),
    )
    g.expect(p0_guardian=0, p1_guardian=0)


def test_moon_song_cures_the_owners_sickness(board):
    """月神: ＜歌声＞は持ち主の病気・災いを解除します。"""
    g = moon_turn(
        "miracles/song",
        p0=Side(hp=99, hand=[FILLER]),
        p1=Side(hp=99, guardian=MOON, sickness=SicknessType.SICKNESS_COLD, hand=[FILLER]),
    )
    g.expect(p1_sickness=SicknessType.SICKNESS_NONE)


def test_moon_attack_miracle_opens_the_miracle_defense_phase(board):
    """月神: 通常の攻撃奇跡は奇跡防御フェイズを起動します。"""
    miracle = "miracles/fireball"
    g = moon_turn(miracle)

    g.expect(
        phase=GamePhase.PHASE_MIRACLE_DEFENSE,
        attacker=1,
        defender=0,
        pending_power=card_feature(miracle, "attack_power"),
    )
    assert g.state.pending_attack_source_id == card_id(miracle)


def test_moon_miracle_rejects_a_card_outside_the_pool():
    """月神の候補外のカードを指定した場合、静かに別の奇跡を検証しないよう例外にします。"""
    from tests.core.dsl import RngController

    with pytest.raises(ValueError, match="月神の発動候補ではありません"):
        RngController().moon_miracle("weapons/punch")
    godfield_core.rng_clear_script()


def test_moon_miracle_pool_matches_the_cpp_table():
    """月神の候補一覧が C++ の MOON_MIRACLES から取得できていることを確認します。

    インデックスをテストに直書きすると、配列の順序を変えた瞬間に別の奇跡を
    検証する黙ったバグになります。
    """
    miracles = godfield_core.get_moon_miracles()
    assert len(miracles) == 28
    for expected in ("miracles/aura", "miracles/mirage", "miracles/spring",
                     "miracles/treasure", "miracles/release", "miracles/song"):
        assert card_id(expected) in miracles, f"{expected} は月神の候補に含まれるべきです"


# ============================================================================
# 移行時に残した低レベルAPIの利用（ActionType を直接使う経路の確認）
# ============================================================================


def test_raw_action_path_still_works(board):
    """DSL を経由せず ActionType を直接渡す経路が壊れていないことを確認します。"""
    g = board(p0=Side(hp=99, hand=[FILLER]), p1=Side(hp=40, hand=[FILLER]))
    g.rng.deck_always(FILLER)
    godfield_core.step_game(g.state, ActionType.ACTION_PRAY)
    g.expect(phase=GamePhase.PHASE_MAIN, actor=1)
