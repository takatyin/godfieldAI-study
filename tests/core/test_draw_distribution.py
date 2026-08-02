"""山札の抽選分布が drop_rate どおりであることの検証。

draw_card は std::discrete_distribution から「重みの分だけカードIDを並べた
フラットテーブル」に置き換えられています（実測 42.33 ns/draw -> 5.12 ns/draw）。
確率分布は数学的に同一のはずなので、それを実際に確かめます。
"""

from collections import Counter

import pytest

import godfield_core
from tests.core.dsl import Game, Side, all_cards, card_id, card_name


def _drop_rates() -> dict[int, int]:
    return {c["id"]: c.get("drop_rate", 0) or 0 for c in all_cards()}


def test_cards_with_zero_drop_rate_are_never_drawn():
    """drop_rate が 0 のカード（悪魔・超常現象・守護神の行動カード等）は引かれないことを検証します。"""
    rates = _drop_rates()
    zero_ids = {cid for cid, rate in rates.items() if rate == 0}
    assert zero_ids, "drop_rate=0 のカードが存在するはずです"

    g = Game(p0=Side(hp=99, hand=[]), p1=Side(hp=99))
    g.state.seed_rng(12345)

    drawn = Counter()
    for _ in range(20000):
        drawn[godfield_core.draw_card(g.state)] += 1

    leaked = zero_ids & set(drawn)
    assert not leaked, (
        "drop_rate=0 のカードが抽選されました: "
        + ", ".join(card_name(cid) for cid in sorted(leaked))
    )


def test_draw_frequencies_match_the_drop_rate_weights():
    """抽選頻度が drop_rate の重み比と一致することを検証します。

    重みの総和に対する各カードの割合が理論値どおりか、十分な試行数で確認します。
    フラットテーブル化で分布がズレていればここで検出できます。
    """
    rates = _drop_rates()
    total_weight = sum(rates.values())
    assert total_weight > 0

    g = Game(p0=Side(hp=99, hand=[]), p1=Side(hp=99))
    g.state.seed_rng(20260727)

    trials = 200000
    drawn = Counter()
    for _ in range(trials):
        drawn[godfield_core.draw_card(g.state)] += 1

    # 最も重みの大きいカード群だけを見る（試行数に対して十分な期待度数があるもの）
    heavy = [cid for cid, rate in rates.items() if rate >= 6]
    assert heavy, "重みの大きいカードが存在するはずです"

    for cid in heavy:
        expected = trials * rates[cid] / total_weight
        actual = drawn[cid]
        # 二項分布の標準偏差の約5倍を許容幅にする（偶然の失敗を実質的に排除しつつ、
        # 分布が壊れていれば必ず外れる幅）
        sd = (trials * (rates[cid] / total_weight) * (1 - rates[cid] / total_weight)) ** 0.5
        assert abs(actual - expected) < 5 * sd, (
            f"{card_name(cid)} の抽選頻度が理論値から外れています: "
            f"期待 {expected:.1f} / 実際 {actual} (許容 ±{5 * sd:.1f})"
        )


def test_scripted_draw_overrides_the_table():
    """テストからの指示が抽選テーブルより優先されることを検証します。"""
    g = Game(p0=Side(hp=99, hand=[]), p1=Side(hp=99))
    g.rng.next_draws("weapons/dangerous-pestle")
    g.pray()
    assert card_id("weapons/dangerous-pestle") in [
        g.state.get_true_hand(0, i) for i in range(18)
    ]


def test_draw_table_size_equals_the_total_weight():
    """抽選テーブルの要素数が drop_rate の総和と一致することを検証します。

    ここがズレていると、特定のカードだけ確率が変わる形で静かに壊れます。
    """
    rates = _drop_rates()
    assert godfield_core.get_draw_table_size() == sum(rates.values())


def test_scripted_draw_rejects_unknown_card_id():
    """存在しないカードIDを指示した場合に例外になることを検証します。"""
    g = Game(p0=Side(hp=99, hand=[]), p1=Side(hp=99))
    g.rng.force(godfield_core.RollKind.DECK_DRAW, 99999)
    with pytest.raises(RuntimeError, match="存在しないカードID"):
        g.pray()
    godfield_core.rng_clear_script()
