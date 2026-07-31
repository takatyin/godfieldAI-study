"""リーグのプール抽選が、速いワーカーに占拠されないこと。

保存はステップ基準なので、同じ実時間でも速いワーカーほど多くのモデルを残します。
一様に選ぶと対戦相手がその1体に偏り、遅いワーカーは自分よりはるかに強い相手と
ばかり当たってほぼ全敗する（＝行動の良し悪しが差として出ず学習信号にならない）。
"""

import random
from collections import Counter

import pytest

from godfield_rl.callbacks import sample_across_workers, worker_id_of


def pool(counts: dict[int, int]) -> list[str]:
    """{ワーカー番号: 個数} からプールのファイル名を作ります。"""
    return [f"worker_{w}_gen_{g}.zip" for w, n in counts.items() for g in range(n)]


# 前回の実行で実際にできた偏り
LOPSIDED = {0: 30, 1: 9, 2: 9, 3: 5}


def test_worker_id_is_parsed_from_filename():
    assert worker_id_of("/tmp/pool/worker_3_gen_12.zip") == 3
    assert worker_id_of("worker_0_gen_1.zip") == 0


def test_unparseable_names_are_grouped_but_not_crashing():
    picked = sample_across_workers(["stray.zip", "worker_0_gen_1.zip"], 2, random.Random(0))
    assert sorted(picked) == ["stray.zip", "worker_0_gen_1.zip"]


def test_dominant_worker_does_not_take_over_the_sample():
    """30/53 を占めるワーカーがいても、抽選は均等に近づく。"""
    rng = random.Random(0)
    counts = Counter()
    for _ in range(400):
        for path in sample_across_workers(pool(LOPSIDED), 4, rng):
            counts[worker_id_of(path)] += 1

    total = sum(counts.values())
    for worker in LOPSIDED:
        share = counts[worker] / total
        assert 0.2 < share < 0.3, f"worker {worker} の割合が {share:.1%} で均等から外れています"


def test_uniform_sampling_would_have_been_lopsided():
    """比較対象。以前の実装（一様抽選）なら偏る、ということの固定。"""
    rng = random.Random(0)
    counts = Counter()
    paths = pool(LOPSIDED)
    for _ in range(400):
        for path in rng.sample(paths, 4):
            counts[worker_id_of(path)] += 1
    assert counts[0] / sum(counts.values()) > 0.5


@pytest.mark.parametrize("k", [1, 3, 4, 5, 8, 53])
def test_returns_requested_count_without_duplicates(k):
    picked = sample_across_workers(pool(LOPSIDED), k, random.Random(1))
    assert len(picked) == min(k, sum(LOPSIDED.values()))
    assert len(set(picked)) == len(picked)


def test_requesting_more_than_available_returns_everything():
    paths = pool({0: 2, 1: 1})
    assert sorted(sample_across_workers(paths, 99, random.Random(2))) == sorted(paths)


def test_empty_pool_is_not_an_error():
    assert sample_across_workers([], 5, random.Random(3)) == []


def test_single_worker_pool_still_works():
    paths = pool({2: 4})
    picked = sample_across_workers(paths, 3, random.Random(4))
    assert len(picked) == 3
    assert {worker_id_of(p) for p in picked} == {2}


def test_sampling_is_reproducible_for_a_given_seed():
    paths = pool(LOPSIDED)
    first = sample_across_workers(paths, 4, random.Random(7))
    second = sample_across_workers(paths, 4, random.Random(7))
    assert first == second
