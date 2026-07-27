
import pytest

import godfield_core
from godfield_core import ActionType, CurseType, GamePhase, GuardianType, SicknessType
from tests.core.dsl import Side, card_feature, card_id, card_name

# 補充ドローで盤面が動かないようにするための無害なカード。
FILLER = "armor/wood-shield"

# ==========================================
# Merged from: tests/core/test_transactions.py
# ==========================================



EXCHANGE = "deals/exchange"


def start_exchange(board, *, hp: int, mp: int, money: int):
    """両替カードを自分に使い、HP指定フェイズまで進めた局面を返します。"""
    g = board(
        p0=Side(hp=hp, mp=mp, money=money, hand=[EXCHANGE]),
        p1=Side(hp=40),
    )
    g.rng.deck_always("armor/wood-shield")
    g.select(EXCHANGE)
    g.target_self()
    g.expect(phase=GamePhase.PHASE_EXCHANGE_HP)
    return g


def test_exchange_redistributes_the_total_across_hp_mp_and_money(board):
    """両替が HP・MP・お金の合計を保ったまま再分配することを検証します。"""
    hp, mp, money = 40, 20, 15
    total = hp + mp + money

    g = start_exchange(board, hp=hp, mp=mp, money=money)

    g.num(30)  # HP を 30 に
    g.expect(phase=GamePhase.PHASE_EXCHANGE_MP)
    g.num(20)  # MP を 20 に（残りがお金になる）

    g.expect(p0_hp=30, p0_mp=20, p0_money=total - 30 - 20, phase=GamePhase.PHASE_MAIN)


def test_exchange_hp_choice_is_capped_at_the_total(board):
    """HPの指定可能な上限が合計値であることを、境界値で検証します。"""
    hp, mp, money = 40, 20, 15
    total = hp + mp + money

    g = start_exchange(board, hp=hp, mp=mp, money=money)

    legal = g.legal_actions()
    assert legal[int(ActionType.ACTION_NUM_0) + total] is True, "合計値ちょうどは指定できる"
    assert legal[int(ActionType.ACTION_NUM_0) + total + 1] is False, "合計値を超えては指定できない"

    # 指示を消費するため、実際に選んで進めておく
    g.num(30)
    g.num(20)


def test_exchange_mp_choice_is_capped_at_the_remainder(board):
    """MPの指定可能な上限が「合計 - 指定済みHP」であることを、境界値で検証します。"""
    hp, mp, money = 40, 20, 15
    total = hp + mp + money
    chosen_hp = 30
    remainder = total - chosen_hp

    g = start_exchange(board, hp=hp, mp=mp, money=money)
    g.num(chosen_hp)

    legal = g.legal_actions()
    assert legal[int(ActionType.ACTION_NUM_0) + remainder] is True, "残額ちょうどは指定できる"
    assert legal[int(ActionType.ACTION_NUM_0) + remainder + 1] is False, "残額を超えては指定できない"

    g.num(20)


def test_exchange_to_zero_hp_is_immediate_death(board):
    """両替でHPに0を指定すると、その場で敗北が確定することを検証します。

    両替によるHP減少は「ダメージ」ではないので守護神の離脱判定は行われませんが、
    HPが0になれば死亡判定は通ります。
    """
    g = start_exchange(board, hp=40, mp=20, money=10)

    g.num(0)   # HP を 0 に
    g.num(20)  # MP を 20 に指定して確定

    g.expect(is_done=True, p0_reward=-1.0)


SELL = "deals/sell"
BUY = "deals/buy"
POT = "sundries/guardian-pot"  # 価格10の売買テスト用カード
FILLER = "armor/wood-shield"


def test_sell_to_self_pays_and_refunds_the_same_price(board):
    """自分に売ると、代金を支払ったうえで同額を受け取り、カードも手元に残ることを検証します。

    支払いは お金 -> MP -> HP の順に行われます（execute_money_deduction）。
    お金が足りない分だけMPが削られ、受け取りはお金で行われるため、
    差し引きで「MPがお金に変換される」形になります。
    """
    price = card_feature(POT, "price")
    g = board(
        p0=Side(hp=50, mp=8, money=5, hand=[SELL, POT]),
        p1=Side(hp=40),
    )
    g.rng.deck_always(FILLER)

    g.select(SELL, POT)
    g.target_self()

    # お金5を使い切り、不足分5をMPから支払い、売却益10を受け取る
    g.expect(p0_money=price, p0_mp=8 - (price - 5), p0_hp=50)
    assert card_name(card_id(POT)) in g.hand(0), "自分に売ったカードは手元に残る"


def test_sell_to_opponent_deducts_money_then_mp(board):
    """相手に売ると、相手の お金 -> MP の順で代金が引かれ、売り手に代金が入ることを検証します。"""
    price = card_feature(POT, "price")
    buyer_money = 4
    g = board(
        p0=Side(hp=40, money=0, hand=[SELL, POT]),
        p1=Side(hp=40, mp=10, money=buyer_money),
    )
    g.rng.deck_always(FILLER)

    g.select(SELL, POT)
    g.target_opp()
    g.confirm()  # 相手が受諾

    g.expect(
        p1_money=0,
        p1_mp=10 - (price - buyer_money),
        p0_money=price,
    )

    # 買い取ったカードが相手の手札に移り、売り手から見えている状態になる
    slot = g.slot_of(1, POT)
    assert g.state.get_is_known_to_opp(1, slot) is True


def test_sell_to_self_can_bankrupt_and_kill(board):
    """総資産より高いカードを自分に売ると、支払い切れずに死亡することを検証します。"""
    price = card_feature(POT, "price")
    g = board(
        p0=Side(hp=5, mp=0, money=0, hand=[SELL, POT]),
        p1=Side(hp=40),
    )
    assert 5 < price, "総資産が価格を下回る前提のテスト"
    g.rng.deck_always(FILLER)

    g.select(SELL, POT)
    g.target_self()

    g.expect(p0_hp=0, is_done=True, p0_reward=-1.0)


def test_sell_to_opponent_can_bankrupt_and_kill(board):
    """総資産より高いカードを相手に売りつけると、相手が死亡することを検証します。"""
    sword = "weapons/god-sword"
    price = card_feature(sword, "price")
    g = board(
        p0=Side(hp=40, money=0, hand=[SELL, sword]),
        p1=Side(hp=10, mp=5, money=5),
    )
    assert 10 + 5 + 5 < price, "相手の総資産が価格を下回る前提のテスト"
    g.rng.deck_always(FILLER)

    g.select(SELL, sword)
    g.target_opp()
    g.confirm()

    g.expect(is_done=True, p1_hp=0)


def test_sell_reflected_by_super_mirror_forces_the_seller_to_buy_back(board):
    """売却をスーパーミラーで反射されると、売り手自身が買い戻すことを検証します。"""
    price = card_feature(POT, "price")
    g = board(
        p0=Side(hp=40, money=price, hand=[SELL, POT]),
        p1=Side(hp=40, money=0, hand=["armor/super-mirror"]),
    )
    g.rng.deck_always(FILLER)

    g.select(SELL, POT)
    g.target_opp()
    g.expect(phase=GamePhase.PHASE_SELL_SELECT_MIRROR)

    g.select("armor/super-mirror")
    g.expect(phase=GamePhase.PHASE_SELL_SELECT_MIRROR, actor=0)
    g.confirm()

    # 売り手が代金を払い、反射した側が受け取る
    g.expect(p0_money=0, p1_money=price)
    slot = g.slot_of(0, POT)
    assert g.state.get_is_known_to_opp(0, slot) is True


def test_buy_from_opponent_transfers_card_and_money(board):
    """相手からカードを購入すると、代金とカードが正しく移動することを検証します。

    購入対象は相手の手札からランダムに1枚公開されるので、どのスロットが出品されるかを
    指定しています（従来は相手の手札が1枚だけの盤面にして間接的に固定していました）。
    """
    price = card_feature(POT, "price")
    g = board(
        p0=Side(hp=40, money=20, hand=[BUY]),
        p1=Side(hp=40, money=0, hand=[POT, FILLER]),
    )
    g.rng.deck_always(FILLER)
    g.rng.reveal_slot(0)  # つぼ（スロット0）を出品させる

    g.select(BUY)
    g.target_opp()
    g.confirm()  # 相手が反射せず受諾

    # 出品されたカードは公開される
    assert g.state.get_is_known_to_opp(1, 0) is True

    g.deal_yes()  # 購入する

    g.expect(p0_money=20 - price, p1_money=price)
    assert g.state.get_true_hand(1, 0) == godfield_core.CARD_EMPTY, "売り手の手札から消える"

    slot = g.slot_of(0, POT)
    assert g.state.get_is_known_to_opp(0, slot) is True, "買ったカードは相手に見えている"


def test_buy_with_a_full_hand_overwrites_the_specified_slot(board):
    """手札が満杯のときに購入すると、指定したスロットが購入カードで上書きされることを検証します。

    従来は「スロット1〜17のどれか1つがつぼになった」という緩い検証で、
    どのスロットが潰れるかを制御できていませんでした。
    """
    price = card_feature(POT, "price")
    victim_slot = 9
    hand = [BUY] + [FILLER] * 17
    g = board(
        p0=Side(hp=40, money=20, hand=hand),
        p1=Side(hp=40, money=0, hand=[POT]),
    )
    g.rng.deck_always(FILLER)
    g.rng.reveal_slot(0)
    g.rng.hand_replace_slot(victim_slot)

    g.select(BUY)
    g.target_opp()
    g.confirm()
    g.deal_yes()

    g.expect(p0_money=20 - price)
    assert g.state.get_true_hand(0, victim_slot) == card_id(POT), (
        "指定したスロットが購入カードで上書きされるべきです"
    )
    assert len(g.hand(0)) == 18, "手札は18枚に保たれるべきです"


# ==========================================
# 「買う」: 反射・拒否・情報公開
# ==========================================

BUY = "deals/buy"
SELL = "deals/sell"
MIRROR = "armor/super-mirror"
POT = "sundries/guardian-pot"


def test_buy_reflected_by_the_super_mirror_forces_the_caster_to_sell(board):
    """「買う」を反射されると、撃った側が売り手に回ることを検証します。"""
    price = card_feature(POT, "price")

    g = board(
        p0=Side(hp=40, money=0, hand=[BUY, POT]),
        p1=Side(hp=40, money=price * 2, hand=[MIRROR]),
    )
    g.rng.deck_always(FILLER)

    g.select(BUY)
    g.target_opp()

    g.select(MIRROR)  # P1 が反射
    g.expect(phase=GamePhase.PHASE_BUY_SELECT_MIRROR, actor=0)

    g.confirm()  # 反射を受け入れる

    # 買い手が P1 に入れ替わる
    g.expect(phase=GamePhase.PHASE_BUY, actor=1)

    offered = g.state.get_staged_card(0, 0)
    assert g.state.get_true_hand(0, offered) == card_id(POT), (
        "「買う」以外の手札が1枚しかないので、必ずつぼが出品される"
    )

    g.deal_yes()

    # 代金とカードが入れ替わる
    g.expect(p0_money=price, p1_money=price)
    assert g.state.get_true_hand(0, offered) == godfield_core.CARD_EMPTY

    bought = [
        j
        for j in range(godfield_core.MAX_HAND_SIZE)
        if g.state.get_true_hand(1, j) == card_id(POT)
    ]
    assert len(bought) == 1, "買ったカードが相手の手札に1枚だけ入るべきです"
    assert g.state.get_is_known_to_opp(1, bought[0]) is True, "買われたカードは公開される"


def test_buy_reflection_is_cancelled_when_the_new_seller_has_nothing(board):
    """反射された「買う」で、売る側に出品できる手札が無ければ自動的に流れることを検証します。"""
    g = board(
        p0=Side(hp=40, money=0, hand=[BUY]),   # 「買う」以外に手札が無い
        p1=Side(hp=40, money=20, hand=[MIRROR]),
    )
    g.rng.deck_always(FILLER)

    g.select(BUY)
    g.target_opp()
    g.select(MIRROR)
    g.confirm()

    # 出品できるカードが無いので取引はキャンセルされ、そのままターンが移る
    g.expect(phase=GamePhase.PHASE_MAIN, actor=1, p0_money=0, p1_money=20)


def offer_for_purchase(board, *, p1: Side):
    """P0 が P1 に「買う」を撃ち、P1 のスロット0 が出品された局面を返します。"""
    g = board(p0=Side(hp=40, money=20, hand=[BUY]), p1=p1)
    g.rng.deck_always(FILLER)

    g.select(BUY)
    g.target_opp()
    g.confirm()  # P1 は反射せず受諾

    assert g.state.get_is_known_to_opp(1, 0) is True, "出品中は相手に見えている"
    return g


def test_a_refused_card_stays_public_when_it_is_the_only_one_of_its_kind(board):
    """購入を断られても、公開された情報はそのまま残ることを検証します。"""
    card = "armor/leather-clothes"
    g = offer_for_purchase(board, p1=Side(hp=40, money=0, hand=[card]))

    g.deal_no()

    assert g.state.get_is_known_to_opp(1, 0) is True, (
        "一度見えたカードの情報は、断られても失われない"
    )


def test_a_refused_card_is_hidden_again_when_an_identical_card_is_already_public(board):
    """同名カードがすでに公開済みなら、断られた側の公開は取り消されることを検証します。

    「革の服がスロット0とスロット1の2枚ある」という情報まで漏らさないための
    情報量クランプです。
    """
    card = "armor/leather-clothes"
    g = offer_for_purchase(
        board,
        p1=Side(hp=40, money=0, hand=[card, card], known_to_opp=[1]),
    )

    g.deal_no()

    assert g.state.get_is_known_to_opp(1, 0) is False, "重複公開は取り消されるべきです"
    assert g.state.get_is_known_to_opp(1, 1) is True, "元から公開されていた側は残る"


def test_a_deployed_miracle_does_not_count_as_a_public_duplicate(board):
    """展開済みの同名奇跡は「公開済みの重複」に数えないことを検証します。

    展開済みの奇跡は場に出ている別の存在なので、手札のコピーが公開されたままでも
    情報の重複にはなりません。
    """
    miracle = "miracles/fireball"
    g = offer_for_purchase(
        board,
        p1=Side(hp=40, mp=20, money=0, hand=[miracle, miracle],
                deployed=[1], known_to_opp=[1]),
    )

    g.deal_no()

    assert g.state.get_is_known_to_opp(1, 0) is True, (
        "展開済みの奇跡とは独立に扱われるべきです"
    )
    assert g.state.get_is_known_to_opp(1, 1) is True


def test_buying_from_yourself_only_reveals_a_card(board):
    """自分に「買う」を使うと、手札が1枚公開されるだけで取引は起きないことを検証します。"""
    club = "weapons/bronze-club"
    g = board(
        p0=Side(hp=40, money=20, hand=[BUY, club]),
        p1=Side(hp=40, money=20),
    )
    g.rng.deck_always(FILLER)

    g.select(BUY)
    g.target_self()

    # 相手の受諾やミラー確認を経ず、即座に解決してターンが移る
    g.expect(phase=GamePhase.PHASE_MAIN, actor=1, p0_money=20, p1_money=20)
    assert g.state.get_is_known_to_opp(0, 1) is True, "手札が1枚公開されるべきです"


# ==========================================
# 「売る」: 手札の増減と反射
# ==========================================


def test_selling_reduces_the_hand_by_one_because_only_the_deal_slot_refills(board):
    """売却では「売る」のスロットだけが補充され、売ったカードのスロットは空のままになることを検証します。"""
    refill = "armor/leather-cap"
    price = card_feature(POT, "price")

    g = board(
        p0=Side(hp=40, money=0, hand=[SELL, POT]),
        p1=Side(hp=40, money=price * 2),
    )
    g.rng.deck_always(refill)

    g.select(SELL, POT)
    g.target_opp()
    g.confirm()  # P1 が受諾

    g.expect(phase=GamePhase.PHASE_MAIN, actor=1)

    assert g.state.get_true_hand(0, 0) == card_id(refill), (
        "「売る」のスロットは補充されるべきです"
    )
    assert g.state.get_true_hand(0, 1) == godfield_core.CARD_EMPTY, (
        "売ったカードのスロットは補充されないべきです"
    )
    assert len(g.hand(0)) == 1, "手札総数が1枚減るべきです"


def test_sell_reflected_by_the_super_mirror_makes_the_seller_buy_it_back(board):
    """「売る」を反射されると、売ろうとした側が自分で買い戻すことを検証します。"""
    refill = "armor/leather-cap"
    price = card_feature(POT, "price")
    p0_money, p1_money = price * 2, price // 2

    g = board(
        p0=Side(hp=40, money=p0_money, hand=[SELL, POT]),
        p1=Side(hp=40, money=p1_money, hand=[MIRROR]),
    )
    g.rng.deck_always(refill)

    g.select(SELL, POT)
    g.target_opp()
    g.expect(phase=GamePhase.PHASE_SELL_SELECT_MIRROR, actor=1)

    g.select(MIRROR)  # P1 が反射
    g.expect(phase=GamePhase.PHASE_SELL_SELECT_MIRROR, actor=0)

    g.confirm()  # P0 が反射を受け入れる

    g.expect(
        phase=GamePhase.PHASE_MAIN,
        actor=1,
        p0_money=p0_money - price,
        p1_money=p1_money + price,
    )

    # つぼは売れずに P0 の手札へ戻る
    assert g.state.get_true_hand(0, 1) == card_id(POT)
    assert card_name(card_id(POT)) not in g.hand(1), "相手にカードは渡らない"

    # 使い切ったスロットはどちらも補充される
    assert g.state.get_true_hand(0, 0) == card_id(refill), "「売る」の補充"
    assert g.state.get_true_hand(1, 0) == card_id(refill), "スーパーミラーの補充"


# ==========================================
# 攻撃内容の観測可能性
# ==========================================


def test_the_attack_stays_visible_to_the_defender_until_it_resolves(board):
    """攻撃確定から防御解決までの間、防御側が攻撃内容を完全に観測できることを検証します。"""
    club = "weapons/bronze-club"
    blowgun = "weapons/blowgun"
    cap = "armor/leather-cap"

    g = board(
        p0=Side(hp=40, mp=10, hand=[club, blowgun]),
        p1=Side(hp=40, mp=10, hand=[cap]),
    )
    g.rng.deck_always(FILLER)

    g.select(club)
    assert g.state.get_is_known_to_opp(0, 0) is False, "仮置き中はまだ見えない"

    g.expect(phase=GamePhase.PHASE_ATTACK_PLUS)
    g.select(blowgun)
    assert g.state.get_is_known_to_opp(0, 1) is False, "仮置き中はまだ見えない"

    g.target_opp()

    # 確定した時点で、使ったカードが相手に公開される
    assert g.state.get_is_known_to_opp(0, 0) is True
    assert g.state.get_is_known_to_opp(0, 1) is True
    g.expect(phase=GamePhase.PHASE_DEFENSE, actor=1)

    # 防御中も攻撃側の仮置きは維持され、使用順まで観測できる
    assert g.state.get_num_staged_cards(0) == 2
    assert g.state.get_staged_card(0, 0) == 0
    assert g.state.get_staged_card(0, 1) == 1

    g.select(cap)
    assert g.state.get_is_known_to_opp(1, 0) is False, "防具は仮置き中まだ見えない"

    g.confirm()

    # 解決後は両者の仮置きがクリアされる
    assert g.state.get_num_staged_cards(0) == 0
    assert g.state.get_num_staged_cards(1) == 0


# ==========================================
# Merged from: tests/core/test_sundries.py
# ==========================================



def test_only_one_sundry_can_be_used_at_a_time(board):
    """雑貨を1枚仮置きすると、別の雑貨を重ねられなくなることを検証します。"""
    g = board(
        p0=Side(hp=10, hand=["sundries/smile-dew", "sundries/romance-fragrance"]),
        p1=Side(hp=40),
    )

    g.select("sundries/smile-dew")

    g.expect_illegal(["sundries/romance-fragrance"])
    g.expect_actions(target_self=True)


# HP を回復する雑貨と回復量。combat_resolution.cpp の apply_card_effect_to_target と対応する。
HP_HEALING_SUNDRIES = [
    ("sundries/smile-dew", 5),
    ("sundries/heart-dew", 10),
    ("sundries/galaxy-geyser", 20),
]

# MP を回復する雑貨と回復量。
MP_HEALING_SUNDRIES = [
    ("sundries/smile-flower", 5),
    ("sundries/heart-flower", 10),
    ("sundries/romance-fragrance", 15),
]


@pytest.mark.parametrize(("card", "heal"), HP_HEALING_SUNDRIES)
def test_hp_healing_sundries_restore_the_documented_amount(board, card, heal):
    """HP回復雑貨が規定量だけ回復し、ターンが相手へ移ることを検証します。

    従来はスマイルのしずく1種だけを検証していました。
    """
    g = board(p0=Side(hp=10, hand=[card]), p1=Side(hp=40))
    g.rng.deck_always("armor/wood-shield")

    g.attack(card, to_self=True)

    g.expect(p0_hp=10 + heal, actor=1)


@pytest.mark.parametrize(("card", "heal"), MP_HEALING_SUNDRIES)
def test_mp_healing_sundries_restore_the_documented_amount(board, card, heal):
    """MP回復雑貨が規定量だけ回復することを検証します。"""
    g = board(p0=Side(hp=10, mp=0, hand=[card]), p1=Side(hp=40))
    g.rng.deck_always("armor/wood-shield")

    g.attack(card, to_self=True)

    g.expect(p0_mp=heal, actor=1)


@pytest.mark.parametrize(("card", "heal"), HP_HEALING_SUNDRIES)
def test_hp_healing_is_clamped_at_99(board, card, heal):
    """HP回復が上限99でクランプされることを、全回復雑貨について検証します。"""
    g = board(p0=Side(hp=98, hand=[card]), p1=Side(hp=40))
    g.rng.deck_always("armor/wood-shield")

    g.attack(card, to_self=True)

    g.expect(p0_hp=99)


@pytest.mark.parametrize(("card", "heal"), MP_HEALING_SUNDRIES)
def test_mp_healing_is_clamped_at_99(board, card, heal):
    """MP回復が上限99でクランプされることを、全回復雑貨について検証します。"""
    g = board(p0=Side(hp=10, mp=98, hand=[card]), p1=Side(hp=40))
    g.rng.deck_always("armor/wood-shield")

    g.attack(card, to_self=True)

    g.expect(p0_mp=99)


def test_heaven_herb_restores_mp_but_inflicts_heaven_sickness(board):
    """天国草が相手のMPを+20する代償に天国病を与えることを検証します。"""
    g = board(
        p0=Side(hp=40, hand=["sundries/heaven-herb"]),
        p1=Side(hp=40, mp=10, sickness=SicknessType.SICKNESS_NONE),
    )
    g.rng.deck_always("armor/wood-shield")

    g.use("sundries/heaven-herb")

    g.expect(p1_mp=30, p1_sickness=SicknessType.SICKNESS_HEAVEN)


def test_smile_shell_cures_only_the_lighter_ailments(board):
    """スマイルの貝がらが風邪と霧・閃光だけを治し、夢と暗雲は残すことを検証します。

    従来は夢が残ることだけを確認していましたが、暗雲も残ることが仕様なので併せて固定します。
    """
    g = board(
        p0=Side(
            hp=40,
            sickness=SicknessType.SICKNESS_COLD,
            curses=[CurseType.CURSE_FOG, CurseType.CURSE_FLASH,
                    CurseType.CURSE_DARK_CLOUD, CurseType.CURSE_DREAM],
            hand=["sundries/smile-shell"],
        ),
        p1=Side(hp=40),
    )
    g.rng.deck_always("armor/wood-shield")

    g.attack("sundries/smile-shell", to_self=True)

    g.expect(
        p0_sickness=SicknessType.SICKNESS_NONE,
        p0_curses={CurseType.CURSE_DARK_CLOUD, CurseType.CURSE_DREAM},
    )


def test_heart_shell_cures_every_ailment(board):
    """ハートの貝がらが地獄病と全ての災いを完全に治すことを検証します。"""
    g = board(
        p0=Side(
            hp=40,
            sickness=SicknessType.SICKNESS_HELL,
            curses=[CurseType.CURSE_FOG, CurseType.CURSE_FLASH,
                    CurseType.CURSE_DARK_CLOUD, CurseType.CURSE_DREAM],
            hand=["sundries/heart-shell"],
        ),
        p1=Side(hp=40),
    )
    g.rng.deck_always("armor/wood-shield")

    g.attack("sundries/heart-shell", to_self=True)

    g.expect(p0_sickness=SicknessType.SICKNESS_NONE, p0_curses=set())


def test_guardian_pot_summons_the_specified_guardian(board):
    """守護封印のつぼで降臨する守護神を指定して検証します。

    従来は「1〜10のいずれか」という緩い検証でした（10種すべての網羅は
    test_roll_branch_coverage.py が担当します）。
    """
    g = board(p0=Side(hp=40, guardian=0, hand=["sundries/guardian-pot"]), p1=Side(hp=40))
    g.rng.deck_always("armor/wood-shield")
    g.rng.guardian_pot(int(GuardianType.SATURN))

    g.attack("sundries/guardian-pot", to_self=True)

    g.expect(p0_guardian=int(GuardianType.SATURN))


def test_sundry_on_opponent_auto_advances_without_a_super_mirror(board):
    """相手に雑貨を使ったとき、相手がスーパーミラーを持たなければ自動進行対象になることを検証します。"""
    g = board(
        p0=Side(hp=40, hand=["sundries/heaven-herb"]),
        p1=Side(hp=40, hand=["armor/wood-shield"]),
    )

    g.attack("sundries/heaven-herb")

    g.expect(phase=GamePhase.PHASE_SUNDRY_SELECT_MIRROR, actor=1)
    assert godfield_core.get_single_legal_action(g.state) == ActionType.ACTION_CONFIRM


@pytest.mark.parametrize("heals", [True, False], ids=["HP+10", "HP-10"])
def test_thump_thump_tear_swings_hp_both_ways(board, heals):
    """ドキドキ涙のHP増減を両方向とも決定的に検証します。

    従来は `hp in [30, 50]` という OR 条件で、どちらに振れたかを制御も検証も
    できていませんでした。
    """
    g = board(p0=Side(hp=40, guardian=0, hand=["sundries/thump-thump-tear"]), p1=Side(hp=40))
    g.rng.deck_always("armor/wood-shield")
    g.rng.thump_thump_tear(heals=heals)

    g.attack("sundries/thump-thump-tear", to_self=True)

    g.expect(p0_hp=50 if heals else 30)


def test_nocturnal_broom_discards_the_rest_of_your_hand(board):
    """夜空のホウキが自分の他の手札をすべて捨てさせ、自分のスロットだけ補充されることを検証します。"""
    broom = "sundries/nocturnal-broom"
    refill = "armor/leather-cap"

    g = board(
        p0=Side(hp=40, mp=20, hand=["weapons/wooden-sword", "armor/wood-shield", broom]),
        p1=Side(hp=40, mp=20),
    )
    g.rng.deck_always(refill)

    g.select(broom)
    g.target_self()

    assert g.state.get_true_hand(0, 0) == godfield_core.CARD_EMPTY, "他の手札は捨てられる"
    assert g.state.get_true_hand(0, 1) == godfield_core.CARD_EMPTY, "他の手札は捨てられる"
    assert g.state.get_true_hand(0, 2) == card_id(refill), (
        "ホウキを使ったスロットだけが補充される"
    )


def test_goddess_soap_discards_the_opponents_deployed_miracle(board):
    """女神の石けんが相手の展開済み奇跡を破棄することを検証します。"""
    soap = "sundries/goddess-s-soap"
    miracle = "miracles/fireball"

    g = board(
        p0=Side(hp=40, mp=20, hand=[soap]),
        p1=Side(hp=40, mp=20, hand=[None, None, None, None, None, miracle], deployed=[5]),
    )
    g.rng.deck_always(FILLER)

    assert g.state.get_is_deployed(1, 5) is True, "展開済みの状態を作れていない"

    g.select(soap)
    g.target_opp()
    g.confirm()  # 相手が反射せず受諾

    assert g.state.get_true_hand(1, 5) == godfield_core.CARD_EMPTY
    assert g.state.get_is_deployed(1, 5) is False


HEAVEN_HERB = "sundries/heaven-herb"
HEAVEN_HERB_MP_GAIN = 20  # 効果量そのものは test_heaven_herb_restores_mp_but_inflicts_heaven_sickness で検証


def test_a_sundry_on_yourself_resolves_immediately(board):
    """自分を対象にした雑貨がミラー確認を経ず即座に解決されることを検証します。"""
    mp = 10
    g = board(
        p0=Side(hp=40, mp=mp, hand=[HEAVEN_HERB]),
        p1=Side(hp=40, mp=mp),
    )
    g.rng.deck_always(FILLER)

    g.select(HEAVEN_HERB)
    g.target_self()

    # 天国草は「MPを全回復し天国病にする」雑貨
    g.expect(
        phase=GamePhase.PHASE_MAIN,
        actor=1,
        p0_mp=mp + HEAVEN_HERB_MP_GAIN,
        p0_sickness=SicknessType.SICKNESS_HEAVEN,
        p1_mp=mp,
        p1_sickness=SicknessType.SICKNESS_NONE,
    )


def test_a_sundry_on_the_opponent_waits_for_their_answer(board):
    """相手を対象にした雑貨がミラー確認フェイズを挟み、受諾で相手に適用されることを検証します。"""
    mp = 10
    g = board(
        p0=Side(hp=40, mp=mp, hand=[HEAVEN_HERB]),
        p1=Side(hp=40, mp=mp),
    )
    g.rng.deck_always(FILLER)

    g.select(HEAVEN_HERB)
    g.target_opp()
    g.expect(phase=GamePhase.PHASE_SUNDRY_SELECT_MIRROR, actor=1)

    g.confirm()  # 相手が受諾

    g.expect(
        phase=GamePhase.PHASE_MAIN,
        actor=1,
        p0_mp=mp,
        p0_sickness=SicknessType.SICKNESS_NONE,
        p1_mp=mp + HEAVEN_HERB_MP_GAIN,
        p1_sickness=SicknessType.SICKNESS_HEAVEN,
    )


def test_a_reflected_sundry_comes_back_to_its_user(board):
    """雑貨をスーパーミラーで反射されると、効果が使用者自身に返ることを検証します。"""
    mp = 10
    g = board(
        p0=Side(hp=40, mp=mp, hand=[HEAVEN_HERB]),
        p1=Side(hp=40, mp=mp, hand=[MIRROR]),
    )
    g.rng.deck_always(FILLER)

    g.select(HEAVEN_HERB)
    g.target_opp()

    g.select(MIRROR)  # 相手が反射
    g.expect(phase=GamePhase.PHASE_SUNDRY_SELECT_MIRROR, actor=0)

    g.confirm()  # 自分が受け入れる

    g.expect(
        p0_mp=mp + HEAVEN_HERB_MP_GAIN,
        p0_sickness=SicknessType.SICKNESS_HEAVEN,
        p1_mp=mp,
        p1_sickness=SicknessType.SICKNESS_NONE,
    )
