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
    SicknessType,
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


def test_miracle_attack_consumes_mp_and_opens_the_miracle_defense_phase(board):
    """単体奇跡の攻撃が、MPを消費して奇跡防御フェイズを開くことを検証します。"""
    miracle = "miracles/fireball"
    mp_cost = card_feature(miracle, "mp_cost")
    power = card_feature(miracle, "attack_power")

    g = board(
        p0=Side(hp=40, mp=10, hand=[miracle]),
        p1=Side(hp=40, mp=10),
    )
    g.rng.deck_always(FILLER)

    g.select(miracle)
    g.expect(phase=GamePhase.PHASE_MIRACLE_PLUS)

    g.target_opp()
    g.expect(phase=GamePhase.PHASE_MIRACLE_DEFENSE, actor=1, p0_mp=10 - mp_cost)

    g.take_hit()
    g.expect(p1_hp=40 - power, phase=GamePhase.PHASE_MAIN, actor=1)


def test_absorption_on_self_nets_out_to_the_attack_power(board):
    """吸収を自分に撃つと、被弾と回復が同ステップで解決されHPが攻撃力と等しくなることを検証します。

    HP5 に ATK10 の吸収を自傷すると、いったん0にクランプされたあと +10 されるため
    最終HPは10になります。死亡判定より先に回復が入ることの確認でもあります。
    """
    miracle = "miracles/absorption"
    power = card_feature(miracle, "attack_power")
    mp_cost = card_feature(miracle, "mp_cost")

    g = board(p0=Side(hp=5, mp=20, hand=[miracle]), p1=Side(hp=40))
    g.rng.deck_always(FILLER)

    g.attack(miracle, to_self=True)

    g.expect(p0_hp=power, p0_mp=20 - mp_cost, is_done=False, phase=GamePhase.PHASE_MAIN, actor=1)


def test_deployed_miracle_stays_in_hand(board):
    """展開型の奇跡は使用後も手札に残り、展開済みフラグが立つことを検証します。"""
    g = board(
        p0=Side(hp=40, mp=20, hand=["weapons/punch", "miracles/aura"]),
        p1=Side(hp=40),
    )
    g.rng.deck_always(FILLER)

    g.attack("weapons/punch", "miracles/aura")
    g.take_hit()

    assert g.state.get_is_deployed(0, 1) is True
    assert g.state.get_true_hand(0, 1) == card_id("miracles/aura")


def test_consumed_weapon_slot_is_refilled_but_deployed_miracle_is_not(board):
    """消費された武器のスロットは補充され、展開された奇跡のスロットは残ることを検証します。"""
    g = board(
        p0=Side(hp=40, mp=20, hand=["weapons/punch", "miracles/aura"]),
        p1=Side(hp=40),
    )
    g.rng.deck_always(FILLER)

    g.attack("weapons/punch", "miracles/aura")
    g.take_hit()

    # 武器は消費されたので補充カードが入る
    assert g.state.get_true_hand(0, 0) == card_id(FILLER)
    assert g.state.get_is_deployed(0, 0) is False
    # 奇跡は展開されたまま残り、その分だけ空きスロットにも補充が入る
    assert g.state.get_true_hand(0, 2) == card_id(FILLER)


def test_aura_doubles_the_attack_power_and_clears_the_element(board):
    """＜オーラ＞が攻撃力を2倍にし、属性を無属性化することを検証します。"""
    weapon = "weapons/blaze-blade"
    g = board(
        p0=Side(hp=40, mp=20, hand=[weapon, "miracles/aura"]),
        p1=Side(hp=40),
    )

    g.attack(weapon, "miracles/aura")

    g.expect(
        pending_power=card_feature(weapon, "attack_power") * 2,
        pending_element=Element.ELEM_NONE,
    )


def test_status_miracle_still_opens_a_defense_phase(board):
    """攻撃力0の状態異常奇跡でも、相手に防御（反射）の機会が与えられることを検証します。"""
    miracle = "miracles/wind"
    g = board(p0=Side(hp=40, mp=20, hand=[miracle]), p1=Side(hp=40))
    g.rng.deck_always(FILLER)

    g.attack(miracle)
    g.expect(phase=GamePhase.PHASE_MIRACLE_DEFENSE, actor=1)

    g.take_hit()
    g.expect(p1_sickness=SicknessType.SICKNESS_COLD)


@pytest.mark.parametrize(
    ("miracle", "sickness", "curses", "expect"),
    [
        ("miracles/tone", SicknessType.SICKNESS_FEVER, [],
         {"p0_sickness": SicknessType.SICKNESS_NONE}),
        ("miracles/tone", SicknessType.SICKNESS_NONE, [CurseType.CURSE_FLASH],
         {"p0_curses": set()}),
    ],
    ids=["音色で熱病を治す", "音色で閃光を治す"],
)
def test_cure_miracles_clear_the_targeted_ailment(board, miracle, sickness, curses, expect):
    """治癒の奇跡が病気・災いを解除することを検証します。"""
    g = board(
        p0=Side(hp=40, mp=20, sickness=sickness, curses=list(curses), hand=[miracle]),
        p1=Side(hp=40),
    )
    g.rng.deck_always(FILLER)

    g.attack(miracle, to_self=True)

    g.expect(**expect)


def test_darkness_miracle_can_be_blocked_by_any_armor(board):
    """闇属性の奇跡攻撃には、無属性・光属性のどちらの防具も出せることを検証します。

    闇属性は防御しきれば即死を免れます。
    """
    miracle = "miracles/darkness"
    plain, light = "armor/leather-clothes", "armor/glittering-dress"
    g = board(
        p0=Side(hp=40, mp=20, hand=[miracle]),
        p1=Side(hp=40, mp=20, hand=[plain, light]),
    )
    g.rng.deck_always(FILLER)

    g.attack(miracle)
    g.expect(phase=GamePhase.PHASE_MIRACLE_DEFENSE, actor=1)
    g.expect_legal([plain, light])

    # 攻撃力以上のガードで完全に防ぐ
    assert card_feature(light, "defense_power") >= card_feature(miracle, "attack_power")
    g.defend(light)

    g.expect(p1_hp=40, is_done=False)


@pytest.mark.parametrize(
    ("card", "can_self_target"),
    [
        ("miracles/smoke", False),     # 命中率100%未満
        ("miracles/fireball", True),   # 命中率100%
    ],
    ids=["命中不安なので自傷不可", "命中率100%なら自傷可"],
)
def test_unstable_accuracy_cards_cannot_target_self(board, card, can_self_target):
    """命中率100%未満のカードは自分自身を対象に取れないことを検証します。

    従来のテストは説明に「命中率100%のカードなら自傷できる」と書きながら、
    その側を一度も検証していませんでした。
    """
    accuracy = card_feature(card, "accuracy", 100)
    assert (accuracy == 100) == can_self_target, "前提としている命中率がマスタと食い違っている"

    g = board(p0=Side(hp=40, mp=20, hand=[card]), p1=Side(hp=40))
    g.select(card)

    g.expect_actions(target_self=can_self_target, target_opp=True)


def test_a_miracle_used_this_turn_cannot_be_used_again(board):
    """このターンすでに使った展開済み奇跡を、同じターンに再度使えないことを検証します。"""
    cascade = "miracles/waterfall"
    g = board(
        p0=Side(hp=40, mp=40, hand=[cascade], deployed=[0], used=[0]),
        p1=Side(hp=40, mp=40),
    )
    g.rng.deck_always(FILLER)

    g.expect_illegal([cascade])


def test_a_deployed_miracle_becomes_usable_again_next_turn(board):
    """展開済みの奇跡が、次の自分のターンには再び使えるようになることを検証します。

    「使えない」ことだけを確認していると、常に使えないバグでもテストが通ります。
    """
    cascade = "miracles/waterfall"
    g = board(
        p0=Side(hp=40, mp=40, hand=[cascade], deployed=[0], used=[0]),
        p1=Side(hp=40, mp=40, hand=[FILLER]),
    )
    g.rng.deck_always(FILLER)

    g.expect_illegal([cascade])

    g.pray()          # P0 のターンを終える
    g.pray()          # P1 のターンを終える → P0 の番に戻る

    g.expect(actor=0)
    g.expect_legal([cascade])


def test_deploying_a_miracle_never_evicts_an_already_deployed_one(board):
    """奇跡の展開数に上限がなく、古い展開が押し出されないことを検証します。"""
    fireball = "miracles/fireball"
    already = 10

    g = board(
        p0=Side(hp=40, mp=99, hand=[fireball] * (already + 1),
                deployed=list(range(already))),
        p1=Side(hp=40, mp=40),
    )
    g.rng.deck_always(FILLER)

    assert g.deployed_count(0) == already, "展開済みの状態を作れていない"

    # まだ展開していない最後の1枚を使う（奇跡は解決されて初めて展開される）
    g.attack_slots(already)
    g.take_hit()

    assert g.deployed_count(0) == already + 1, (
        "新しく展開した分だけ増えるべきです（古い展開が押し出されてはいけない）"
    )
    for slot in range(already + 1):
        assert g.state.get_is_deployed(0, slot) is True, f"スロット{slot}の展開が消えています"


def test_a_weapon_with_a_miracle_stacked_resolves_as_a_weapon_attack(board):
    """武器に奇跡を重ねた攻撃が「武器攻撃」として扱われることを検証します。

    奇跡攻撃なら PHASE_MIRACLE_DEFENSE に入るので、遷移先で区別できます。
    """
    punch = "weapons/punch"
    fireball = "miracles/fireball"
    power = card_feature(punch, "attack_power") + card_feature(fireball, "attack_power")

    g = board(
        p0=Side(hp=40, mp=10, hand=[punch, fireball]),
        p1=Side(hp=40, mp=10),
    )
    g.rng.deck_always(FILLER)

    g.select(punch)
    g.expect(phase=GamePhase.PHASE_ATTACK_PLUS)

    g.select(fireball)
    g.target_opp()

    g.expect(phase=GamePhase.PHASE_DEFENSE, pending_power=power)


def test_only_a_spiritual_card_can_be_stacked_onto_a_miracle(board):
    """奇跡を1枚目に置いた後は、精霊系カード以外を重ねられないことを検証します。"""
    fireball = "miracles/fireball"
    ice = "miracles/ice"
    blowgun = "weapons/blowgun"      # プラス武器
    doll = "sundries/spiritual-doll"

    g = board(
        p0=Side(hp=40, mp=10, hand=[fireball, fireball, blowgun, ice, doll]),
        p1=Side(hp=40, mp=10),
    )
    g.rng.deck_always(FILLER)

    g.select_slots(0)
    g.expect(phase=GamePhase.PHASE_MIRACLE_PLUS)

    actions = g.legal_actions()
    assert actions[ActionType.ACTION_SELECT_HAND_1] is False, "同じ奇跡の2枚目は重ねられない"
    assert actions[ActionType.ACTION_SELECT_HAND_2] is False, "プラス武器は重ねられない"
    assert actions[ActionType.ACTION_SELECT_HAND_3] is False, "別の奇跡も重ねられない"
    assert actions[ActionType.ACTION_SELECT_HAND_4] is True, "精霊系カードだけが重ねられる"


# ==========================================
# Merged from: tests/core/test_apocalypse.py
# ==========================================



APOCALYPSE_TURN = godfield_core.APOCALYPSE_TURN


@pytest.mark.parametrize(
    ("turn", "is_apocalypse"),
    [
        (APOCALYPSE_TURN - 1, False),
        (APOCALYPSE_TURN, True),
    ],
    ids=["終末の1ターン前", "終末が始まるターン"],
)
def test_the_apocalypse_starts_exactly_on_its_turn(board, turn, is_apocalypse):
    """終末の時が APOCALYPSE_TURN ちょうどから始まることを、実際の挙動で検証します。

    従来のテストは
        runner.state.current_turn = 149
        assert runner.state.current_turn < 150
    と書かれており、Python の代入結果を読み返しているだけでゲームロジックを
    一度も呼んでいませんでした。閾値が変わっても、終末の判定が壊れても通ります。

    ここでは「終末の時にだけ悪魔が引かれる」という観測可能な差で判定します。
    """
    devil = "devils/small-devil"
    g = board(
        p0=Side(hp=40, mp=10, money=10, hand=[FILLER]),
        p1=Side(hp=40, mp=10, money=10),
        turn=turn,
    )
    g.rng.deck_always(FILLER)
    g.rng.apocalypse_draws(devil, optional=True)

    g.pray()

    drew_devil = g.rng.consumed(RollKind.APOCALYPSE_DRAW) > 0
    assert drew_devil is is_apocalypse, (
        f"ターン{turn}で悪魔抽選が{'行われる' if is_apocalypse else '行われない'}べきです"
    )


@pytest.mark.parametrize(
    ("turn", "refills"),
    [
        (0, False),
        (APOCALYPSE_TURN, True),
    ],
    ids=["通常の「捨てる」", "終末の「ささげる」"],
)
def test_discarding_refills_the_slot_only_during_the_apocalypse(board, turn, refills):
    """通常は捨てたスロットが空のまま、終末の時は補充されることを検証します。"""
    discarded = "armor/leather-clothes"
    refill = "armor/leather-cap"

    g = board(
        p0=Side(hp=40, mp=10, money=10, hand=[discarded]),
        p1=Side(hp=40, mp=10, money=10),
        turn=turn,
    )
    g.rng.deck_always(refill)
    g.rng.apocalypse_draws(None, optional=True)

    g.discard(discarded)

    if refills:
        assert g.state.get_true_hand(0, 0) == card_id(refill), (
            "終末の時はささげた分だけ引き直される"
        )
    else:
        assert g.state.get_true_hand(0, 0) == godfield_core.CARD_EMPTY, (
            "通常時は捨てたスロットが空のまま残る"
        )


def crossbow_kills_with_a_deferred_draw(board, *, turn: int, devil: str | None):
    """P0 がクロスボウで HP1 の P1 を倒した直後の局面を返します。"""
    bow = "weapons/crossbow"
    g = board(
        p0=Side(hp=10, mp=10, money=10, hand=[bow]),
        p1=Side(hp=1, mp=10, money=10, hand=[]),
        turn=turn,
    )
    g.rng.deck_always(FILLER)
    if devil is not None:
        # 引いた悪魔で死亡するとドローが打ち切られるため、末尾の指示は消費されないことがある
        g.rng.apocalypse_draws(devil, None, repeat_last=True)
    else:
        g.rng.apocalypse_draws(None, optional=True)

    g.attack(bow)
    g.take_hit()
    return g


def test_a_lethal_hit_ends_the_game_immediately_in_normal_play(board):
    """通常時は、被弾でHP0になった時点でゲームが終わることを検証します。"""
    g = crossbow_kills_with_a_deferred_draw(board, turn=0, devil=None)

    g.expect(p0_hp=10, p1_hp=0, is_done=True, p0_reward=1.0)


def test_the_apocalypse_defers_the_death_check_until_after_the_refill_draw(board):
    """終末の時は死亡判定が補充ドローの後まで持ち越され、引いた悪魔で相打ちになりうることを検証します。

    従来は「補充ドローで大悪魔を引いてP0も死ぬ」シードを最大500回探索していました。
    どの悪魔を引くかは制御できず、HP10に対して致死量かどうかも運任せでした。
    """
    # 大悪魔は30ダメージ。P0 の HP10 を確実に削り切れる悪魔を選んでいる
    # （悪魔ごとのダメージ量そのものは test_apocalypse_draw_triggers_each_devil で検証）。
    large_devil = "devils/large-devil"

    g = crossbow_kills_with_a_deferred_draw(
        board, turn=APOCALYPSE_TURN, devil=large_devil
    )

    # 被弾の瞬間には終わらず、補充ドローで引いた大悪魔が P0 も倒す
    g.expect(p0_hp=0, p1_hp=0, is_done=True, p0_reward=0.0, p1_reward=0.0)


# ==========================================
# Merged from: tests/core/test_phenomena.py
# ==========================================



FATE = "sundries/string-of-fate"
FILLER = "armor/wood-shield"


def trigger_phenomenon(board, phenomenon, *, p0=None, p1=None, **rng_kwargs):
    """「運命のひも」を自分に使い、指定した超常現象を発生させた局面を返します。

    従来は目的の現象が出るまで最大5000シードを3回に分けて探索していました。
    """
    g = board(
        p0=p0 if p0 is not None else Side(hp=99, mp=10, money=10, hand=[FATE]),
        p1=p1 if p1 is not None else Side(hp=99, mp=10, money=10),
    )
    g.rng.deck_always(FILLER)
    g.rng.phenomenon(phenomenon)
    for kind, value in rng_kwargs.items():
        g.rng.force(getattr(RollKind, kind.upper()), value)
    g.attack(FATE, to_self=True)
    return g


def test_sunset_gives_both_players_fever(board):
    """夕焼け: 両者が熱病になることを検証します。"""
    g = trigger_phenomenon(board, PhenomenonType.SUNSET)
    g.expect(
        p0_sickness=SicknessType.SICKNESS_FEVER,
        p1_sickness=SicknessType.SICKNESS_FEVER,
    )


def test_dense_fog_curses_both_players(board):
    """濃霧: 両者が霧状態になることを検証します。"""
    g = trigger_phenomenon(board, PhenomenonType.DENSE_FOG)
    g.expect(p0_curses={CurseType.CURSE_FOG}, p1_curses={CurseType.CURSE_FOG})


def test_tornado_sets_both_players_to_one_hp(board):
    """竜巻: 両者のHPが1になることを検証します。"""
    g = trigger_phenomenon(board, PhenomenonType.TORNADO)
    g.expect(p0_hp=1, p1_hp=1)


def test_gigantic_tub_on_self_deals_undefendable_damage(board):
    """巨大なタライが自分に当たった場合、防御できず即座にダメージが入ることを検証します。"""
    power = card_feature("phenomena/gigantic-tub", "attack_power")
    g = trigger_phenomenon(
        board, PhenomenonType.GIGANTIC_TUB,
        p0=Side(hp=80, mp=10, money=10, hand=[FATE]),
        phenomenon_tub_target=0,  # 0 = 使用者自身
    )
    g.expect(p0_hp=80 - power, phase=GamePhase.PHASE_MAIN)


def test_gigantic_tub_on_opponent_opens_a_defense_phase(board):
    """巨大なタライが相手に当たった場合、光属性の物理防御フェイズが起動することを検証します。"""
    source = "phenomena/gigantic-tub"
    g = trigger_phenomenon(
        board, PhenomenonType.GIGANTIC_TUB, phenomenon_tub_target=1,
    )
    g.expect(
        phase=GamePhase.PHASE_DEFENSE,
        attacker=0,
        defender=1,
        pending_power=card_feature(source, "attack_power"),
        pending_element=element_of(source),
    )
    assert g.state.pending_attack_source_id == card_id(source)


def test_black_hole_is_a_group_darkness_attack(board):
    """ブラックホール: 相手に闇属性の全体攻撃が飛ぶことを検証します。"""
    source = "phenomena/black-hole"
    g = trigger_phenomenon(board, PhenomenonType.BLACK_HOLE)

    g.expect(
        phase=GamePhase.PHASE_DEFENSE,
        attacker=0,
        defender=1,
        pending_power=card_feature(source, "attack_power"),
        pending_element=element_of(source),
        pending_is_group=True,
    )
    assert g.state.pending_attack_source_id == card_id(source)


def test_warm_current_heals_the_user(board):
    """暖流: 使用者のHPが+50されることを検証します。"""
    g = trigger_phenomenon(
        board, PhenomenonType.WARM_CURRENT,
        p0=Side(hp=40, mp=10, money=10, hand=[FATE]),
    )
    g.expect(p0_hp=90)


@pytest.mark.parametrize("lucky", [0, 1], ids=["P0が総取り", "P1が総取り"])
def test_gold_mine_concentrates_all_money(board, lucky):
    """金山: お金が指定した側へ集約されることを検証します。

    従来は「どちらか一方が30でもう一方が0」という OR 条件で、どちらが選ばれたかを
    制御も検証もできていませんでした。
    """
    g = trigger_phenomenon(
        board, PhenomenonType.GOLD_MINE,
        p0=Side(hp=99, mp=10, money=10, hand=[FATE]),
        p1=Side(hp=99, mp=10, money=20),
        phenomenon_gold_mine=lucky,
    )
    if lucky == 0:
        g.expect(p0_money=30, p1_money=0)
    else:
        g.expect(p0_money=0, p1_money=30)


def test_eclipse_assigns_distinct_guardians_to_both(board):
    """日食: 両者に重複しない守護神が割り当てられることを検証します。

    従来は「1〜10のいずれかで、かつ異なる」という緩い検証でした。
    重複回避の補正そのものは test_roll_branch_coverage.py が境界値で検証します。
    """
    g = trigger_phenomenon(
        board, PhenomenonType.ECLIPSE,
        phenomenon_eclipse_g0=4,
        phenomenon_eclipse_g1=4,  # g0 以上なので +1 されて 5 になる
    )
    g.expect(p0_guardian=4, p1_guardian=5)


@pytest.mark.parametrize("disguised", [True, False], ids=["偽装される", "偽装されない"])
def test_magnetic_storm_makes_both_hands_unconfirmed_if_either_side_dreams(board, disguised):
    """磁気嵐: どちらかが夢状態なら、配り直された手札が両者とも未確定になることを検証します。

    夢の偽装は50%でしか起きないため、「見た目が変わっていること」を条件にすると
    半分の確率で落ちるテストになります。夢が効いているかどうかは is_confirmed で
    判定し、見た目については偽装の有無を明示的に固定して両方を検証します。
    """
    g = board(
        p0=Side(hp=40, hand=["sundries/string-of-fate", "weapons/bronze-club", "armor/sky-armor"]),
        p1=Side(hp=40, curses=[CurseType.CURSE_DREAM], hand=["armor/god-shield"]),
    )
    g.rng.deck_always(FILLER)
    g.rng.phenomenon(PhenomenonType.MAGNETIC_STORM)
    g.rng.dream(disguised=disguised)

    g.attack("sundries/string-of-fate", to_self=True)

    # ひもは消費されるので、配り直される非ステージのカードは3枚（P0に2枚、P1に1枚）
    dealt = [(0, 0), (0, 1), (1, 0)]
    for p, i in dealt:
        true_id = g.state.get_true_hand(p, i)
        assert true_id != godfield_core.CARD_EMPTY, f"P{p} スロット{i} に配られているはず"
        assert g.state.get_is_confirmed(p, i) is False, (
            f"P{p} スロット{i}: 夢の相手がいるので未確定になるべきです"
        )
        apparent = g.state.get_apparent_hand(p, i)
        if disguised:
            assert apparent in dream_candidates(true_id), "同じ夢グループの別カードに見える"
        else:
            assert apparent == true_id, "偽装されなければ見た目は真のカードのまま"


def test_magnetic_storm_tracks_who_knows_which_card(board):
    """磁気嵐で手札を交換したあと、公開状態が正しく引き継がれることを検証します。

    規則は「相手から渡ってきたカードは相手が中身を知っている」「自分に戻ってきた
    カードは元の公開状態を保つ」の2つです。
    """
    mine_known = "weapons/bronze-club"     # 元から相手に知られている自分のカード
    mine_secret = "armor/sky-armor"        # 相手に知られていない自分のカード
    theirs_secret = "armor/god-shield"     # 相手の非公開カード

    g = board(
        p0=Side(
            hp=40, mp=10, money=10,
            hand=["sundries/string-of-fate", mine_known, mine_secret],
            known_to_opp=[1],
        ),
        p1=Side(hp=40, mp=10, money=10, hand=[theirs_secret]),
    )
    g.rng.deck_always(FILLER)
    g.rng.phenomenon(PhenomenonType.MAGNETIC_STORM)

    g.attack("sundries/string-of-fate", to_self=True)

    # ひもを除く3枚が配り直される（P0 に2枚、P1 に1枚）
    expected_known = {
        # 自分に戻ってきたカードは元の公開状態を保つ
        (0, card_id(mine_known)): True,
        (0, card_id(mine_secret)): False,
        # 相手から渡ってきたカードは、元の持ち主が中身を知っている
        (0, card_id(theirs_secret)): True,
        (1, card_id(mine_known)): True,
        (1, card_id(mine_secret)): True,
        # 自分に戻ってきた相手のカード
        (1, card_id(theirs_secret)): False,
    }

    checked = 0
    for player, slots in ((0, 2), (1, 1)):
        for slot in range(slots):
            cid = g.state.get_true_hand(player, slot)
            assert cid != godfield_core.CARD_EMPTY, f"P{player} スロット{slot} が空です"
            want = expected_known[(player, cid)]
            got = g.state.get_is_known_to_opp(player, slot)
            assert got is want, (
                f"P{player} スロット{slot} の {card_name(cid)}:"
                f" 公開状態は {want} であるべきですが {got} でした"
            )
            checked += 1
    assert checked == 3, "配り直された3枚すべてを検証しているべきです"


def test_the_string_of_fate_logs_which_phenomenon_it_triggered(board):
    """運命のひもが、発生した超常現象を TRIGGER_PHENOMENON として記録することを検証します。

    従来は発生する現象を制御しておらず、値の範囲（0..9）しか確認できませんでした。
    現象を名指しして、その番号が記録されることを確認します。
    """
    fate = "sundries/string-of-fate"
    phenomenon = PhenomenonType.WARM_CURRENT  # 盤面をほとんど動かさない現象

    g = board(
        p0=Side(hp=99, mp=10, money=10, hand=[fate]),
        p1=Side(hp=99, mp=10, money=10),
    )
    g.rng.deck_always(FILLER)
    g.rng.phenomenon(phenomenon)

    g.attack(fate, to_self=True)

    g.expect_events(ev(EventType.TRIGGER_PHENOMENON, card=fate, value=int(phenomenon)))
