# ==========================================
# Merged from: tests/core/test_special_gimmicks.py
# ==========================================
import pytest

import godfield_core
from godfield_core import GamePhase
from tests.core.dsl import (
    Side,
    all_cards,
    card_feature,
    card_id,
    card_name,
    cards_where,
    dream_candidates,
)

FILLER = "armor/wood-shield"

GROUP_WEAPONS = cards_where(type="weapon", is_group_attack=True)


@pytest.mark.parametrize(
    "group_weapon", GROUP_WEAPONS, ids=[card_name(c) for c in GROUP_WEAPONS]
)
def test_earth_guardian_group_attack_opens_a_defense_phase(board, group_weapon):
    """地球神が全体攻撃武器を引いても、防御フェイズが正しく立ち上がることを検証します。

    従来は地球神が全体攻撃武器を引くまで最大20000回シードを探索していました。
    どの全体攻撃武器を引いたかは制御できず、20000回で見つからなければテスト自体が
    失敗する構造でした。しかも「たまたま最初に見つかった1種類」しか検証されません。

    現在は引くカードを名指しできるので、カードマスタにある全体攻撃武器を
    全種類まわしています。
    """
    earth = int(godfield_core.GuardianType.EARTH)

    g = board(
        p0=Side(hp=99, mp=10, money=10, hand=[FILLER]),
        p1=Side(hp=99, mp=10, money=10, guardian=earth, hand=[FILLER]),
    )
    g.rng.guardian_act(acts=True)
    # 山札は「P0の祈るドロー」「地球神のドロー」の順に消費される
    g.rng.next_draws(FILLER, group_weapon, then=FILLER)
    if card_feature(group_weapon, "accuracy", 100) < 100:
        g.rng.hits(always=True)

    g.pray()

    g.expect(phase=godfield_core.GamePhase.PHASE_DEFENSE, actor=0, attacker=1, defender=0)
    assert g.state.pending_is_group_attack is True
    assert g.state.pending_attack_source_id == group_weapon


def env_pool_observation(state):
    """EnvPool に状態を流し込み、観測バッファを1環境分だけ取り出します。

    観測レイアウトが EnvPool のバッファ経由でも壊れていないことを確認するための経路です。
    従来はここでバイトオフセット（obs_flat[462:584] など）を直書きしていましたが、
    Observation の構造を変えると黙って別の領域を読むため、C++ が公開している
    サイズ定数から算出するようにしています。
    """
    env = godfield_core.EnvPool(1)
    env.reset(42)
    env.set_state(0, state)
    return env.get_observations()


def test_env_pool_observation_matches_get_legal_actions():
    """EnvPool 経由の観測に載る action_mask が get_legal_actions と一致することを検証します。

    観測バッファのレイアウトがズレると、学習側が別の位置を合法手マスクとして
    読んでしまい、無効な行動を選び続けることになります。
    """
    state = godfield_core.InternalState()
    godfield_core.clear_state(state)
    state.current_actor_id = 0
    state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    state.set_hp(0, 40)
    state.set_hp(1, 40)
    state.set_money(0, 35)
    state.set_money(1, 75)

    obs_flat = env_pool_observation(state)

    # money は先頭付近の固定位置（hp_me, hp_opp, mp_me, mp_opp, money_me, money_opp）
    assert obs_flat[4] == pytest.approx(0.35)
    assert obs_flat[5] == pytest.approx(0.75)

    # action_mask は観測特徴量の末尾に置かれている
    mask_start = godfield_core.OBSERVATION_FEATURE_SIZE - godfield_core.ACTION_SPACE_SIZE
    mask = obs_flat[mask_start : mask_start + godfield_core.ACTION_SPACE_SIZE]

    expected = godfield_core.get_legal_actions(state)
    for i in range(godfield_core.ACTION_SPACE_SIZE):
        assert mask[i] == (1.0 if expected[i] else 0.0), f"action_mask[{i}] が一致しません"


def test_fog_hides_the_opponent_hand_from_the_cursed_player(board):
    """霧にかかると、相手の公開済み手札も見えなくなることを検証します。

    ステータスのマスキングは test_observation.py が検証しています。
    ここでは手札のマスキングを扱います。
    """
    revealed = "weapons/bronze-club"
    g = board(
        p0=Side(hp=40, mp=10, money=30),
        p1=Side(hp=50, mp=20, money=60, hand=[revealed], known_to_opp=[0]),
    )

    # 霧が無ければ、公開されている相手の手札が見える
    clear = godfield_core.get_observation(g.state, 0)
    assert clear.get_opponent_hand_cards()[0] == card_id(revealed)

    # 霧をかけると見えなくなる
    g.state.set_curses(0, godfield_core.CurseType.CURSE_FOG, True)
    fogged = godfield_core.get_observation(g.state, 0)
    assert fogged.get_opponent_hand_cards()[0] == 0, "霧の下では相手の手札は隠される"


def test_dream_masks_only_newly_drawn_cards(board):
    """夢状態では、既に持っている手札は変化せず、新たに引いたカードだけが偽装されることを検証します。"""
    real = "weapons/bronze-club"
    fake = "weapons/saw-boom-boom"
    g = board(p0=Side(hp=40, hand=[real]), p1=Side(hp=40))

    # 夢が無い状態では真のカードが見える
    assert godfield_core.get_observation(g.state, 0).get_hand_cards()[0] == card_id(real)

    # 夢をかけても、既に持っている手札は変化しない
    g.state.set_curses(0, godfield_core.CurseType.CURSE_DREAM, True)
    assert godfield_core.get_observation(g.state, 0).get_hand_cards()[0] == card_id(real)

    # 夢状態で新たに引いたカードだけが偽装される
    g.state.set_true_hand(0, 1, card_id(real))
    g.state.set_is_confirmed(0, 1, False)
    g.state.set_apparent_hand(0, 1, card_id(fake))

    obs = godfield_core.get_observation(g.state, 0)
    assert obs.get_hand_cards()[1] == card_id(fake), "見かけ上は偽装カードになる"
    assert g.state.get_true_hand(0, 1) == card_id(real), "真のカードは変わらない"


@pytest.mark.parametrize(
    ("hp_before", "hp_after", "is_done", "why"),
    [
        # 1撃目でHP0 -> お守りで復活(10) -> 自傷でHP0 -> お守りは既に消費済みで死亡
        (14, 0, True, "1撃目で死んで復活し、自傷で再度死ぬ"),
        # 1撃目ではHP6で生存（復活なし） -> 自傷でHP0 -> お守りで復活して生存
        (20, 10, False, "1撃目は耐え、自傷で死んでお守りで復活する"),
    ],
    ids=["HP14で死亡", "HP20で生存"],
)
def test_evil_broadsword_self_harm_and_amulet_timing(board, hp_before, hp_after, is_done, why):
    """邪神の大剣を自分に使った際の、自傷ダメージと太陽のお守りの発動タイミングを検証します。

    邪神の大剣は与えたダメージと同じだけ自分も受けるため、自分に使うと同じ威力を
    2回連続で受けます。お守りは1枚しかないので、1撃目で死ぬか2撃目で死ぬかによって
    最終的な生死が変わります。この境界が実装の要点です。
    """
    sword = "weapons/evil-broadsword"
    damage = card_feature(sword, "attack_power")
    assert hp_before <= damage * 2, "2撃で死にうる体力である前提のテスト"

    g = board(
        p0=Side(hp=hp_before, hand=[sword, "sundries/sun-amulet"]),
        p1=Side(hp=40),
    )
    g.rng.deck_always(FILLER)
    g.attack(sword, to_self=True)

    g.expect(p0_hp=hp_after, is_done=is_done)
    # お守りはどちらの経路でも消費される
    assert card_name(card_id("sundries/sun-amulet")) not in g.hand(0)
    if not is_done:
        g.expect(actor=1, phase=GamePhase.PHASE_MAIN)


VENUS = int(godfield_core.GuardianType.VENUS)


def venus_action(board, action_card: str, *, p0=None, p1=None):
    """P1 の金星神が指定の行動を発動し、P0 に選択が回ってきた局面を作ります。

    従来は PHASE_SUNDRY_SELECT_MIRROR を手で組み立てていましたが、実経路を通すことで
    「その局面が実際に発生しうるか」も同時に検証されます。
    """
    g = board(
        p0=p0 if p0 is not None else Side(hp=40, money=10, hand=["armor/leather-clothes"]),
        p1=p1 if p1 is not None else Side(hp=40, money=10, guardian=VENUS),
    )
    g.rng.deck_always(FILLER)
    g.rng.guardian_action_card(VENUS, action_card)
    g.discard("armor/leather-clothes")
    g.expect(phase=godfield_core.GamePhase.PHASE_SUNDRY_SELECT_MIRROR, actor=0)
    return g


@pytest.mark.parametrize("reflected", [False, True], ids=["受諾する", "反射する"])
def test_venus_bribe_gives_money_to_whoever_accepts(board, reflected):
    """わいろが「受け入れた側」にお金を与えることを、反射の有無で検証します。"""
    hand = ["armor/leather-clothes"] + (["armor/super-mirror"] if reflected else [])
    g = venus_action(
        board, "gurdians/bribe",
        p0=Side(hp=40, money=10, hand=hand),
    )
    amount = g.state.pending_attack_power
    assert amount > 0, "わいろの金額が0ならこのテストは何も検証していない"

    if reflected:
        g.select("armor/super-mirror")
        g.expect(phase=godfield_core.GamePhase.PHASE_SUNDRY_SELECT_MIRROR, actor=1)
        g.take_hit()
        # 反射されたので、発動した側（金星神の持ち主）が受け取る
        g.expect(p0_money=10, p1_money=10 + amount)
    else:
        g.take_hit()
        g.expect(p0_money=10 + amount, p1_money=10)


@pytest.mark.parametrize("reflected", [False, True], ids=["受諾する", "反射する"])
def test_venus_fine_takes_money_from_whoever_accepts(board, reflected):
    """罰金が「受け入れた側」からお金を徴収し、もう一方に渡ることを検証します。"""
    hand = ["armor/leather-clothes"] + (["armor/super-mirror"] if reflected else [])
    g = venus_action(
        board, "gurdians/fine",
        p0=Side(hp=40, money=10, hand=hand),
    )
    amount = g.state.pending_attack_power
    assert amount > 0, "罰金の金額が0ならこのテストは何も検証していない"

    if reflected:
        g.select("armor/super-mirror")
        g.expect(phase=godfield_core.GamePhase.PHASE_SUNDRY_SELECT_MIRROR, actor=1)
        g.take_hit()
        # 反射されたので、発動した側が徴収される
        g.expect(p0_money=10 + amount, p1_money=10 - amount)
    else:
        g.take_hit()
        g.expect(p0_money=10 - amount, p1_money=10 + amount)


GALE_SWORD = "weapons/severe-gale-sword"  # ATK13・命中率100%・風邪を付与
AURA = "miracles/aura"
FEVER_MASK = "armor/fever-mask"  # DEF10・被弾時に熱病を付与
SUN_AMULET = "sundries/sun-amulet"

# ターン終了時の病気による増減（エンジン側の定数）
SICKNESS_TURN_END_DELTA = {
    godfield_core.SicknessType.SICKNESS_FEVER: -2,
    godfield_core.SicknessType.SICKNESS_HELL: -5,
    godfield_core.SicknessType.SICKNESS_HEAVEN: +5,
}


def severe_gale_with_two_auras_power() -> int:
    """激烈疾風剣に＜オーラ＞を2枚重ねた攻撃力（オーラは1枚ごとに2倍）。"""
    return card_feature(GALE_SWORD, "attack_power") * 2 * 2


@pytest.mark.parametrize(
    ("num_masks", "expected_sickness"),
    [
        # 激烈疾風剣が風邪を与えたあと、熱狂仮面が1枚ごとに熱病を重ねて病気が1段階ずつ進む
        (1, godfield_core.SicknessType.SICKNESS_FEVER),
        (2, godfield_core.SicknessType.SICKNESS_HELL),
        (3, godfield_core.SicknessType.SICKNESS_HEAVEN),
    ],
    ids=["仮面1枚->熱病", "仮面2枚->地獄病", "仮面3枚->天国病"],
)
def test_fever_masks_escalate_the_sickness_one_step_each(board, num_masks, expected_sickness):
    """熱狂仮面を重ねるごとに病気が1段階ずつ悪化することを検証します。

    激烈疾風剣が風邪を与え、そこへ熱狂仮面が熱病を重ねます。すでに病気の相手に
    同等以下の病気を与えると1段階進む、という規則がこのテストの主題です。

    HPは「攻撃力 - 仮面の防御力合計」を受けたあと、ターン終了時に病気ぶんの
    増減が入ります。従来は 55 / 62 / 82 という結果の数値が直書きされており、
    どう計算されるのか読めませんでした。
    """
    power = severe_gale_with_two_auras_power()
    guard = card_feature(FEVER_MASK, "defense_power") * num_masks
    expected_hp = 99 - (power - guard) + SICKNESS_TURN_END_DELTA[expected_sickness]

    g = board(
        p0=Side(hp=99, mp=50, money=10, hand=[FEVER_MASK] * num_masks),
        p1=Side(hp=40, mp=50, money=10, hand=[GALE_SWORD, AURA, AURA]),
        actor=1,
    )
    g.rng.deck_always(FILLER)
    g.rng.sickness_worsen(False)  # ターン終了時の追加悪化は起こさない

    g.select_slots(0, 1, 2)  # 激烈疾風剣 + オーラ + オーラ
    g.target_opp()
    g.select_slots(*range(num_masks))
    g.confirm()

    g.expect(p0_sickness=expected_sickness, p0_hp=expected_hp)


def test_four_fever_masks_cause_a_fatal_seizure(board):
    """熱狂仮面4枚では天国病を超えて発作が起き、即死することを検証します。"""
    g = board(
        p0=Side(hp=99, mp=50, money=10, hand=[FEVER_MASK] * 4),
        p1=Side(hp=40, mp=50, money=10, hand=[GALE_SWORD, AURA, AURA]),
        actor=1,
    )
    g.rng.deck_always(FILLER)

    g.select_slots(0, 1, 2)
    g.target_opp()
    g.select_slots(0, 1, 2, 3)
    g.confirm()

    g.expect(p0_hp=0)


def test_seizure_death_is_survivable_with_the_sun_amulet(board):
    """発作死しても太陽のお守りがあれば復活し、天国病の回復も適用されることを検証します。

    復活後のHP10に、ターン終了時の天国病回復が乗って15になります。
    """
    heaven_heal = SICKNESS_TURN_END_DELTA[godfield_core.SicknessType.SICKNESS_HEAVEN]
    g = board(
        p0=Side(hp=99, mp=50, money=10, hand=[FEVER_MASK] * 4 + [SUN_AMULET]),
        p1=Side(hp=40, mp=50, money=10, hand=[GALE_SWORD, AURA, AURA]),
        actor=1,
    )
    g.rng.deck_always(FILLER)
    g.rng.sickness_worsen(False)

    g.select_slots(0, 1, 2)
    g.target_opp()
    g.select_slots(0, 1, 2, 3)
    g.confirm()

    g.expect(
        p0_hp=10 + heaven_heal,
        p0_sickness=godfield_core.SicknessType.SICKNESS_HEAVEN,
        is_done=False,
    )


# ==========================================
# Merged from: tests/core/test_dream.py
# ==========================================



DREAM = godfield_core.CurseType.CURSE_DREAM

# 夢状態でドローしたカードは、50%はそのまま正しく見え、残る50%は同じ夢グループの
# 「自分以外」のカードに見える。どちらの場合も未確定（is_confirmed=False）なので、
# 「見た目が変わっていないこと」は夢がかかっていない証拠にはならない。


def draw_under_dream(g, player: int, slot: int, card: str, *, disguised: bool, as_card=None):
    """夢状態のプレイヤーが `card` をドローした状況を作ります。"""
    g.rng.dream(card, disguised=disguised, as_card=as_card)
    g.state.add_card_to_hand_slot(player, slot, card_id(card), True)  # is_drawn=True


def test_dream_draw_is_unconfirmed_and_disguised_within_the_group(board):
    """夢状態でドローしたカードが未確定になり、同じ夢グループのカードに偽装されることを検証します。"""
    real = "weapons/bronze-club"
    g = board(p0=Side(hp=40, curses=[DREAM], hand=[]), p1=Side(hp=40))

    draw_under_dream(g, 0, 0, real, disguised=True)

    assert g.state.get_is_confirmed(0, 0) is False, "夢状態のドローは未確定になる"
    assert g.state.get_true_hand(0, 0) == card_id(real), "真の手札は引いたカードのまま"

    apparent_id = g.state.get_apparent_hand(0, 0)
    assert apparent_id != card_id(real), "偽装される側では必ず自分以外のカードになる"

    # 偽装先は必ず同じ夢グループ（ここでは単体・リアクションなしの通常武器）
    apparent = next(c for c in all_cards() if c["id"] == apparent_id)
    assert apparent.get("type") == "weapon"
    assert not apparent.get("is_group_attack")
    assert not apparent.get("reaction_type")


def test_dream_disguise_never_picks_the_card_itself(board):
    """偽装先の候補に元のカード自身が含まれないことを、候補一覧を全走査して検証します。

    自分自身が候補に混ざっていると「正しく見える確率」が 50% を超えてしまいます。
    """
    for real in ["weapons/bronze-club", "armor/leather-clothes", "sundries/sun-amulet"]:
        candidates = dream_candidates(real)
        assert candidates, f"{real} は夢グループを持つはずです"
        assert card_id(real) not in candidates, f"{real} の偽装先候補に自分自身が入っています"


def test_dream_draw_can_look_exactly_like_the_true_card(board):
    """偽装されなかった場合、見た目は真のカードのまま・未確定のままであることを検証します。

    「見た目が変わっていること」は夢状態の判定条件にできません。夢がかかっているか
    どうかは is_confirmed で判断する必要があります。
    """
    real = "weapons/bronze-club"
    g = board(p0=Side(hp=40, curses=[DREAM], hand=[]), p1=Side(hp=40))

    draw_under_dream(g, 0, 0, real, disguised=False)

    assert g.state.get_apparent_hand(0, 0) == card_id(real), "偽装されなければ見た目は変わらない"
    assert g.state.get_is_confirmed(0, 0) is False, "見た目が同じでも未確定であることに変わりはない"
    assert g.rng.consumed(godfield_core.RollKind.DREAM_FAKE_CARD) == 0, (
        "偽装されない場合は偽装先の抽選自体が起きない"
    )


def test_miracles_are_not_disguised_by_dream(board):
    """奇跡は夢の影響を受けず、ドローしても即座に確定することを検証します。"""
    miracle = "miracles/fireball"
    g = board(p0=Side(hp=40, curses=[DREAM], hand=[]), p1=Side(hp=40))

    g.state.add_card_to_hand_slot(0, 0, card_id(miracle), True)

    assert g.state.get_is_confirmed(0, 0) is True
    assert g.state.get_apparent_hand(0, 0) == card_id(miracle)


def test_dream_card_is_finalized_when_the_true_card_is_playable(board):
    """偽装されたカードを使い、真のカードもそのフェイズで合法なら確定して実行されることを検証します。"""
    real, fake = "weapons/punch", "weapons/bronze-club"
    g = board(p0=Side(hp=40, curses=[DREAM], hand=[]), p1=Side(hp=40))

    g.state.add_card_to_hand_slot(0, 0, card_id(real), False)
    g.state.set_apparent_hand(0, 0, card_id(fake))
    g.state.set_is_confirmed(0, 0, False)

    g.select_slots(0)
    g.expect(phase=godfield_core.GamePhase.PHASE_ATTACK_PLUS)
    assert g.state.get_is_confirmed(0, 0) is False, "仮置きの時点ではまだ確定しない"

    g.target_opp()

    # 確定し、偽装先ではなく真のカードの攻撃力で解決される
    assert g.state.get_is_confirmed(0, 0) is True
    assert g.state.get_apparent_hand(0, 0) == card_id(real)
    g.expect(
        phase=godfield_core.GamePhase.PHASE_DEFENSE,
        pending_power=card_feature(real, "attack_power"),
    )
    assert card_feature(real, "attack_power") != card_feature(fake, "attack_power"), (
        "真偽で攻撃力が異なる組み合わせでないと、確定処理を検証できない"
    )


def test_dream_card_returns_to_hand_when_the_true_card_is_illegal(board):
    """真のカードがそのフェイズで非合法なら、仮置きが取り消されて確定した状態で手札に戻ることを検証します。"""
    real, fake = "armor/wood-shield", "weapons/bronze-club"
    g = board(p0=Side(hp=40, curses=[DREAM], hand=[]), p1=Side(hp=40))

    g.state.add_card_to_hand_slot(0, 0, card_id(real), False)
    g.state.set_apparent_hand(0, 0, card_id(fake))
    g.state.set_is_confirmed(0, 0, False)

    g.select_slots(0)
    g.expect(phase=godfield_core.GamePhase.PHASE_ATTACK_PLUS)

    g.target_opp()

    # 防具では攻撃できないので、仮置きが解除されメインフェイズに戻る
    g.expect(phase=godfield_core.GamePhase.PHASE_MAIN)
    assert g.state.get_num_staged_cards(0) == 0
    assert g.state.get_is_confirmed(0, 0) is True, "正体が露見したので確定する"
    assert g.state.get_apparent_hand(0, 0) == card_id(real)


def test_card_offered_for_purchase_is_finalized(board):
    """「買う」の対象にされたカードは、実際に買われたかに関わらず確定することを検証します。"""
    real, fake = "weapons/bronze-club", "weapons/silver-club"
    g = board(
        p0=Side(hp=40, money=50, hand=["deals/buy"]),
        p1=Side(hp=40, money=50, curses=[DREAM], hand=[]),
    )
    g.rng.deck_always(FILLER)

    g.state.add_card_to_hand_slot(1, 0, card_id(real), False)
    g.state.set_apparent_hand(1, 0, card_id(fake))
    g.state.set_is_confirmed(1, 0, False)

    g.select("deals/buy")
    g.target_opp()
    g.expect(phase=godfield_core.GamePhase.PHASE_BUY_SELECT_MIRROR, actor=1)

    g.confirm()  # 相手が反射せず受諾

    offered = g.state.get_staged_card(1, 0)
    assert offered == 0
    assert g.state.get_is_confirmed(1, offered) is True, "出品されたカードは確定する"
    assert g.state.get_apparent_hand(1, offered) == card_id(real)


def test_curing_dream_restores_the_true_appearance(board):
    """夢が解除されると、偽装されていた手札が本来の見た目に戻ることを検証します。"""
    real = "weapons/bronze-club"
    g = board(p0=Side(hp=40, mp=10, curses=[DREAM], hand=[None, "miracles/song"]), p1=Side(hp=40))
    g.rng.deck_always(FILLER)

    draw_under_dream(g, 0, 0, real, disguised=True)
    assert g.state.get_apparent_hand(0, 0) != card_id(real)

    g.attack("miracles/song", to_self=True)

    g.expect(p0_curses=set())
    assert g.state.get_is_confirmed(0, 0) is True
    assert g.state.get_apparent_hand(0, 0) == card_id(real), "本物の見た目に戻る"


# ==========================================
# Merged from: tests/core/test_mushroom.py
# ==========================================



def run_mushroom_outbreak(board, *, preloaded_turns: int = 0):
    """「きのこ大発生」を発生させ、ご乱心が終わるまで自動進行させた局面を返します。

    `preloaded_turns` に値を入れると、すでにご乱心中の状態から重ねて発生させた
    ケースを再現できます。
    """
    start_turn = 10
    g = board(
        p0=Side(hp=40, mp=10, money=10, hand=["sundries/string-of-fate"]),
        p1=Side(hp=40, mp=10, money=10),
        turn=start_turn,
        mushroom_turns=preloaded_turns,
    )
    g.rng.deck_always(FILLER)
    g.rng.phenomenon(godfield_core.PhenomenonType.MUSHROOM)
    g.rng.force(godfield_core.RollKind.MUSHROOM_ACTION, 0)  # 常に先頭の合法手を選ぶ

    g.attack("sundries/string-of-fate", to_self=True)
    return g, start_turn


def test_mushroom_outbreak_auto_advances_six_turns(board):
    """きのこ大発生でご乱心の6ターンが自動進行し、通常操作に戻ることを検証します。"""
    g, start_turn = run_mushroom_outbreak(board)

    g.expect(turn=start_turn + 6, phase=godfield_core.GamePhase.PHASE_MAIN)
    assert g.state.mushroom_turns == 0, "ご乱心が終了しているべきです"
    assert g.rng.consumed(godfield_core.RollKind.MUSHROOM_ACTION) > 0, (
        "自動進行中に行動が選ばれているべきです"
    )


def test_mushroom_outbreak_adds_to_the_remaining_turns(board):
    """ご乱心中にさらにきのこ大発生が起きると、残りターン数が上書きではなく加算されることを検証します。

    【重要】従来のテストは C++ を一切呼ばず、Python 側で
        runner.state.mushroom_turns += 6
        assert runner.state.mushroom_turns == 9
    としていた。これは Python の足し算を確認しているだけで、C++ の実装が
    上書き（= 6）に変わっても検出できない完全に空のテストだった。

    ここでは「すでに3ターン残っている状態」と「0の状態」で発生させ、
    自動進行するターン数の差が事前の残りターン数と一致することを確認する。
    加算ではなく上書きなら、どちらも同じターン数しか進まない。
    """
    preloaded = 3

    fresh, start = run_mushroom_outbreak(board, preloaded_turns=0)
    stacked, _ = run_mushroom_outbreak(board, preloaded_turns=preloaded)

    fresh_advanced = fresh.state.current_turn - start
    stacked_advanced = stacked.state.current_turn - start

    assert stacked_advanced == fresh_advanced + preloaded, (
        f"残りターンに加算されるべきです（加算なら {fresh_advanced + preloaded}、"
        f"上書きなら {fresh_advanced}）。実際: {stacked_advanced}"
    )
    assert stacked.state.mushroom_turns == 0
