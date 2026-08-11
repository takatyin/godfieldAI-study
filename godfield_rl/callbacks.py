import glob
import os
import random
import re
from collections import defaultdict

import numpy as np
from sb3_contrib import MaskablePPO
from stable_baselines3.common.callbacks import BaseCallback

from godfield_rl.opponents import FrozenOpponent, PoolOpponent


class WinRateCallback(BaseCallback):
    """
    Opponentに対する勝率・敗北率・引き分け率を記録し、TensorBoard/WandBに出力するコールバック。
    """

    def __init__(self, history_size: int = 1000, verbose: int = 0):
        super().__init__(verbose)
        self.history_size = history_size
        self.wins = 0
        self.losses = 0
        self.draws = 0
        self.episodes = 0

        # 1: Win, -1: Loss, 0: Draw
        self.recent_results = []

    def _on_step(self) -> bool:
        if "dones" in self.locals and "rewards" in self.locals:
            dones = self.locals["dones"]
            rewards = self.locals["rewards"]
            infos = self.locals.get("infos") or [{}] * len(dones)

            for i in range(len(dones)):
                if dones[i]:
                    self.episodes += 1
                    # 勝敗は必ず info の game_outcome を見る。報酬シェーピングを
                    # 入れると終端報酬がちょうど ±1 でなくなり、報酬の値で判定すると
                    # 全部「引き分け」に数えてしまう。
                    r = infos[i].get("game_outcome", rewards[i])
                    if r > 0:
                        self.wins += 1
                        self.recent_results.append(1)
                    elif r < 0:
                        self.losses += 1
                        self.recent_results.append(-1)
                    else:
                        self.draws += 1
                        self.recent_results.append(0)

                    if len(self.recent_results) > self.history_size:
                        self.recent_results.pop(0)
        return True

    def _on_rollout_end(self) -> None:
        if self.episodes > 0:
            win_rate_all = self.wins / self.episodes

            recent = np.array(self.recent_results)
            if len(recent) > 0:
                win_rate_recent = np.sum(recent == 1) / len(recent)
                loss_rate_recent = np.sum(recent == -1) / len(recent)
                draw_rate_recent = np.sum(recent == 0) / len(recent)
            else:
                win_rate_recent = 0.0
                loss_rate_recent = 0.0
                draw_rate_recent = 0.0

            self.logger.record("win_rate/recent_win", win_rate_recent)
            self.logger.record("win_rate/recent_loss", loss_rate_recent)
            self.logger.record("win_rate/recent_draw", draw_rate_recent)
            self.logger.record("win_rate/overall", win_rate_all)
            self.logger.record("win_rate/total_episodes", self.episodes)


def worker_id_of(path: str) -> int:
    """`worker_3_gen_12.zip` から 3 を取り出します。読めなければ -1。"""
    m = re.search(r"worker_?(\d+)", os.path.basename(path))
    return int(m.group(1)) if m else -1


def sample_across_workers(paths: list[str], k: int, rng: random.Random) -> list[str]:
    """ワーカーを均等に巡回しながら k 個選びます。

    一様に選ぶと、速いワーカーがプールを占拠します。保存はステップ基準なので、
    同じ実時間でも速いワーカーほど多くのモデルを残すためです。実測では
    d128 の worker 0 が 53 個中 30 個（57%）を占め、まだ 5M の worker 3 が
    50M まで育った worker 0 とばかり当たって勝率 15% に沈んでいました。
    ほぼ全敗では行動の良し悪しが差として出ず、学習信号になりません。

    ワーカー単位で均等にすると、モデルの大きさや速度が違っても対戦相手の
    構成が変わらなくなります。
    """
    by_worker: dict[int, list[str]] = defaultdict(list)
    for path in paths:
        by_worker[worker_id_of(path)].append(path)
    for models in by_worker.values():
        rng.shuffle(models)

    workers = sorted(by_worker)
    rng.shuffle(workers)

    picked: list[str] = []
    while len(picked) < k and any(by_worker.values()):
        for worker in workers:
            if not by_worker[worker]:
                continue
            picked.append(by_worker[worker].pop())
            if len(picked) == k:
                break
    return picked


class SelfPlayCallback(BaseCallback):
    """
    一定のステップ数ごとに現在のモデルを共有ディレクトリに保存し、
    同時に共有ディレクトリから他のモデルをランダムに読み込んで対戦プールを更新するコールバック（League Training対応）。
    """

    def __init__(
        self,
        pool: PoolOpponent,
        save_freq: int,
        save_path: str,
        max_pool_size: int = 5,
        worker_id: int = 0,
        seed: int = 0,
        total_timesteps: int = 0,
        verbose: int = 0,
    ):
        super().__init__(verbose)
        self.pool = pool
        self.save_freq = save_freq
        self.save_path = save_path
        self.max_pool_size = max_pool_size
        self.worker_id = worker_id
        # 錨の配分を進み具合で動かすために使う。SB3 の内部属性
        # （_total_timesteps / _current_progress_remaining）に頼ると
        # バージョンで壊れるので、設定から受け取る。
        self.total_timesteps = total_timesteps
        self.generation = 0
        # プールの抽選はワーカーごとに独立させつつ、再現できるようにする。
        # 以前は random モジュールのグローバル状態を使っていたため、実行のたびに
        # 違う結果になり（＝再現不能）、しかも「ワーカーが分岐する唯一の要因」が
        # ここだった（seed が全ワーカー共通だったため）。
        self._rng = random.Random(seed * 1000 + worker_id)

        os.makedirs(self.save_path, exist_ok=True)

    def _on_training_start(self) -> None:
        """既にあるプールのモデルが読めるかを、学習を始める前に確かめます。

        プールの同期は save_freq ごと（既定で 1M ステップごと）なので、
        ここで確認しないと「観測を変えたのに古いプールを指していた」ことに
        気づくのが10分後になります。実際にそれが起きました。
        起動直後に落ちれば、設定を直してすぐ入れ直せます。
        """
        existing = sorted(glob.glob(os.path.join(self.save_path, "*.zip")))
        if not existing:
            return  # 新しいプール。他のワーカーが書き始めるのを待てばよい

        try:
            MaskablePPO.load(existing[0], device=self.model.device)
        except Exception as exc:
            raise RuntimeError(
                f"プール {self.save_path} の既存モデルが読み込めません"
                f"（{len(existing)} 件中の {os.path.basename(existing[0])} で確認）。\n"
                f"  観測のレイアウトを変えると、それ以前のモデルは読めません。\n"
                f"  --pool-dir に新しいディレクトリを指定するか、古いモデルを消してください。\n"
                f"  元のエラー: {str(exc).splitlines()[0]}"
            ) from exc

    def _on_step(self) -> bool:
        # 錨の配分は学習の進み具合で決まるので、毎ステップ伝えておく。
        if self.total_timesteps > 0:
            self.pool.progress = min(1.0, self.num_timesteps / self.total_timesteps)

        if self.n_calls % self.save_freq == 0:
            self.generation += 1

            # Atomic save: SB3は拡張子がないと .zip を付けるため、.tmp を付けて一時保存し、その後リネームする
            temp_path_base = os.path.join(self.save_path, f"worker_{self.worker_id}_gen_{self.generation}.tmp")
            final_path = os.path.join(self.save_path, f"worker_{self.worker_id}_gen_{self.generation}.zip")

            self.model.save(temp_path_base)

            # SB3は引数に .zip を付けて保存する仕様なのでリネーム元は .tmp.zip になる
            actual_temp_path = temp_path_base + ".zip"
            if os.path.exists(actual_temp_path):
                os.replace(actual_temp_path, final_path)
            else:
                # 念のためそのままのファイル名もチェック
                if os.path.exists(temp_path_base):
                    os.replace(temp_path_base, final_path)

            # 同期処理: 共有ディレクトリから .zip ファイルを全て取得
            all_models = glob.glob(os.path.join(self.save_path, "*.zip"))

            # ワーカーを均等に巡回して選ぶ（速いワーカーの占拠を防ぐ）
            selected_models = sample_across_workers(all_models, min(len(all_models), self.max_pool_size), self._rng)
            sample_size = len(selected_models)

            # 抽出したモデルをロードして分身のプールを作る。
            # 錨（人手の戦略など）は PoolOpponent.anchors 側にあるので触らない。
            new_snapshots = []
            failures = []
            for m_path in selected_models:
                try:
                    frozen_model = MaskablePPO.load(m_path, device=self.model.device)
                    new_snapshots.append(FrozenOpponent(frozen_model))
                except Exception as e:
                    failures.append((m_path, e))

            # 読めないモデルが混ざっているのは設定の誤り。黙って捨てると、
            # 「自己対戦のつもりが初期相手としか戦っていない」状態で何十時間も
            # 回ることになる。保存は .tmp からのリネームで原子的に行っているので、
            # 書きかけを掴むことは無い＝失敗したら本当におかしい。
            if failures:
                head = "\n".join(f"    {os.path.basename(p)}: {e}" for p, e in failures[:2])
                raise RuntimeError(
                    f"プール {self.save_path} の {len(failures)}/{len(selected_models)} 件が"
                    f"読み込めませんでした。観測のレイアウトを変えた場合、それ以前の"
                    f"モデルは読めません。新しいプールのディレクトリを指定するか、"
                    f"古いモデルを消してください。\n{head}"
                )

            # 分身だけを入れ替える
            self.pool.snapshots = new_snapshots

            if self.verbose > 0:
                print(
                    f"[{self.num_timesteps} steps] Worker {self.worker_id} synced League Pool. "
                    f"錨 {len(self.pool.anchors)} 体 (当たる割合 {self.pool.anchor_ratio:.0%}, "
                    f"配分 {self.pool.describe_anchors()}) "
                    f"/ 分身 {len(self.pool.snapshots)} 体 (loaded {sample_size} models)"
                )

        return True
