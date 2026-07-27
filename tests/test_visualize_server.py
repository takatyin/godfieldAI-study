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
