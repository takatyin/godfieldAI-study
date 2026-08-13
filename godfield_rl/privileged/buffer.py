from typing import NamedTuple

import godfield_core
import numpy as np
import torch as th
from sb3_contrib.common.maskable.buffers import MaskableRolloutBuffer


class PrivilegedRolloutBufferSamples(NamedTuple):
    """PPO の1 minibatch分のデータ。

    通常の MaskableRolloutBufferSamples に、
    critic 専用の privileged 情報として opponent_true_hands を追加する。
    """

    observations: th.Tensor
    actions: th.Tensor
    old_values: th.Tensor
    old_log_prob: th.Tensor
    advantages: th.Tensor
    returns: th.Tensor

    # Actor には渡さず、Critic V(o, h) の計算だけに使用する。
    opponent_true_hands: th.Tensor

    # MaskablePPO が通常から使用する合法手マスク。
    action_masks: th.Tensor


class PrivilegedRolloutBuffer(MaskableRolloutBuffer):
    """相手の真の手札を追加で保存する MaskableRolloutBuffer。"""

    def reset(self) -> None:
        # observations / actions / values / action_masks 等の
        # 通常の rollout buffer を親クラス側で初期化する。
        super().reset()

        # rollout 全体では
        #   (T, N, H)
        # T: rollout length
        # N: parallel environments
        # H: MAX_HAND_SIZE
        #
        # 各時刻・各環境について相手の真の手札を保存する。
        self.opponent_true_hands = np.zeros(
            (
                self.buffer_size,
                self.n_envs,
                godfield_core.MAX_HAND_SIZE,
            ),
            dtype=np.int32,
        )

    def add(
        self,
        obs,
        action,
        reward,
        episode_start,
        value,
        log_prob,
        opponent_true_hands,
        action_masks=None,
    ) -> None:
        # super().add() の中で self.pos が次の時刻へ進む。
        # そのため、現在時刻 t の hidden hand は
        # super().add() より先に同じ self.pos へ保存する必要がある。
        self.opponent_true_hands[self.pos] = opponent_true_hands

        # 通常の PPO データと action mask は親クラスに保存を任せる。
        super().add(
            obs,
            action,
            reward,
            episode_start,
            value,
            log_prob,
            action_masks=action_masks,
        )

    def get(self, batch_size=None):
        # PPO の学習は rollout が全て埋まってから行う。
        assert self.full, ""

        # T*N 個の rollout sample をランダムな順番に並べ替える。
        indices = np.random.permutation(
            self.buffer_size * self.n_envs
        )

        if not self.generator_ready:
            # 保存時の shape は基本的に (T, N, ...)。
            # PPO の minibatch 学習用に (T*N, ...) へ変換する。
            #
            # opponent_true_hands も通常データと同じ変換を行うことで、
            # observation/action と同じ sample index を維持する。
            tensor_names = [
                "observations",
                "actions",
                "values",
                "log_probs",
                "advantages",
                "returns",
                "action_masks",
                "opponent_true_hands",
            ]

            for tensor in tensor_names:
                self.__dict__[tensor] = self.swap_and_flatten(
                    self.__dict__[tensor]
                )

            # 同じ rollout に対して何度も flatten しないためのフラグ。
            self.generator_ready = True

        if batch_size is None:
            # batch_size 未指定なら rollout 全体を1 batchとして返す。
            batch_size = self.buffer_size * self.n_envs

        start_idx = 0

        while start_idx < self.buffer_size * self.n_envs:
            yield self._get_samples(
                indices[start_idx : start_idx + batch_size]
            )
            start_idx += batch_size

    def _get_samples(self, batch_inds):
        # 全データに同じ batch_inds を適用することで、
        #
        #   observation_t
        #   action_t
        #   value_t
        #   hidden_hand_t
        #   action_mask_t
        #
        # が同じ時刻・同じ環境のサンプルとして対応する。
        data = (
            self.observations[batch_inds],
            self.actions[batch_inds],
            self.values[batch_inds].flatten(),
            self.log_probs[batch_inds].flatten(),
            self.advantages[batch_inds].flatten(),
            self.returns[batch_inds].flatten(),

            # flatten 後は (T*N, H) なので、
            # minibatch では (B, H) になる。
            self.opponent_true_hands[batch_inds],

            # MaskablePPO が期待する
            # (B, mask_dims) に整形する。
            self.action_masks[batch_inds].reshape(
                -1,
                self.mask_dims,
            ),
        )

        # NumPy -> torch.Tensor に変換し、
        # 名前付き tuple として PPO の train() 側へ返す。
        return PrivilegedRolloutBufferSamples(
            *tuple(map(self.to_torch, data))
        )
    