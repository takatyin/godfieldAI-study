"""自己対戦プールで、固定の相手と当たる割合が指定どおりになることの検証。

以前は「人手の戦略1体 + 自分の過去5体」を一様に選んでいたため、外部の相手と
当たるのは約17%でした。自分の過去は自分と同じ弱点を持つので、その弱点は
一度も罰されません。ここが黙って元に戻ると、学習は普通に進むのに
「学習相手には強いが、見たことのない相手には勝てない」方策に戻ります。
"""

import numpy as np
import pytest

from godfield_rl.opponents import PoolOpponent


class Tag:
    """自分が誰かを返すだけの相手。どちらが選ばれたかを数えるために使う。"""

    def __init__(self, name: str):
        self.name = name
        self.calls = 0

    def act(self, observations, action_masks):
        self.calls += 1
        return np.zeros(len(observations), dtype=np.int32)


def counts(pool: PoolOpponent, n: int) -> dict[str, int]:
    tally: dict[str, int] = {}
    for _ in range(n):
        name = pool.select().name
        tally[name] = tally.get(name, 0) + 1
    return tally


@pytest.mark.parametrize("ratio", [0.0, 0.25, 0.5, 0.9])
def test_anchor_ratio_is_respected(ratio):
    anchor = Tag("錨")
    pool = PoolOpponent(
        anchors=[anchor],
        snapshots=[Tag("分身1"), Tag("分身2"), Tag("分身3")],
        seed=0,
        anchor_ratio=ratio,
    )
    n = 6000
    tally = counts(pool, n)
    got = tally.get("錨", 0) / n
    assert abs(got - ratio) < 0.03, f"錨と当たる割合が {got:.1%}（指定は {ratio:.0%}）"


def test_anchor_is_used_while_no_snapshot_exists():
    """学習の最初はプールが空。そのときは錨だけが相手になる。"""
    pool = PoolOpponent(anchors=[Tag("錨")], seed=0, anchor_ratio=0.1)
    assert {pool.select().name for _ in range(200)} == {"錨"}


def test_snapshots_are_used_when_there_is_no_anchor():
    pool = PoolOpponent(snapshots=[Tag("分身")], seed=0, anchor_ratio=0.9)
    assert {pool.select().name for _ in range(200)} == {"分身"}


def test_an_empty_pool_raises():
    with pytest.raises(RuntimeError, match="空"):
        PoolOpponent(seed=0).select()


def test_ratio_outside_zero_to_one_is_rejected():
    with pytest.raises(ValueError, match="anchor_ratio"):
        PoolOpponent(anchors=[Tag("錨")], anchor_ratio=1.5)


def test_opponents_lists_both_kinds():
    pool = PoolOpponent(anchors=[Tag("錨")], snapshots=[Tag("分身")], seed=0)
    assert [o.name for o in pool.opponents] == ["錨", "分身"]


def test_replacing_snapshots_keeps_the_anchor():
    """SelfPlayCallback は分身だけを入れ替える。錨を巻き込むと外部の相手が消える。"""
    anchor = Tag("錨")
    pool = PoolOpponent(anchors=[anchor], snapshots=[Tag("古い分身")], seed=0)
    pool.snapshots = [Tag("新しい分身")]
    assert pool.anchors == [anchor]
    assert [o.name for o in pool.opponents] == ["錨", "新しい分身"]


# ============================================================================
# 錨の梯子（弱い相手から強い相手へ）
#
# 初期化直後のネットの勝率は 対 random 49.4% / 対 heuristic 26.0% /
# 対 strategic 3.3%。最強の相手だけで始めると勝敗がほぼ定数になり、
# 行動の良し悪しが差として出ない。
# ============================================================================


def ladder(progress: float, n: int = 2, end: float = 0.3) -> PoolOpponent:
    pool = PoolOpponent(
        anchors=[Tag(f"錨{i}") for i in range(n)], seed=0, curriculum_end=end
    )
    pool.progress = progress
    return pool


def test_training_starts_against_the_weakest_anchor():
    weights = ladder(progress=0.0).anchor_weights()
    assert weights[0] == 1.0
    assert weights[-1] == 0.0


def test_the_strongest_anchor_takes_over_completely_at_the_end():
    """「比率を1にしていく」— curriculum_end 以降は最強の錨だけになる。"""
    for progress in (0.3, 0.5, 1.0):
        weights = ladder(progress=progress, end=0.3).anchor_weights()
        assert weights[-1] == 1.0, f"進み具合 {progress} で最強の錨だけになっていません"
        assert weights[:-1].sum() == 0.0


def test_the_mix_moves_gradually():
    halfway = ladder(progress=0.15, end=0.3).anchor_weights()
    assert halfway == pytest.approx([0.5, 0.5])

    quarter = ladder(progress=0.075, end=0.3).anchor_weights()
    assert quarter == pytest.approx([0.75, 0.25])


def test_weights_always_form_a_distribution():
    for n in (1, 2, 3, 4):
        for progress in (0.0, 0.1, 0.2, 0.29, 0.3, 0.7, 1.0):
            weights = ladder(progress, n=n).anchor_weights()
            assert weights.sum() == pytest.approx(1.0)
            assert (weights >= 0).all()


def test_three_anchors_climb_one_rung_at_a_time():
    """3体なら、中間の錨を経由して最強へ移る（隣り合う2体にだけ質量が乗る）。"""
    assert ladder(0.0, n=3).anchor_weights() == pytest.approx([1.0, 0.0, 0.0])
    assert ladder(0.15, n=3).anchor_weights() == pytest.approx([0.0, 1.0, 0.0])
    assert ladder(0.3, n=3).anchor_weights() == pytest.approx([0.0, 0.0, 1.0])


def test_curriculum_can_be_switched_off():
    """0 にすると最初から最強の錨だけを使う。"""
    assert ladder(0.0, end=0.0).anchor_weights() == pytest.approx([0.0, 1.0])


def test_selection_follows_the_weights():
    pool = ladder(progress=0.15, end=0.3)
    tally = counts(pool, 4000)
    assert abs(tally.get("錨0", 0) / 4000 - 0.5) < 0.03


def test_the_curriculum_only_reweights_the_anchors():
    """錨と分身の比は anchor_ratio のまま。梯子は錨の内側の配分だけを変える。"""
    pool = PoolOpponent(
        anchors=[Tag("弱"), Tag("強")],
        snapshots=[Tag("分身")],
        seed=0,
        anchor_ratio=0.5,
        curriculum_end=0.3,
    )
    pool.progress = 1.0
    tally = counts(pool, 6000)
    assert abs(tally.get("分身", 0) / 6000 - 0.5) < 0.03
    assert tally.get("弱", 0) == 0, "移行後も弱い錨が選ばれています"


def test_curriculum_end_outside_zero_to_one_is_rejected():
    with pytest.raises(ValueError, match="curriculum_end"):
        PoolOpponent(anchors=[Tag("錨")], curriculum_end=1.5)
