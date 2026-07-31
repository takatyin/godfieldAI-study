"""仮置き中に更新される pending 情報（攻撃力・属性・全体攻撃フラグ・防御力）の検証。

【移行メモ】
このファイルは全体が生のカードID直書き（`create_game_with_hand([23, 63])`）で
書かれていました。カードマスタは `tools/build_cards.py` で生成されるため、
YAML にカードを1枚挿すだけで以降のIDがずれ、テストは落ちずに「別のカードの
組み合わせ」を検証し始めます。実際コメントの `# ID 6: 弓` は吹き矢でした。

攻撃力・属性もすべて直書きだったので、カードの性能を変えたときに
「どちらが正しいのか」が分からないまま落ちます。すべてカードマスタから
引くようにしました。
"""

import pytest

from godfield_core import Element, GamePhase
from tests.core.dsl import Side, card_feature, element_of

FILLER = "armor/wood-shield"

GLAIVE = "weapons/glaive-classic"                       # 無属性 ATK7
WAND_OF_IGNITION = "weapons/wand-of-ignition"           # 火属性 ATK2（属性を火に染める）
WAND_OF_MYSTIC_WATER = "weapons/wand-of-mystic-water"   # 水属性 ATK5（属性を水に染める）
BLOWGUN = "weapons/blowgun"                             # 無属性 ATK1（プラス武器）
MAGICAL_STICK = "weapons/magical-stick"                 # 残りMPを攻撃力に変える
METEOR = "miracles/meteor"                              # 光属性 ATK10 MP7
FIREBALL = "miracles/fireball"                          # 火属性 ATK2 MP2
BLAZE_BLADE = "weapons/blaze-blade"                     # 火属性 ATK5
JAVELIN = "weapons/paleolithic-javelin"                 # 土属性 ATK5
MIRAGE = "miracles/mirage"                              # 全体攻撃化
AURA = "miracles/aura"                                  # 攻撃力2倍・無属性化

# マジカルステッキは残りMP1につき攻撃力2を生む
MAGICAL_STICK_POWER_PER_MP = 2


def atk(card: str) -> int:
    return card_feature(card, "attack_power")


def defense(card: str) -> int:
    return card_feature(card, "defense_power")


def mp_cost(card: str) -> int:
    return card_feature(card, "mp_cost", 0) or 0


def test_a_wand_dyes_the_whole_stack_with_its_element(board):
    """ワンドを重ねると、仮置きの時点で攻撃全体がその属性に染まることを検証します。"""
    assert element_of(GLAIVE) == Element.ELEM_NONE
    assert element_of(WAND_OF_IGNITION) == Element.ELEM_FIRE

    g = board(
        p0=Side(hp=40, mp=50, money=99, hand=[GLAIVE, WAND_OF_IGNITION]),
        p1=Side(hp=40, mp=50, money=99),
    )
    g.rng.deck_always(FILLER)

    g.select(GLAIVE)
    g.expect(pending_power=atk(GLAIVE), pending_element=Element.ELEM_NONE)

    g.select(WAND_OF_IGNITION)
    g.expect(
        pending_power=atk(GLAIVE) + atk(WAND_OF_IGNITION),
        pending_element=Element.ELEM_FIRE,
    )


def test_stacking_an_un_elemental_weapon_only_adds_power(board):
    """無属性のプラス武器を重ねても、属性は変わらず攻撃力だけ加算されることを検証します。"""
    assert element_of(BLOWGUN) == Element.ELEM_NONE

    g = board(
        p0=Side(hp=40, mp=50, money=99, hand=[GLAIVE, BLOWGUN]),
        p1=Side(hp=40, mp=50, money=99),
    )
    g.rng.deck_always(FILLER)

    g.select(GLAIVE)
    g.expect(pending_power=atk(GLAIVE), pending_element=Element.ELEM_NONE)

    g.select(BLOWGUN)
    g.expect(
        pending_power=atk(GLAIVE) + atk(BLOWGUN),
        pending_element=Element.ELEM_NONE,
    )


def test_the_magical_stick_recomputes_when_a_mp_cost_card_is_added(board):
    """マジカルステッキの攻撃力が、後から重ねたMP消費カードのぶんだけ即座に減ることを検証します。"""
    mp = 10
    assert 0 < mp_cost(METEOR) < mp, "残りMPが残る組み合わせでないと再計算を検証できない"

    g = board(
        p0=Side(hp=40, mp=mp, money=99, hand=[MAGICAL_STICK, METEOR]),
        p1=Side(hp=40, mp=50, money=99),
    )
    g.rng.deck_always(FILLER)

    # 他にMPを使うカードが無いので、MPを全部ステッキに注げる
    g.select(MAGICAL_STICK)
    g.expect(
        pending_power=mp * MAGICAL_STICK_POWER_PER_MP,
        pending_element=Element.ELEM_NONE,
    )

    # ＜流星＞のMP消費ぶんだけ、ステッキに回せる残りMPが減る
    g.select(METEOR)
    leftover = mp - mp_cost(METEOR)
    g.expect(pending_power=leftover * MAGICAL_STICK_POWER_PER_MP + atk(METEOR))


def test_stacked_armor_sums_its_defense_power_while_staged(board):
    """防具を重ねた時点で、合計防御力が仮置き情報に反映されることを検証します。

    従来は pending_attack_* を直接代入して防御フェイズを組み立てていました。
    実際に攻撃を受けて同じ局面に到達します。
    """
    clothes = "armor/leather-clothes"
    gauntlet = "armor/iron-gauntlet"

    g = board(
        p0=Side(hp=40, mp=50, money=99, hand=[GLAIVE]),
        p1=Side(hp=40, mp=50, money=99, hand=[clothes, gauntlet]),
    )
    g.rng.deck_always(FILLER)

    g.attack(GLAIVE)
    g.expect(phase=GamePhase.PHASE_DEFENSE, actor=1, pending_defense=0)

    g.select(clothes)
    g.expect(pending_defense=defense(clothes))

    g.select(gauntlet)
    g.expect(pending_defense=defense(clothes) + defense(gauntlet))


def test_same_element_cards_keep_the_element_and_sum_their_power(board):
    """火属性で揃えた重ねがけで、属性が保たれて攻撃力が素直に足されることを検証します。"""
    stack = [BLAZE_BLADE, METEOR, FIREBALL]
    for card in (BLAZE_BLADE, FIREBALL):
        assert element_of(card) == Element.ELEM_FIRE
    # ＜流星＞は光属性だが、光は中立なのでベースの火が維持される
    assert element_of(METEOR) == Element.ELEM_LIGHT

    g = board(
        p0=Side(hp=40, mp=50, money=99, hand=list(stack)),
        p1=Side(hp=40, mp=50, money=99),
    )
    g.rng.deck_always(FILLER)

    running = 0
    for card in stack:
        g.select(card)
        running += atk(card)
        g.expect(pending_power=running, pending_element=Element.ELEM_FIRE)


def test_a_long_stack_recomputes_element_power_and_group_flag_at_every_step(board):
    """長い重ねがけの各段階で、属性・攻撃力・全体攻撃フラグが正しく再計算されることを検証します。

    旧石器ジャベリン(土) → 魔水のワンド(水) → ＜流星＞(光) → ＜蜃気楼＞(全体化)
    → 発火のワンド(火) → ＜オーラ＞(2倍) の順に重ねます。
    """
    g = board(
        p0=Side(
            hp=40, mp=50, money=99,
            hand=[JAVELIN, WAND_OF_MYSTIC_WATER, METEOR, MIRAGE, WAND_OF_IGNITION, AURA],
        ),
        p1=Side(hp=40, mp=50, money=99),
    )
    g.rng.deck_always(FILLER)

    # 1. 土属性の武器そのまま
    g.select(JAVELIN)
    g.expect(pending_power=atk(JAVELIN), pending_element=Element.ELEM_STONE)
    assert g.state.pending_is_group_attack is False

    # 2. ワンドは属性を上書きする（土 → 水）
    power = atk(JAVELIN) + atk(WAND_OF_MYSTIC_WATER)
    g.select(WAND_OF_MYSTIC_WATER)
    g.expect(pending_power=power, pending_element=Element.ELEM_WATER)
    assert g.state.pending_is_group_attack is False

    # 3. ワンドの後ろに置いた光属性も水に染まったまま
    power += atk(METEOR)
    g.select(METEOR)
    g.expect(pending_power=power, pending_element=Element.ELEM_WATER)
    assert g.state.pending_is_group_attack is False

    # 4. ＜蜃気楼＞は無属性なので属性が打ち消され、全体攻撃になる
    g.select(MIRAGE)
    g.expect(pending_power=power, pending_element=Element.ELEM_NONE)
    assert g.state.pending_is_group_attack is True, "＜蜃気楼＞で全体攻撃になるべきです"

    # 5. 後から置いたワンドが属性を再度上書きする。全体攻撃は維持される
    power += atk(WAND_OF_IGNITION)
    g.select(WAND_OF_IGNITION)
    g.expect(pending_power=power, pending_element=Element.ELEM_FIRE)
    assert g.state.pending_is_group_attack is True

    # 6. ＜オーラ＞で2倍になり、無属性に戻る
    g.select(AURA)
    g.expect(pending_power=power * 2, pending_element=Element.ELEM_NONE)
    assert g.state.pending_is_group_attack is True


@pytest.mark.parametrize(
    "item",
    ["weapons/ascension-bow", "sundries/guardian-pot", "armor/super-mirror"],
    ids=["昇天弓", "守護封印のつぼ", "スーパーミラー"],
)
def test_selling_transfers_exactly_the_master_price(board, item):
    """売却で動くお金が、カードマスタの価格ちょうどであることを検証します。

    【削除したフィールドについて】
    以前ここには test_staging_sell_price_zero_yen_item という
    「0円アイテム（昇天弓）を売却仮置きすると pending_sell_price が 0 になる」
    テストがありました。しかし昇天弓はマスタ上 price=10 で、0円アイテムでは
    ありません。調べたところ pending_sell_price には値が入る経路が一つも無く
    （計算処理は書かれているのに、売却フェイズのハンドラから呼ばれていなかった）、
    常に 0 でした。つまりどのカードを置いても通る空のテストでした。

    このフィールドは観測にも含まれておらず、visualizer は Python 側で価格を
    計算し直すフォールバックを持っていたため、削除しました。代わりにここでは
    「実際に動くお金がマスタの価格と一致する」という意味のある不変条件を検証します。
    """
    price = card_feature(item, "price")
    assert price > 0, "価格0のカードでは受け渡しを検証できない"
    seller_money, buyer_money = 0, 99

    g = board(
        p0=Side(hp=40, mp=50, money=seller_money, hand=["deals/sell", item]),
        p1=Side(hp=40, mp=50, money=buyer_money),
    )
    g.rng.deck_always(FILLER)

    g.select("deals/sell", item)
    g.target_opp()
    g.expect(phase=GamePhase.PHASE_SELL_SELECT_MIRROR, actor=1)

    g.confirm()  # 買い手が受諾

    g.expect(p0_money=seller_money + price, p1_money=buyer_money - price)
