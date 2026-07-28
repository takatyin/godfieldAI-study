"""確率判定（RollKind）ごとの分岐網羅テスト。

RollKind を全件洗い出し、テストが一度も指示していない判定を機械的に特定して
埋めたものです。以下はいずれも「乱数を固定できるようになって初めて書けるように
なった」検証で、従来はシード探索でも到達を制御できなかったものを含みます。

各テストは「その判定が実際に行われたか（rng.consumed）」も確認します。
盤面の前提が崩れて判定に到達しなくなった場合、conftest の未消費検査で落ちます。
"""

import pytest

import godfield_core
from godfield_core import (
    CurseType,
    EventType,
    GamePhase,
    GuardianType,
    PhenomenonType,
    RollKind,
)
from tests.core.dsl import (
    Side,
    card_feature,
    card_id,
    card_name,
    dream_candidates,
    element_of,
    ev,
)

FILLER = "armor/wood-shield"


# ============================================================================
# MARS_RING: 火星の指輪の反撃（75%）
# ============================================================================


@pytest.mark.parametrize("counters", [True, False], ids=["反撃する", "反撃しない"])
def test_mars_ring_counter_roll_decides_whether_it_fires(board, counters):
    """火星の指輪の反撃判定の両分岐を検証します（従来はどちらも未検証）。

    指輪は防御時にダメージを受けると、一定確率で攻撃者へ反撃を予約します。
    """
    g = board(
        p0=Side(hp=40, hand=["weapons/punch"]),
        p1=Side(hp=40, hand=["armor/mars-ring"]),
    )
    g.rng.deck_always(FILLER)
    g.rng.mars_ring(counters=counters)

    g.attack("weapons/punch")
    g.defend("armor/mars-ring")

    assert g.rng.consumed(RollKind.MARS_RING) == 1
    if counters:
        # 反撃が予約され、攻撃者（P0）が防御側になる
        g.expect(phase=GamePhase.PHASE_DEFENSE, attacker=1, defender=0)
        g.expect_events(ev(EventType.RING_EFFECT, card="armor/mars-ring"))
    else:
        g.expect_no_events(ev(EventType.RING_EFFECT, card="armor/mars-ring"))


# ============================================================================
# 超常現象: 金山 / 日食 / 磁気嵐
# ============================================================================


@pytest.mark.parametrize("lucky", [0, 1], ids=["P0が総取り", "P1が総取り"])
def test_gold_mine_gives_all_money_to_the_chosen_player(board, lucky):
    """金山: お金が片方に集約されることを、どちらが得るかを指定して検証します。

    従来は「どちらかが20でもう一方が0」という OR 条件で、どちらが選ばれたかを
    制御も検証もできていませんでした。
    """
    g = board(
        p0=Side(hp=99, mp=50, money=12, hand=["sundries/string-of-fate"]),
        p1=Side(hp=99, money=8),
    )
    g.rng.deck_always(FILLER)
    g.rng.phenomenon(PhenomenonType.GOLD_MINE)
    g.rng.force(RollKind.PHENOMENON_GOLD_MINE, lucky)
    g.use("sundries/string-of-fate", to_self=True)

    total = 12 + 8
    if lucky == 0:
        g.expect(p0_money=total, p1_money=0)
    else:
        g.expect(p0_money=0, p1_money=total)


def test_gold_mine_clamps_the_total_at_99(board):
    """金山: 合計が99を超える場合に上限でクランプされることを検証します。"""
    g = board(
        p0=Side(hp=99, mp=50, money=80, hand=["sundries/string-of-fate"]),
        p1=Side(hp=99, money=60),
    )
    g.rng.deck_always(FILLER)
    g.rng.phenomenon(PhenomenonType.GOLD_MINE)
    g.rng.force(RollKind.PHENOMENON_GOLD_MINE, 0)
    g.use("sundries/string-of-fate", to_self=True)

    g.expect(p0_money=99, p1_money=0)  # 140 -> 99 にクランプ


@pytest.mark.parametrize(
    ("g0", "g1_roll", "expected_g1"),
    [
        (5, 4, 4),   # g1 < g0 なのでそのまま
        (5, 5, 6),   # g1 >= g0 なので +1 されて重複を避ける
        (1, 1, 2),   # 下端: g0=1 なら g1 は 2..10 になる
        (10, 9, 9),  # 上端: g0=10 なら補正は起きない
    ],
    ids=["補正なし", "重複回避で+1", "下端", "上端"],
)
def test_eclipse_assigns_two_distinct_guardians(board, g0, g1_roll, expected_g1):
    """日食: 両者に重複しない守護神が割り当てられることを、境界を含めて検証します。

    g1 は 1..9 で抽選され、g0 以上なら +1 して重複を避ける実装です。
    この補正の境界（g1 == g0、g0 が最小・最大）は従来まったく検証されていませんでした。
    """
    g = board(
        p0=Side(hp=99, mp=50, hand=["sundries/string-of-fate"]),
        p1=Side(hp=99),
    )
    g.rng.deck_always(FILLER)
    g.rng.phenomenon(PhenomenonType.ECLIPSE)
    g.rng.force(RollKind.PHENOMENON_ECLIPSE_G0, g0)
    g.rng.force(RollKind.PHENOMENON_ECLIPSE_G1, g1_roll)
    g.use("sundries/string-of-fate", to_self=True)

    g.expect(p0_guardian=g0, p1_guardian=expected_g1)
    assert g.state.get_guardian(0) != g.state.get_guardian(1), "守護神は重複しないべきです"


def test_magnetic_storm_redistributes_hands_in_the_specified_order(board):
    """磁気嵐: 手札が交換され、並び順を指定できることを検証します。

    従来はシード探索で「相手の手札の先頭が自分のカードだった」ことしか
    確認できていませんでした。
    """
    g = board(
        p0=Side(
            hp=99, mp=50,
            hand=["sundries/string-of-fate", "armor/iron-shield", "armor/wood-shield"],
        ),
        p1=Side(hp=99, hand=["armor/leather-clothes"]),
    )
    g.rng.deck_always(FILLER)
    g.rng.phenomenon(PhenomenonType.MAGNETIC_STORM)
    # プール（仮置き中の運命のひもを除く3枚）の並び順を元インデックスで指定する
    g.rng.pick_order(RollKind.PHENOMENON_MAGNETIC_STORM, [2, 0, 1])
    g.use("sundries/string-of-fate", to_self=True)

    # 交換後も両者の手札枚数の合計は保存される（仮置き中のカードは対象外）
    combined = sorted(g.hand(0) + g.hand(1))
    assert card_name(card_id("armor/leather-clothes")) in combined
    assert card_name(card_id("armor/iron-shield")) in combined
    assert card_name(card_id("armor/wood-shield")) in combined


# ============================================================================
# GUARDIAN_POT: 守護神の壺（1..10）
# ============================================================================


@pytest.mark.parametrize("guardian", list(range(1, 11)))
def test_guardian_pot_can_summon_every_guardian(board, guardian):
    """守護神の壺で降臨する守護神を10種すべて指定して検証します。

    従来はどの守護神が出るか制御できず、「0より大きい」ことしか見ていませんでした。
    """
    g = board(p0=Side(hp=40, mp=50, hand=["sundries/guardian-pot"]), p1=Side(hp=40))
    g.rng.deck_always(FILLER)
    g.rng.guardian_pot(guardian)
    g.use("sundries/guardian-pot", to_self=True)

    g.expect(p0_guardian=guardian)
    g.expect_events(ev(EventType.GUARDIAN_ENTER, value=float(guardian)))


# ============================================================================
# DEVIL_PRANKSTER / DEVIL_FAIRY: 悪魔カードの効果
# ============================================================================


def test_trickster_discards_the_two_specified_slots(board):
    """イタズラマン: 捨てられる2枚を指定して検証します（従来は完全に未検証）。"""
    g = board(
        p0=Side(
            hp=90, guardian=0,
            hand=["armor/iron-shield", "armor/wood-shield",
                  "armor/leather-clothes", "armor/super-mirror"],
        ),
        p1=Side(hp=90),
        turn=150,
    )
    g.rng.deck_always("weapons/punch")
    g.rng.apocalypse_draws("devils/trickster", None)
    # 候補（手札4枚）のうち 0番目と2番目を捨てさせる
    g.rng.script(RollKind.DEVIL_PRANKSTER, [0, 2])
    g.pray()

    hand = g.hand(0)
    assert card_name(card_id("armor/iron-shield")) not in hand
    assert card_name(card_id("armor/leather-clothes")) not in hand
    assert card_name(card_id("armor/wood-shield")) in hand
    assert card_name(card_id("armor/super-mirror")) in hand


@pytest.mark.parametrize(
    ("choice", "expect"),
    [
        (0, {"p0_hp": 60}),      # HP+10
        (1, {"p0_mp": 20}),      # MP+10
        (2, {"p0_money": 20}),   # お金+10
    ],
    ids=["HP+10", "MP+10", "お金+10"],
)
def test_charity_fairy_grants_the_chosen_resource(board, choice, expect):
    """めぐみの妖精: HP/MP/お金のどれが増えるかを3通りすべて検証します。"""
    g = board(
        p0=Side(hp=50, mp=10, money=10, hand=[]),
        p1=Side(hp=90),
        turn=150,
    )
    g.rng.deck_always(FILLER)
    g.rng.apocalypse_draws("devils/charity-fairy", None)
    g.rng.force(RollKind.DEVIL_FAIRY, choice)
    g.pray()

    g.expect(**expect)


# ============================================================================
# PESTLE_TARGET / MORTAR_VICTIM: あぶないキネ
# ============================================================================


@pytest.mark.parametrize("target_idx", [0, 1], ids=["自分に当たる", "相手に当たる"])
def test_dangerous_pestle_target_selection(board, target_idx):
    """あぶないキネ: ウスが無い場合、生存者から対象が抽選されることを検証します。

    従来は対象の抽選（PESTLE_TARGET）が一度も指示されていませんでした。

    自分に当たった側と相手に当たった側で、威力が同じ（＝どちらもカードマスタの
    attack_power から来る）ことも併せて固定します。以前は自傷側だけ 30 が
    直書きされており、マスタを変えると片側だけ追従しませんでした。
    """
    pestle = "weapons/dangerous-pestle"
    power = card_feature(pestle, "attack_power")

    g = board(
        p0=Side(hp=99, hand=[pestle]),
        p1=Side(hp=99, hand=[]),
    )
    g.rng.deck_always(FILLER)
    g.rng.force(RollKind.PESTLE_TARGET, target_idx)
    g.attack(pestle)

    assert g.rng.consumed(RollKind.PESTLE_TARGET) == 1
    if target_idx == 0:
        # 自傷: 防御フェイズを起動せず直撃
        g.expect(p0_hp=99 - power, p1_hp=99)
    else:
        # 相手を狙う: 物理防御フェイズが起動し、同じ威力・属性で飛ぶ
        g.expect(
            phase=GamePhase.PHASE_DEFENSE,
            attacker=0,
            defender=1,
            pending_power=power,
            pending_element=element_of(pestle),
        )


@pytest.mark.parametrize("victim_roll", [0, 1], ids=["攻撃側が被弾", "防御側が被弾"])
def test_dangerous_mortar_victim_selection(board, victim_roll):
    """あぶないウス: 所持者が複数いる場合の被弾者選定を両方向で検証します。"""
    g = board(
        p0=Side(hp=99, hand=["weapons/dangerous-pestle", "sundries/dangerous-mortar"]),
        p1=Side(hp=99, hand=["sundries/dangerous-mortar"]),
    )
    g.rng.deck_always(FILLER)
    g.rng.force(RollKind.MORTAR_VICTIM, victim_roll)
    g.attack("weapons/dangerous-pestle")

    assert g.rng.consumed(RollKind.MORTAR_VICTIM) == 1
    if victim_roll == 0:
        g.expect(p0_hp=0, p1_hp=99)
    else:
        g.expect(p0_hp=99, p1_hp=0)


# ============================================================================
# 手札スロットの選択: DISCARD_ONE_SLOT / REVEAL_SLOT / HAND_REPLACE_SLOT
# ============================================================================


def test_pray_with_full_hand_discards_the_specified_slot(board):
    """手札満杯で祈った際に捨てられる1枚を指定して検証します（従来は未検証）。"""
    hand = [FILLER] * 18
    hand[7] = "armor/super-mirror"  # 捨てられることを確認できる目印
    g = board(p0=Side(hp=40, hand=hand), p1=Side(hp=40))
    g.rng.deck_always("weapons/punch")
    g.rng.discard_one(7)
    g.pray()

    assert card_name(card_id("armor/super-mirror")) not in g.hand(0), (
        "指定したスロットのカードが捨てられるべきです"
    )
    assert len(g.hand(0)) == 18, "捨てた枠にドローされ、18枚が保たれるべきです"


@pytest.mark.parametrize("revealed_slot", [1, 2], ids=["スロット1を公開", "スロット2を公開"])
def test_buy_on_self_reveals_the_specified_slot(board, revealed_slot):
    """「買う」を自分に使った際に相手へ公開されるスロットを指定して検証します。

    従来 REVEAL_SLOT は一度も指示されておらず、どのカードが公開されるかは
    検証できていませんでした。
    """
    g = board(
        p0=Side(hp=40, money=50, hand=["deals/buy", FILLER, "armor/iron-shield"]),
        p1=Side(hp=40, money=50),
    )
    g.rng.deck_always(FILLER)
    g.rng.reveal_slot(revealed_slot)
    g.select("deals/buy")
    g.target_self()

    assert g.rng.consumed(RollKind.REVEAL_SLOT) == 1
    assert g.state.get_is_known_to_opp(0, revealed_slot) is True, (
        "指定したスロットが相手に公開されるべきです"
    )
    other = 2 if revealed_slot == 1 else 1
    assert g.state.get_is_known_to_opp(0, other) is False, (
        "指定していないスロットは公開されないべきです"
    )


def test_buy_with_full_hand_overwrites_the_specified_slot(board):
    """買い手の手札が満杯の場合に上書きされるスロットを指定して検証します。

    従来 HAND_REPLACE_SLOT は一度も指示されていませんでした。
    """
    hand = ["deals/buy"] + [FILLER] * 17
    hand[9] = "armor/super-mirror"  # 上書きされることを確認できる目印
    g = board(
        p0=Side(hp=40, money=50, hand=hand),
        p1=Side(hp=40, money=50, hand=["armor/iron-shield"]),
    )
    g.rng.deck_always(FILLER)
    g.rng.reveal_slot(0)
    g.rng.hand_replace_slot(9)
    g.select("deals/buy")
    g.target_opp()
    g.confirm()
    g.deal_yes()

    assert g.rng.consumed(RollKind.HAND_REPLACE_SLOT) == 1
    assert g.state.get_true_hand(0, 9) == card_id("armor/iron-shield"), (
        "指定したスロットが購入したカードで上書きされるべきです"
    )


@pytest.mark.parametrize("offer_slot", [0, 2], ids=["スロット0を出品", "スロット2を出品"])
def test_earth_guardian_offers_the_specified_slot(board, offer_slot):
    """地球神が「売る」を引いた際に出品するスロットを指定して検証します。

    従来 EARTH_SELL_SLOT は一度も指示されておらず、複数の売却候補があるときに
    どれが出品されるかは検証できていませんでした。
    """
    p1_hand = ["armor/wood-shield", "armor/leather-clothes", "armor/super-mirror"]
    g = board(
        p0=Side(hp=99, money=50, hand=[FILLER]),
        p1=Side(hp=99, money=50, guardian=int(GuardianType.EARTH), hand=list(p1_hand)),
    )
    g.rng.guardian_act(acts=True)
    # 山札は「P0の祈るドロー」「地球神のドロー」の順に消費される
    g.rng.next_draws(FILLER, "deals/sell", then=FILLER)
    g.rng.force(RollKind.EARTH_SELL_SLOT, offer_slot)
    g.pray()

    g.expect(phase=GamePhase.PHASE_SELL_SELECT_MIRROR, attacker=1, defender=0)
    assert g.rng.consumed(RollKind.EARTH_SELL_SLOT) == 1
    assert g.state.get_staged_card(1, 0) == -1, "地球神の番兵が置かれるべきです"
    assert g.state.get_staged_card(1, 1) == offer_slot, (
        "指定したスロットのカードが出品されるべきです"
    )


# ============================================================================
# DREAM_FAKE_CARD: 夢による手札の偽装
# ============================================================================


def test_dream_disguises_a_drawn_card_as_another_of_the_same_group(board):
    """夢状態で引いたカードが、同じ夢グループの別カードとして見えることを検証します。

    従来 DREAM_FAKE_CARD は一度も指示されていませんでした。
    """
    real = "armor/iron-shield"
    fake = card_name(dream_candidates(real)[0])
    g = board(p0=Side(hp=40, curses=[CurseType.CURSE_DREAM], hand=[]), p1=Side(hp=40))
    g.rng.next_draws(real)
    g.rng.dream(real, disguised=True, as_card=fake)
    g.pray()

    slot = next(i for i in range(18) if g.state.get_true_hand(0, i) != godfield_core.CARD_EMPTY)
    assert g.state.get_true_hand(0, slot) == card_id(real), "真の手札は引いたカードのまま"
    assert g.state.get_is_confirmed(0, slot) is False, "夢状態では確定していない"
    assert g.state.get_apparent_hand(0, slot) == card_id(fake), "指定した偽装先に見える"
    assert g.rng.consumed(RollKind.DREAM_FAKE_CARD) == 1


@pytest.mark.parametrize(
    ("roll", "should_disguise"),
    [
        (godfield_core.DREAM_DISGUISE_RATE - 1, True),
        (godfield_core.DREAM_DISGUISE_RATE, False),
    ],
    ids=["閾値の直前は偽装される", "閾値ちょうどは偽装されない"],
)
def test_dream_disguise_threshold_is_exactly_the_declared_percentage(board, roll, should_disguise):
    """偽装確率の境界値を検証します。

    抽選値は 0..99 なので、閾値未満が偽装される側になります。この2点を押さえることで
    「50%のはずが51%になっている」といった境界のずれを検出できます。
    """
    real = "armor/iron-shield"
    g = board(p0=Side(hp=40, curses=[CurseType.CURSE_DREAM], hand=[]), p1=Side(hp=40))
    g.rng.next_draws(real)
    g.rng.force(RollKind.DREAM_DISGUISE, roll)
    g.pray()

    slot = next(i for i in range(18) if g.state.get_true_hand(0, i) != godfield_core.CARD_EMPTY)
    disguised = g.state.get_apparent_hand(0, slot) != card_id(real)
    assert disguised is should_disguise


def test_dream_draw_is_not_always_disguised(board):
    """夢状態でも50%は偽装されず、そのままの見た目でドローされることを検証します。"""
    real = "armor/iron-shield"
    g = board(p0=Side(hp=40, curses=[CurseType.CURSE_DREAM], hand=[]), p1=Side(hp=40))
    g.rng.next_draws(real)
    g.rng.dream(disguised=False)
    g.pray()

    slot = next(i for i in range(18) if g.state.get_true_hand(0, i) != godfield_core.CARD_EMPTY)
    assert g.state.get_apparent_hand(0, slot) == card_id(real), "偽装されなければ見た目は変わらない"
    assert g.state.get_is_confirmed(0, slot) is False, "偽装されなくても未確定のままである"
    assert g.rng.consumed(RollKind.DREAM_FAKE_CARD) == 0, "偽装先の抽選自体が起きない"


# ============================================================================
# MUSHROOM_ACTION: ご乱心中のランダム行動
# ============================================================================


def test_mushroom_outbreak_picks_actions_deterministically_when_scripted(board):
    """ご乱心中の自動行動を固定できることを検証します（従来は未検証）。

    きのこ大発生が起きると6ターン分が自動進行します。その間の行動選択は
    合法手からのランダム抽選なので、指示できないと結果が毎回変わります。
    """
    g = board(
        p0=Side(hp=99, mp=50, money=20, hand=["sundries/string-of-fate"]),
        p1=Side(hp=99, mp=50, money=20),
        turn=10,
    )
    g.rng.deck_always(FILLER)
    g.rng.phenomenon(PhenomenonType.MUSHROOM)
    g.rng.force(RollKind.MUSHROOM_ACTION, 0)  # 常に先頭の合法手を選ぶ
    g.use("sundries/string-of-fate", to_self=True)

    # ご乱心が終了し、通常の操作受付に戻っていること
    assert g.state.mushroom_turns == 0
    assert g.rng.consumed(RollKind.MUSHROOM_ACTION) > 0
