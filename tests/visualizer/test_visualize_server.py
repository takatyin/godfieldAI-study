"""visualizer が手札に表示するラベル（power_label / 仮置き合計バッジ）の検証。

【移行メモ】
表示ラベルの数値部分がすべて直書きでした（'¥4' '守3' '攻12' '+攻10'）。
カードの性能を変えるとラベルも変わるはずですが、どちらが正しいのか
コードから読めません。数値はカードマスタから引き、テストが検証するのは
「どの場面でどの数値が選ばれるか」という表示ルールに絞りました。

局面の組み立ても、フェイズや仮置き状態を直接代入していた箇所を実際の操作に
置き換えています（`set_num_staged_cards` などを手で設定すると、その状態が
本当に発生しうるのかが検証されないため）。
"""

import pytest

import godfield_core
from godfield_core import GamePhase
from tests.core.dsl import Side, card_feature, card_id
from visualizer.constants import CARDS_BY_ID
from visualizer.presenter import (
    compute_smart_action_label,
    compute_staged_total_badge,
    serialize_observation,
)

FILLER = "armor/wood-shield"

ACTION_CONFIRM = 18
ACTION_DEAL_NO = 19
ACTION_DISCARD = 21


def view(g, player: int) -> dict:
    """指定プレイヤーの視点で、visualizer に渡る表示用データを組み立てます。"""
    obs = godfield_core.get_observation(g.state, player)
    return serialize_observation(obs, player_id=player, state=g.state)


def label_of(data: dict, card: str, where: str = "hand") -> str:
    """表示データから指定カードの power_label を取り出します。"""
    cid = card_id(card)
    for entry in data[where]:
        if entry["id"] == cid:
            return entry["power_label"]
    raise AssertionError(f"{where} に {card} がありません: {data[where]}")


# ============================================================================
# 売却モード: 価格を表示する
# ============================================================================


@pytest.mark.parametrize(
    "item",
    [FILLER, "armor/ogre-s-gauntlet"],
    ids=["安いカード", "高いカード"],
)
def test_the_sell_phase_shows_the_price_of_every_card(board, item):
    """売却フェイズでは、種別を問わず手札のカードに価格が表示されることを検証します。"""
    g = board(
        p0=Side(hp=40, mp=20, hand=["deals/sell", item]),
        p1=Side(hp=40, mp=20),
    )
    g.rng.deck_always(FILLER)

    g.select("deals/sell")
    g.expect(phase=GamePhase.PHASE_SELL_SELECT)

    assert label_of(view(g, 0), item) == f"¥{card_feature(item, 'price')}"


def test_the_price_label_only_appears_while_selling(board):
    """価格ラベルが売却フェイズ以外では出ないことを検証します。"""
    item = "armor/ogre-s-gauntlet"
    g = board(
        p0=Side(hp=40, mp=20, hand=["deals/sell", item]),
        p1=Side(hp=40, mp=20),
    )
    g.rng.deck_always(FILLER)

    # メインフェイズでは価格ではなく本来の性能が出る
    assert label_of(view(g, 0), item) == f"守{card_feature(item, 'defense_power')}"

    g.select("deals/sell")
    assert label_of(view(g, 0), item) == f"¥{card_feature(item, 'price')}"


def test_the_card_being_used_as_the_sell_trigger_shows_no_price(board):
    """出品に使っている「売る」自身には価格が出ず、手札に残る同名カードには出ることを検証します。"""
    sell = "deals/sell"
    price = card_feature(sell, "price")

    g = board(
        p0=Side(hp=40, mp=20, hand=[sell, sell]),
        p1=Side(hp=40, mp=20),
    )
    g.rng.deck_always(FILLER)

    g.select_slots(0)  # 1枚目をトリガーとして使う
    g.expect(phase=GamePhase.PHASE_SELL_SELECT)

    data = view(g, 0)
    assert data["hand"][0]["power_label"] == "", "使用中の「売る」に価格は出さない"
    assert data["hand"][1]["power_label"] == f"¥{price}", "手札に残る「売る」には価格を出す"

    # 2枚目を商品として出品すると、仮置きの合計バッジに商品の価格が出る
    g.select_slots(1)

    data = view(g, 0)
    assert data["hand"][0]["power_label"] == ""
    assert data["hand"][1]["power_label"] == ""
    assert len(data["staged"]) == 2
    assert data["staged"][0]["power_label"] == "", "トリガーの「売る」には価格を出さない"
    assert data["staged"][1]["power_label"] == f"¥{price}", "商品には価格を出す"
    assert data["staged_total_badge"]["label"] == f"¥{price}"


def test_the_sell_trigger_can_be_any_slot(board):
    """トリガーに使う「売る」がスロット0でなくても表示が正しいことを検証します。

    実装がスロット0を特別扱いしていないかの確認です。
    """
    sell = "deals/sell"
    g = board(
        p0=Side(hp=40, mp=20, hand=[sell, sell]),
        p1=Side(hp=40, mp=20),
    )
    g.rng.deck_always(FILLER)

    g.select_slots(1)  # 2枚目をトリガーにする

    data = view(g, 0)
    assert data["hand"][0]["power_label"] == f"¥{card_feature(sell, 'price')}"
    assert data["hand"][1]["power_label"] == ""
    assert len(data["staged"]) == 1
    assert data["staged"][0]["power_label"] == ""


# ============================================================================
# リアクション防具: 「弾く」と表示されるのはそれが実際に効く場面だけ
# ============================================================================


def test_a_reaction_armor_shows_bounce_only_as_the_first_card(board):
    """リアクション防具が「弾く」と出るのは1枚目のときだけであることを検証します。"""
    first, second = "armor/sky-gauntlet", "armor/sky-boots"

    g = board(
        p0=Side(hp=40, mp=20, hand=["miracles/flame"]),
        p1=Side(hp=40, mp=20, hand=[first, second]),
    )
    g.rng.deck_always(FILLER)

    g.attack("miracles/flame")
    g.expect(phase=GamePhase.PHASE_MIRACLE_DEFENSE, actor=1)

    # まだ何も置いていないので、リアクションとして働ける
    assert label_of(view(g, 1), first) == "弾く"

    g.select(first)

    # 2枚目はリアクションにならないので、防御力の表示に戻る
    assert label_of(view(g, 1), second) == f"守{card_feature(second, 'defense_power')}"


def test_a_miracle_only_reaction_armor_shows_its_defense_against_a_physical_attack(board):
    """奇跡にしか効かないリアクション防具が、物理攻撃では防御力表示になることを検証します。"""
    armor = "armor/sky-gauntlet"

    g = board(
        p0=Side(hp=40, mp=20, hand=["weapons/plate-of-strike"]),
        p1=Side(hp=40, mp=20, hand=[armor]),
    )
    g.rng.deck_always(FILLER)

    g.attack("weapons/plate-of-strike")
    g.expect(phase=GamePhase.PHASE_DEFENSE, actor=1)

    assert label_of(view(g, 1), armor) == f"守{card_feature(armor, 'defense_power')}"


# ============================================================================
# フェイズによって役割が変わるカード
# ============================================================================


def test_a_spiritual_card_shows_zero_cost_only_while_a_miracle_is_staged(board):
    """精霊系カードが「消費0」と出るのは、奇跡を仮置きしている間だけであることを検証します。"""
    staff = "weapons/spiritual-staff"

    g = board(
        p0=Side(hp=40, mp=20, hand=["miracles/flame", staff]),
        p1=Side(hp=40, mp=20),
    )
    g.rng.deck_always(FILLER)

    # 仮置き場が空なら、本来の攻撃力が出る
    assert label_of(view(g, 0), staff) == f"攻{card_feature(staff, 'attack_power')}"

    g.select("miracles/flame")
    g.expect(phase=GamePhase.PHASE_MIRACLE_PLUS)

    assert label_of(view(g, 0), staff) == "消費0"


def test_a_dual_use_armor_switches_from_defense_to_plus_attack(board):
    """攻守兼用の防具が、攻撃プラスフェイズで防御力表示から攻撃力表示に切り替わることを検証します。"""
    helm = "armor/ogre-s-helm"

    g = board(
        p0=Side(hp=40, mp=20, hand=["weapons/plate-of-strike", helm]),
        p1=Side(hp=40, mp=20),
    )
    g.rng.deck_always(FILLER)

    # メインでは単体攻撃に使えないので、防具として見せる
    g.expect(phase=GamePhase.PHASE_MAIN)
    assert label_of(view(g, 0), helm) == f"守{card_feature(helm, 'defense_power')}"

    g.select("weapons/plate-of-strike")
    g.expect(phase=GamePhase.PHASE_ATTACK_PLUS)

    assert label_of(view(g, 0), helm) == f"+攻{card_feature(helm, 'attack_power')}"


def test_the_attack_plus_phase_labels_each_kind_of_booster(board):
    """攻撃プラスフェイズで、加算・倍化・全体化がそれぞれ区別して表示されることを検証します。"""
    powder = "sundries/strength-powder"
    aura = "miracles/aura"
    mirage = "miracles/mirage"

    g = board(
        p0=Side(hp=40, mp=20, hand=["weapons/plate-of-strike", powder, aura, mirage]),
        p1=Side(hp=40, mp=20),
    )
    g.rng.deck_always(FILLER)

    g.select("weapons/plate-of-strike")
    g.expect(phase=GamePhase.PHASE_ATTACK_PLUS)

    data = view(g, 0)
    assert label_of(data, powder) == f"+攻{card_feature(powder, 'attack_power')}"
    assert label_of(data, aura) == "2倍"
    assert label_of(data, mirage) == "全体"


@pytest.mark.parametrize(
    ("weapon", "expected_prefix"),
    [
        ("weapons/blowgun", "+攻"),       # 武器かつプラス武器
        ("weapons/wooden-sword", "攻"),   # 通常武器のみ
    ],
    ids=["プラス武器を兼ねる", "通常武器のみ"],
)
def test_the_main_phase_marks_which_weapons_can_be_stacked(board, weapon, expected_prefix):
    """メインフェイズで、重ねがけできる武器が「+攻」として区別されることを検証します。"""
    g = board(p0=Side(hp=40, mp=20, hand=[weapon]), p1=Side(hp=40, mp=20))
    g.rng.deck_always(FILLER)

    g.expect(phase=GamePhase.PHASE_MAIN)
    assert label_of(view(g, 0), weapon) == f"{expected_prefix}{card_feature(weapon, 'attack_power')}"


def test_a_dual_use_weapon_contributes_its_defense_to_the_staged_badge(board):
    """武器を防御に使ったとき、仮置き合計バッジに防御力が計上されることを検証します。"""
    sword_shield = "weapons/sword-shield"

    g = board(
        p0=Side(hp=40, mp=20, hand=["weapons/plate-of-strike"]),
        p1=Side(hp=40, mp=20, hand=[sword_shield]),
    )
    g.rng.deck_always(FILLER)

    g.attack("weapons/plate-of-strike")
    g.select(sword_shield)

    obs = godfield_core.get_observation(g.state, 1)
    staged = [CARDS_BY_ID.get(cid) for cid in obs.get_staged_cards() if cid != -1]

    badge = compute_staged_total_badge(staged, player_id=1, game_state=g.state)
    assert badge is not None
    assert badge["label"] == f"守{card_feature(sword_shield, 'defense_power')}"


# ============================================================================
# 確定ボタンの文言
#
# ここは局面の遷移ではなく「フェイズ名と仮置き内容からどの文言を選ぶか」という
# 純粋な写像の検証なので、フェイズを直接指定しています。
# ============================================================================


@pytest.mark.parametrize(
    ("phase", "expected"),
    [
        (GamePhase.PHASE_BUY, "買う"),
        (GamePhase.PHASE_SELL_SELECT, "承諾"),
    ],
    ids=["購入フェイズ", "売却フェイズ"],
)
def test_the_confirm_button_is_named_after_the_phase(board, phase, expected):
    """確定ボタンの文言がフェイズごとに変わることを検証します。"""
    g = board(phase=phase)
    assert compute_smart_action_label(ACTION_CONFIRM, [], g.state) == expected


def test_the_discard_button_keeps_its_name(board):
    """「捨てる」はフェイズによらず同じ文言であることを検証します。"""
    g = board(phase=GamePhase.PHASE_SELL_SELECT)
    assert compute_smart_action_label(ACTION_DISCARD, [], g.state) == "捨てる"


def test_the_refusal_button_is_named_after_the_deal(board):
    """購入フェイズでの拒否が「買わない」と表示されることを検証します。"""
    g = board(phase=GamePhase.PHASE_BUY)
    assert compute_smart_action_label(ACTION_DEAL_NO, [], g.state) == "買わない"


@pytest.mark.parametrize(
    "phase",
    [
        GamePhase.PHASE_BUY_SELECT_MIRROR,
        GamePhase.PHASE_SELL_SELECT_MIRROR,
        GamePhase.PHASE_SUNDRY_SELECT_MIRROR,
    ],
    ids=["買う", "売る", "雑貨"],
)
def test_the_mirror_button_reflects_whether_a_mirror_is_staged(board, phase):
    """反射確認フェイズで、スーパーミラーを置いているかどうかで文言が変わることを検証します。"""
    g = board(phase=phase)

    assert compute_smart_action_label(ACTION_DEAL_NO, [], g.state) == "受け入れる"

    mirror = [CARDS_BY_ID[card_id("armor/super-mirror")]]
    assert compute_smart_action_label(ACTION_DEAL_NO, mirror, g.state) == "はね返す"


# ==========================================
# 相手の手札の描画（スロット位置と表示可否）
# ==========================================


def _opp_hand(state, player_id):
    """serialize_observation が返す「相手の手札」をスロット番号で引ける辞書にします。"""
    data = serialize_observation(godfield_core.get_observation(state, player_id), player_id, state)
    return {c["slot_idx"]: c for c in data["opponent_hand"] if c}


def test_opponent_cards_are_rendered_at_their_real_slot(board):
    """相手の公開カードが、実際のスロット位置に描画されることを検証します。

    観測の opponent_hand_cards は「公開されているカードだけを左詰め」した配列で、
    その添字はスロット番号ではありません。以前はこれをスロット番号として使って
    いたため、スロット5の公開カードがスロット0に描かれ、表示可否の判定も
    別のスロットを見ていました。
    """
    hidden_card = "armor/wood-shield"
    revealed = "weapons/bronze-club"

    g = board(
        p0=Side(hp=99),
        p1=Side(hp=99, hand=[hidden_card] + [None] * 4 + [revealed]),
    )
    g.state.set_is_known_to_opp(1, 5, True)

    slots = _opp_hand(g.state, 0)

    assert slots[5]["id"] == card_id(revealed), (
        f"公開カードはスロット5に描かれるべきです: {slots}"
    )
    assert slots[5]["hidden"] is False
    assert slots[0]["hidden"] is True, "非公開のカードは裏向きで描かれるべきです"


def test_a_revealed_exchange_card_is_not_treated_as_hidden(board):
    """公開された「両替」が裏向き扱いにならないことを検証します。

    両替はカードID 0 です。以前は 0 を「見えない」の目印として使っていたため、
    公開されているのに裏向きで描かれていました。
    """
    exchange = "deals/exchange"
    assert card_id(exchange) == 0, "この検証は両替のIDが0であることが前提です"

    g = board(p0=Side(hp=99), p1=Side(hp=99, hand=[exchange]))
    g.state.set_is_known_to_opp(1, 0, True)

    slots = _opp_hand(g.state, 0)
    assert slots[0]["id"] == 0
    assert slots[0]["hidden"] is False, "公開された両替が裏向き扱いになっています"


@pytest.mark.parametrize("owner", [0, 1], ids=["自分が展開", "相手が展開"])
def test_serializing_a_deployed_miracle_does_not_crash(board, owner):
    """展開済みの奇跡がある局面を可視化できることを検証します。

    presenter は展開順を得るために state.get_num_deployed_miracles() /
    get_deployed_miracle_order() を呼んでいましたが、これらは C++ 側に存在せず、
    奇跡を展開した瞬間に AttributeError で可視化サーバーが落ちていました。

    エンジンは展開順を保持していないため、現在はスロット番号を並び順として
    使っています。
    """
    miracle = "miracles/flame"
    g = board(
        p0=Side(hp=99, mp=99, hand=[miracle]),
        p1=Side(hp=99, mp=99, hand=[miracle]),
    )
    g.state.set_is_deployed(owner, 0, True)
    g.state.set_is_known_to_opp(owner, 0, True)

    data = serialize_observation(godfield_core.get_observation(g.state, 0), 0, g.state)

    key = "hand" if owner == 0 else "opponent_hand"
    deployed = [c for c in data[key] if c and c["deployed"]]
    assert deployed, f"展開済みの奇跡が {key} に現れるべきです"
    assert deployed[0]["deployed_order"] >= 0, (
        "展開済みのカードには並び順が付くべきです（フロントがこの値で並べ替える）"
    )


def test_an_undeployed_card_has_no_deploy_order(board):
    """展開していないカードの並び順が -1 になることを検証します。

    上のテストが「常に0以上が返る」だけを見ていないことの担保です。
    """
    g = board(p0=Side(hp=99, mp=99, hand=["miracles/flame"]), p1=Side(hp=99))

    data = serialize_observation(godfield_core.get_observation(g.state, 0), 0, g.state)
    card = next(c for c in data["hand"] if c)

    assert card["deployed"] is False
    assert card["deployed_order"] == -1


@pytest.mark.parametrize("seed", range(3))
def test_serialization_survives_a_whole_random_game(seed):
    """ランダム対戦の全局面を可視化できることを検証します。

    可視化サーバーは毎ステップ、両プレイヤーぶんのシリアライズとイベント整形を
    行います。稀な局面で例外が出るとプレイ中に切断されるため、局面を名指しせず
    通しで踏みます（実際に「奇跡を展開すると必ず落ちる」不具合がありました）。

    展開済み奇跡のある局面に到達したことも確認します。到達していなければ、
    上記の不具合を踏めていないことになるためです。
    """
    import numpy as np

    from visualizer.event_formatter import format_event_log

    pool = godfield_core.EnvPool(1)
    pool.reset(seed)
    rng = np.random.default_rng(seed)

    saw_deployed = False
    for _ in range(400):
        state = pool.get_state(0)
        if any(state.get_is_deployed(p, i) for p in (0, 1) for i in range(18)):
            saw_deployed = True

        for pid in (0, 1):
            obs = godfield_core.get_observation(state, pid)
            serialize_observation(obs, pid, state)
            for event in obs.get_history():
                format_event_log(event, pid)

        legal = np.flatnonzero(np.array(godfield_core.get_legal_actions(state), dtype=bool))
        assert legal.size > 0, "合法手が0件です（進行不能）"
        pool.step_subset([0], [int(rng.choice(legal))])

    assert saw_deployed, (
        "展開済み奇跡のある局面に到達していないため、この検証は空振りしています"
    )
