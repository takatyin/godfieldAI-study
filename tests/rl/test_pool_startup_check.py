"""読めないプールを指したとき、学習を始める前に落ちること。

プールの同期は save_freq ごと（既定で1Mステップごと）なので、そこで初めて
気づくと約10分走ってからの失敗になる。実際に「観測を変えたのに古いプールを
指していた」がその形で起きた。起動時に落ちれば、直してすぐ入れ直せる。
"""

import os

import pytest

from godfield_rl.callbacks import SelfPlayCallback
from godfield_rl.opponents import PoolOpponent


class FakeModel:
    """コールバックが触るのは device だけ。"""

    device = "cpu"


def make_callback(pool_dir: str) -> SelfPlayCallback:
    callback = SelfPlayCallback(
        pool=PoolOpponent([]), save_freq=1000, save_path=pool_dir, worker_id=0
    )
    callback.model = FakeModel()
    return callback


def test_unreadable_pool_fails_before_training_starts(tmp_path):
    pool = tmp_path / "old_pool"
    pool.mkdir()
    (pool / "worker_1_gen_1.zip").write_bytes(b"not a real model")

    with pytest.raises(RuntimeError) as excinfo:
        make_callback(str(pool))._on_training_start()

    message = str(excinfo.value)
    assert "読み込めません" in message
    assert "worker_1_gen_1.zip" in message, "どのファイルで失敗したか分からない"
    assert "--pool-dir" in message, "直し方が示されていない"


def test_empty_pool_is_fine(tmp_path):
    """新しいプールは空。他のワーカーが書き始めるのを待てばよい。"""
    make_callback(str(tmp_path / "new_pool"))._on_training_start()


def test_pool_directory_is_created_if_missing(tmp_path):
    pool = tmp_path / "does_not_exist_yet"
    make_callback(str(pool))
    assert os.path.isdir(pool)


def test_non_zip_files_are_ignored(tmp_path):
    """ログやテンポラリが混ざっていても、モデルでなければ見に行かない。"""
    pool = tmp_path / "pool"
    pool.mkdir()
    (pool / "notes.txt").write_text("メモ", encoding="utf-8")
    (pool / "worker_0_gen_1.tmp").write_bytes(b"partially written")

    make_callback(str(pool))._on_training_start()
