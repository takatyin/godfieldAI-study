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
