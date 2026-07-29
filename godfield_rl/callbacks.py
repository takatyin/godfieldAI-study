import os
import numpy as np
from stable_baselines3.common.callbacks import BaseCallback
from sb3_contrib import MaskablePPO

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
            
            for i in range(len(dones)):
                if dones[i]:
                    self.episodes += 1
                    r = rewards[i]
                    if r == 1.0:
                        self.wins += 1
                        self.recent_results.append(1)
                    elif r == -1.0:
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


class SelfPlayCallback(BaseCallback):
    """
    一定のステップ数ごとに現在のモデルを保存し、対戦相手プールに追加するコールバック。
    """
    def __init__(self, pool: PoolOpponent, save_freq: int, save_path: str, max_pool_size: int = 5, verbose: int = 0):
        super().__init__(verbose)
        self.pool = pool
        self.save_freq = save_freq
        self.save_path = save_path
        self.max_pool_size = max_pool_size
        self.generation = 0
        
        os.makedirs(self.save_path, exist_ok=True)

    def _on_step(self) -> bool:
        if self.n_calls % self.save_freq == 0:
            self.generation += 1
            model_path = os.path.join(self.save_path, f"selfplay_gen_{self.generation}.zip")
            
            # 現在のモデルを保存
            self.model.save(model_path)
            
            # 保存したモデルを読み込んでFrozenOpponentを作成 (推論もGPUで行う)
            frozen_model = MaskablePPO.load(model_path, device=self.model.device)
            frozen_opponent = FrozenOpponent(frozen_model)
            
            # プールに追加
            self.pool.add_opponent(frozen_opponent)
            
            # プールサイズ制限の適用 (FrozenOpponent のみカウントし、古いものから削除)
            frozen_count = sum(1 for opp in self.pool.opponents if isinstance(opp, FrozenOpponent))
            if frozen_count > self.max_pool_size:
                for idx, opp in enumerate(self.pool.opponents):
                    if isinstance(opp, FrozenOpponent):
                        self.pool.opponents.pop(idx)
                        break
                        
            if self.verbose > 0:
                print(f"[{self.num_timesteps} steps] Self-play generation {self.generation} added to pool. Current pool size: {len(self.pool.opponents)}")
                
        return True
