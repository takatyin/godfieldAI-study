"""錨の梯子が設定から実際のプールまで繋がっていることの検証。

`PoolOpponent.anchor_weights()` が正しくても、進み具合が誰も更新しなければ
配分は永久に初期状態のままです。しかも例外は出ず、「弱い相手とだけ延々戦う」
形で静かに失敗します。
"""

import pytest

from godfield_rl.config import TrainingConfig
from godfield_rl.opponents import HeuristicOpponent, PoolOpponent
from godfield_rl.strategy import StrategicOpponent
from godfield_rl.training import anchor_kinds, build_opponent


def config(**kwargs) -> TrainingConfig:
    base = dict(self_play=True, total_timesteps=1_000_000, num_envs=8, n_steps=8,
                batch_size=8)
    base.update(kwargs)
    return TrainingConfig(**base)


# --- 設定の解釈 -------------------------------------------------------------


def test_default_ladder_goes_from_heuristic_to_strategic():
    assert anchor_kinds(config()) == ["heuristic", "strategic"]


def test_the_ladder_must_end_at_the_evaluation_opponent():
    """eval 環境は --opponent を使うので、梯子の最後がずれると評価が食い違う。"""
    with pytest.raises(ValueError, match="--opponent と同じ"):
        anchor_kinds(config(anchor_kinds="strategic,heuristic"))


def test_unknown_anchor_kind_is_rejected():
    with pytest.raises(ValueError, match="未知の方策"):
        anchor_kinds(config(anchor_kinds="heuristic,minmax"))


def test_a_single_kind_is_allowed():
    assert anchor_kinds(config(anchor_kinds="strategic")) == ["strategic"]


def test_curriculum_end_outside_range_is_rejected():
    with pytest.raises(ValueError, match="anchor_curriculum_end"):
        config(anchor_curriculum_end=2.0)


# --- 組み立て ---------------------------------------------------------------


def test_build_opponent_orders_the_anchors_weakest_first():
    pool = build_opponent(config(), device="cpu")

    assert isinstance(pool, PoolOpponent)
    assert isinstance(pool.anchors[0], HeuristicOpponent)
    assert isinstance(pool.anchors[-1], StrategicOpponent)
    assert pool.curriculum_end == config().anchor_curriculum_end


def test_training_starts_on_the_weak_anchor_and_ends_on_the_strong_one():
    pool = build_opponent(config(anchor_curriculum_end=0.3), device="cpu")

    pool.progress = 0.0
    assert isinstance(pool.select(), HeuristicOpponent)

    pool.progress = 0.5
    assert isinstance(pool.select(), StrategicOpponent)


# --- 進み具合を誰が更新するか -----------------------------------------------


def advance(pool: PoolOpponent, timesteps: int, total: int, tmp_path) -> None:
    """保存には入らずに progress の更新だけを踏ませる。

    `n_calls` を 1 にしておくのは、0 だと `n_calls % save_freq == 0` が成立して
    モデルの保存経路に入ってしまうため（このテストに model は無い）。
    """
    from godfield_rl.callbacks import SelfPlayCallback

    callback = SelfPlayCallback(
        pool=pool, save_freq=10**9, save_path=str(tmp_path), total_timesteps=total,
    )
    callback.n_calls = 1
    callback.num_timesteps = timesteps
    callback._on_step()


def test_the_callback_advances_the_curriculum(tmp_path):
    """SelfPlayCallback が毎ステップ progress を進めること。"""
    pool = build_opponent(config(), device="cpu")
    advance(pool, timesteps=300, total=1000, tmp_path=tmp_path)

    assert pool.progress == pytest.approx(0.3)


def test_progress_is_clamped_to_one(tmp_path):
    pool = build_opponent(config(), device="cpu")
    advance(pool, timesteps=5000, total=1000, tmp_path=tmp_path)

    assert pool.progress == 1.0


def test_the_ladder_actually_switches_over_during_a_run(tmp_path):
    """設定 → コールバック → 選ばれる相手、までが繋がっていること。"""
    cfg = config(total_timesteps=1000, anchor_curriculum_end=0.3)
    pool = build_opponent(cfg, device="cpu")

    advance(pool, timesteps=0, total=cfg.total_timesteps, tmp_path=tmp_path)
    assert isinstance(pool.select(), HeuristicOpponent)

    advance(pool, timesteps=600, total=cfg.total_timesteps, tmp_path=tmp_path)
    assert isinstance(pool.select(), StrategicOpponent)
