import numpy as np
import torch as th
from gymnasium import spaces
from sb3_contrib import MaskablePPO
from sb3_contrib.common.maskable.buffers import MaskableRolloutBuffer
from sb3_contrib.common.maskable.utils import (
    get_action_masks,
    is_masking_supported,
)
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.utils import (
    explained_variance,
    obs_as_tensor,
)
from stable_baselines3.common.vec_env import VecEnv
from torch.nn import functional as F

from godfield_rl.privileged.buffer import PrivilegedRolloutBuffer


class PrivilegedMaskablePPO(MaskablePPO):
    def __init__(self, *args, **kwargs):
        # 通常の MaskableRolloutBuffer の代わりに、
        # opponent_true_hands を保存できる buffer を使う。
        kwargs["rollout_buffer_class"] = PrivilegedRolloutBuffer

        super().__init__(*args, **kwargs)

    def collect_rollouts(
        self,
        env: VecEnv,
        callback: BaseCallback,
        rollout_buffer: MaskableRolloutBuffer,
        n_rollout_steps: int,
        use_masking: bool = True,
    ) -> bool:
        """
        MaskablePPO の rollout 収集に privileged critic 用の
        opponent_true_hands を追加する。
        """

        assert self._last_obs is not None, "No previous observation was provided"

        self.policy.set_training_mode(False)

        n_steps = 0
        action_masks = None

        rollout_buffer.reset()

        if use_masking and not is_masking_supported(env):
            raise ValueError("Environment does not support action masking.")

        callback.on_rollout_start()

        while n_steps < n_rollout_steps:
            with th.no_grad():
                # o_t
                obs_tensor = obs_as_tensor(
                    self._last_obs,
                    self.device,
                )

                # -------------------------------------------------
                # Privileged critic:
                # env.step() 前に h_t を取得する。
                # -------------------------------------------------
                opponent_true_hands = env.get_opponent_true_hands()

                hand_tensor = th.as_tensor(
                    opponent_true_hands,
                    device=self.device,
                )

                if use_masking:
                    action_masks = get_action_masks(env)

                # Actor:  o_t
                # Critic: o_t + h_t
                actions, values, log_probs = self.policy(
                    obs_tensor,
                    hand_tensor,
                    action_masks=action_masks,
                )

            actions = actions.cpu().numpy()

            # Discrete action space なので必要なら clip 等は親実装に合わせる。
            clipped_actions = actions

            if isinstance(self.action_space, spaces.Box):
                if self.policy.squash_output:
                    clipped_actions = self.policy.unscale_action(clipped_actions)
                else:
                    clipped_actions = np.clip(
                        actions,
                        self.action_space.low,
                        self.action_space.high,
                    )

            # a_t を環境へ適用して o_{t+1} へ
            new_obs, rewards, dones, infos = env.step(clipped_actions)

            self.num_timesteps += env.num_envs

            callback.update_locals(locals())

            if not callback.on_step():
                return False

            self._update_info_buffer(infos, dones)

            n_steps += 1

            # Discrete の場合、buffer 側が期待する shape に合わせる
            if isinstance(self.action_space, spaces.Discrete):
                actions = actions.reshape(-1, 1)

            # TimeLimit.truncated の bootstrap 処理。
            #
            # NOTE:
            # privileged critic では terminal observation に対応する
            # true hand も本来必要。
            # GodField 側で TimeLimit.truncated を使わないのであれば
            # 現状は通常経路では通らない。
            for idx, done in enumerate(dones):
                if (
                    done
                    and infos[idx].get("terminal_observation") is not None
                    and infos[idx].get("TimeLimit.truncated", False)
                ):
                    terminal_obs = self.policy.obs_to_tensor(infos[idx]["terminal_observation"])[0]

                    # terminal state 用 hidden hand の取得方法を
                    # 別途用意する必要がある。
                    #
                    # GodFieldVectorEnv が TimeLimit.truncated=False 固定なら
                    # この分岐には入らない。
                    raise RuntimeError(
                        "Privileged critic does not yet support TimeLimit.truncated terminal-value bootstrap."
                    )

            # -------------------------------------------------
            # o_t と同じ時刻の h_t を保存
            # -------------------------------------------------
            rollout_buffer.add(
                self._last_obs,
                actions,
                rewards,
                self._last_episode_starts,
                values,
                log_probs,
                opponent_true_hands=opponent_true_hands,
                action_masks=action_masks,
            )

            self._last_obs = new_obs
            self._last_episode_starts = dones

        # -----------------------------------------------------
        # GAE 用の最後の bootstrap value:
        #
        # V(o_T, h_T)
        # -----------------------------------------------------
        with th.no_grad():
            last_obs_tensor = obs_as_tensor(
                self._last_obs,
                self.device,
            )

            last_hands = env.get_opponent_true_hands()

            last_hands_tensor = th.as_tensor(
                last_hands,
                device=self.device,
            )

            values = self.policy.predict_values(
                last_obs_tensor,
                last_hands_tensor,
            )

        rollout_buffer.compute_returns_and_advantage(
            last_values=values,
            dones=dones,
        )

        callback.update_locals(locals())
        callback.on_rollout_end()

        return True

    def train(self) -> None:
        """
        MaskablePPO.train() の privileged critic 対応版。

        PPO の loss 自体は変更しない。
        Critic の value 計算だけ
            V(o)
        から
            V(o, opponent_true_hands)
        に変更する。
        """

        self.policy.set_training_mode(True)

        self._update_learning_rate(self.policy.optimizer)

        clip_range = self.clip_range(self._current_progress_remaining)

        if self.clip_range_vf is not None:
            clip_range_vf = self.clip_range_vf(self._current_progress_remaining)

        entropy_losses = []
        pg_losses = []
        value_losses = []
        clip_fractions = []

        continue_training = True

        # train() が呼ばれるたびに n_epochs 回、
        # 同じ rollout に対して PPO 更新を行う。
        for epoch in range(self.n_epochs):
            approx_kl_divs = []

            for rollout_data in self.rollout_buffer.get(self.batch_size):
                actions = rollout_data.actions

                if isinstance(
                    self.action_space,
                    spaces.Discrete,
                ):
                    actions = actions.long().flatten()

                # -------------------------------------------------
                # Privileged critic:
                #
                # Actor:
                #   rollout_data.observations
                #
                # Critic:
                #   observations + opponent_true_hands
                # -------------------------------------------------
                values, log_prob, entropy = self.policy.evaluate_actions(
                    rollout_data.observations,
                    actions,
                    rollout_data.opponent_true_hands,
                    action_masks=rollout_data.action_masks,
                )

                values = values.flatten()

                # Advantage normalization
                advantages = rollout_data.advantages

                if self.normalize_advantage and len(advantages) > 1:
                    advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

                # -------------------------------------------------
                # PPO policy ratio
                #
                # π_new(a|o) / π_old(a|o)
                # -------------------------------------------------
                ratio = th.exp(log_prob - rollout_data.old_log_prob)

                policy_loss_1 = advantages * ratio

                policy_loss_2 = advantages * th.clamp(
                    ratio,
                    1 - clip_range,
                    1 + clip_range,
                )

                policy_loss = -th.min(
                    policy_loss_1,
                    policy_loss_2,
                ).mean()

                pg_losses.append(policy_loss.item())

                clip_fraction = th.mean((th.abs(ratio - 1) > clip_range).float()).item()

                clip_fractions.append(clip_fraction)

                # -------------------------------------------------
                # Value loss
                #
                # values は privileged critic:
                # V(o_t, h_t)
                # -------------------------------------------------
                if self.clip_range_vf is None:
                    values_pred = values
                else:
                    values_pred = rollout_data.old_values + th.clamp(
                        values - rollout_data.old_values,
                        -clip_range_vf,
                        clip_range_vf,
                    )

                value_loss = F.mse_loss(
                    rollout_data.returns,
                    values_pred,
                )

                value_losses.append(value_loss.item())

                # Entropy loss
                if entropy is None:
                    entropy_loss = -th.mean(-log_prob)
                else:
                    entropy_loss = -th.mean(entropy)

                entropy_losses.append(entropy_loss.item())

                loss = policy_loss + self.ent_coef * entropy_loss + self.vf_coef * value_loss

                # Approximate KL
                with th.no_grad():
                    log_ratio = log_prob - rollout_data.old_log_prob

                    approx_kl_div = th.mean((th.exp(log_ratio) - 1) - log_ratio).cpu().numpy()

                    approx_kl_divs.append(approx_kl_div)

                if self.target_kl is not None and approx_kl_div > 1.5 * self.target_kl:
                    continue_training = False

                    if self.verbose >= 1:
                        print(f"Early stopping at step {epoch} due to reaching max kl: {approx_kl_div:.2f}")

                    break

                # -------------------------------------------------
                # Gradient update
                # -------------------------------------------------
                self.policy.optimizer.zero_grad()

                loss.backward()

                th.nn.utils.clip_grad_norm_(
                    self.policy.parameters(),
                    self.max_grad_norm,
                )

                self.policy.optimizer.step()

            self._n_updates += 1

            if not continue_training:
                break

        explained_var = explained_variance(
            self.rollout_buffer.values.flatten(),
            self.rollout_buffer.returns.flatten(),
        )

        # -----------------------------------------------------
        # Logging
        # -----------------------------------------------------
        self.logger.record(
            "train/entropy_loss",
            np.mean(entropy_losses),
        )

        self.logger.record(
            "train/policy_gradient_loss",
            np.mean(pg_losses),
        )

        self.logger.record(
            "train/value_loss",
            np.mean(value_losses),
        )

        self.logger.record(
            "train/approx_kl",
            np.mean(approx_kl_divs),
        )

        self.logger.record(
            "train/clip_fraction",
            np.mean(clip_fractions),
        )

        self.logger.record(
            "train/loss",
            loss.item(),
        )

        self.logger.record(
            "train/explained_variance",
            explained_var,
        )

        if hasattr(
            self.policy,
            "log_std",
        ):
            self.logger.record(
                "train/std",
                th.exp(self.policy.log_std).mean().item(),
            )

        self.logger.record(
            "train/n_updates",
            self._n_updates,
            exclude="tensorboard",
        )

        self.logger.record(
            "train/clip_range",
            clip_range,
        )

        if self.clip_range_vf is not None:
            self.logger.record(
                "train/clip_range_vf",
                clip_range_vf,
            )
