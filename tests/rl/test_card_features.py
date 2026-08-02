"""カード属性テーブルの検証。

観測にはカードIDしか入っていないため、値段や攻撃力はこのテーブルからしか
ネットワークに届きません。ここが黙って壊れると、方策は「カードの意味を知らない」
状態に戻りますが、学習は普通に進んでしまい気付けません。
"""

import numpy as np
import pytest

from godfield_rl.card_features import (
    CARD_TYPES,
    ELEMENTS,
    NUMERIC_FIELDS,
    USAGE_TIMINGS,
    card_attr_dim,
    card_attribute_table,
    feature_names,
    thermometer,
)
from godfield_rl.cards import all_cards, card_id, feature
from godfield_rl.feature_config import NUM_CARD_TYPES


@pytest.fixture(scope="module")
def table() -> np.ndarray:
    return card_attribute_table()


def column(name: str) -> int:
    return feature_names().index(name)


def row_of(table: np.ndarray, name: str) -> np.ndarray:
    """カード名の行（テーブルは padding のぶん +1 ずれている）。"""
    return table[card_id(name) + 1]


# --- 形と規約 ---------------------------------------------------------------


def test_table_covers_every_card(table):
    assert table.shape == (NUM_CARD_TYPES + 1, card_attr_dim())
    assert table.dtype == np.float32


def test_row_zero_is_the_empty_slot(table):
    """行0は CARD_EMPTY 用。埋め込みの padding_idx=0 と同じ規約。"""
    assert not table[0].any(), "空スロットの行に値が入っています"


def test_every_real_card_has_some_attribute(table):
    """種別は全カードにあるので、実在するカードの行が全ゼロになることはない。"""
    for card in all_cards():
        assert table[card["id"] + 1].any(), f"{card['name']} の行が全ゼロです"


def test_feature_names_match_the_width(table):
    assert len(feature_names()) == table.shape[1]
    assert len(set(feature_names())) == len(feature_names()), "列名が重複しています"


# --- 温度計符号 -------------------------------------------------------------


def test_thermometer_marks_every_edge_at_or_below_the_value():
    assert thermometer(15, (1, 5, 10, 15, 20)) == [1.0, 1.0, 1.0, 1.0, 0.0]
    assert thermometer(0, (1, 5)) == [0.0, 0.0]


def test_thermometer_is_monotone_for_every_card(table):
    """閾値が大きくなるほど 1 が減る。ここが崩れると閾値の意味が壊れる。"""
    for field, _, edges in NUMERIC_FIELDS:
        cols = [column(f"{field}>={e}") for e in edges]
        block = table[:, cols]
        assert np.all(np.diff(block, axis=1) <= 0), f"{field} の温度計符号が単調ではありません"


def test_price_thresholds_reflect_the_master(table):
    """人手の戦略が使う「15円以上」がテーブルから読めること。"""
    expensive = [c for c in all_cards() if (c.get("price") or 0) >= 15]
    assert expensive, "15円以上のカードがカードマスタにありません"
    col = column("price>=15")
    for card in expensive:
        assert table[card["id"] + 1, col] == 1.0, f"{card['name']} が高額として立っていません"
    for card in all_cards():
        if (card.get("price") or 0) < 15:
            assert table[card["id"] + 1, col] == 0.0


# --- 欠損と0の区別 ----------------------------------------------------------


def test_missing_and_zero_are_distinguished(table):
    """「攻撃力0」と「攻撃力という概念が無い」は別物として表す。"""
    has_col = column("has_attack_power")
    for card in all_cards():
        expected = 1.0 if card.get("attack_power") is not None else 0.0
        assert table[card["id"] + 1, has_col] == expected, card["name"]

    zero_attack = [c for c in all_cards() if c.get("attack_power") == 0]
    if zero_attack:
        r = table[zero_attack[0]["id"] + 1]
        assert r[has_col] == 1.0
        assert r[column("attack_power>=1")] == 0.0


# --- 具体的なカードで意味を確認 ---------------------------------------------


def test_a_weapon_carries_its_attack_power(table):
    r = row_of(table, "パンチ")
    assert r[column("type=weapon")] == 1.0
    assert r[column("has_attack_power")] == 1.0
    power = feature(card_id("パンチ"), "attack_power")
    assert r[column("attack_power>=3")] == (1.0 if power >= 3 else 0.0)


def test_a_miracle_carries_its_element_and_mp_cost(table):
    r = row_of(table, "＜氷＞")
    assert r[column("type=miracle")] == 1.0
    assert r[column("has_element")] == 1.0
    assert r[column("element=水")] == 1.0
    assert r[column("has_mp_cost")] == 1.0


def test_trade_cards_are_marked_as_deals(table):
    for name in ("買う", "売る", "両替"):
        r = row_of(table, name)
        assert r[column("type=deal")] == 1.0, name
        assert r[column("timing=main_deal_phase")] == 1.0, name


def test_types_and_elements_cover_the_master():
    """カードマスタに未知の値が入ったら気付けること。"""
    assert {c["type"] for c in all_cards()} <= set(CARD_TYPES)
    assert {c["element"] for c in all_cards() if c.get("element")} <= set(ELEMENTS)
    timings = {t for c in all_cards() for t in (c.get("usage_timing") or [])}
    assert timings <= set(USAGE_TIMINGS)


def test_cards_with_different_prices_have_different_rows(table):
    """値段が違えば行も違う。テーブルが定数を返していないことの確認。"""
    cheap = row_of(table, "パンチ")
    pricey = row_of(table, "神の盾")
    assert not np.array_equal(cheap, pricey)
