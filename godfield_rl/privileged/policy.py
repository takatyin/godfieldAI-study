from functools import partial

import numpy as np
import torch as th
import torch.nn as nn
from sb3_contrib.common.maskable.policies import MaskableActorCriticPolicy

from godfield_rl.feature_config import MAX_HAND_SIZE, NUM_CARD_TYPES


class PrivilegedMaskableActorCriticPolicy(MaskableActorCriticPolicy):
    """Actor は通常観測のみ、Critic は相手の真の手札も使う非対称 Actor-Critic。

    Actor:
        π(a | o)

    Critic:
        V(o, h_opp)

    privileged 情報を Actor に流さないことで、推論時には通常観測だけで
    行動できる方策を維持する。
    """

    def __init__(
        self,
        *args,
        hand_embed_dim: int = 16,
        **kwargs,
    ):
        # 親 __init__ 内から override した _build() が呼ばれるため、
        # _build() が使用する属性は super().__init__() より前に定義する。
        self.hand_embed_dim = hand_embed_dim

        # Actor / Critic で feature extractor のパラメータを分離する。
        #
        # Critic の value loss が Actor の特徴抽出器へ直接流れることを避け、
        # privileged critic を通常 Actor から構造的に分離する。
        kwargs["share_features_extractor"] = False

        super().__init__(*args, **kwargs)

    def _build(self, lr_schedule):
        """Actor/Critic のネットワークと optimizer を構築する。"""

        # 通常の Actor / Critic 用 MLP を構築する。
        self._build_mlp_extractor()

        # Actor の latent 表現から action distribution のパラメータを出力する層。
        self.action_net = self.action_dist.proba_distribution_net(
            latent_dim=self.mlp_extractor.latent_dim_pi
        )

        # Critic の latent 表現からスカラー value を出力する層。
        self.value_net = nn.Linear(
            self.mlp_extractor.latent_dim_vf,
            1,
        )

        # ============================================================
        # Privileged critic
        # ============================================================

        # true hand は card ID の列なので、そのまま連続値として扱わず
        # categorical embedding へ変換する。
        #
        # CARD_EMPTY=-1 を +1 して 0 に移すため、
        # embedding は NUM_CARD_TYPES + 1 個用意する。
        self.privileged_hand_embedding = nn.Embedding(
            NUM_CARD_TYPES + 1,
            self.hand_embed_dim,
            padding_idx=0,
        )

        # 通常観測から得た Critic feature:
        #   (B, features_dim)
        #
        # hidden hand embedding:
        #   (B, H, E) -> (B, H*E)
        #
        # を結合すると次元が増えるので、既存 critic MLP が期待する
        # features_dim へ戻す。
        self.critic_fusion = nn.Sequential(
            nn.Linear(
                self.features_dim
                + MAX_HAND_SIZE * self.hand_embed_dim,
                self.features_dim,
            ),
            nn.ReLU(),
        )

        # ============================================================
        # Initialization
        # ============================================================

        if self.ortho_init:
            # SB3 の既存初期化方針を維持する。
            #
            # 中間表現には sqrt(2)、action head は初期方策を
            # 極端に偏らせないため小さい gain、value head は 1。
            module_gains = {
                self.pi_features_extractor: np.sqrt(2),
                self.vf_features_extractor: np.sqrt(2),
                self.mlp_extractor: np.sqrt(2),
                self.action_net: 0.01,
                self.value_net: 1.0,
                self.critic_fusion: np.sqrt(2),
            }

            for module, gain in module_gains.items():
                # gain を固定した init_weights を各 submodule に再帰適用する。
                module.apply(
                    partial(self.init_weights, gain=gain)
                )

        # privileged module を全て登録した「後」で optimizer を作る。
        # これにより hand embedding / critic_fusion も self.parameters()
        # に含まれ、学習対象になる。
        self.optimizer = self.optimizer_class(
            self.parameters(),
            lr=lr_schedule(1),
            **self.optimizer_kwargs,
        )

    def forward(
        self,
        obs: th.Tensor,
        opponent_true_hands: th.Tensor,
        deterministic: bool = False,
        action_masks=None,
    ):
        """Rollout 収集中の action / value / log_prob を計算する。"""

        # ============================================================
        # 通常観測から Actor / Critic の特徴を別々に抽出
        # ============================================================
        pi_features = self.pi_features_extractor(obs)
        vf_features = self.vf_features_extractor(obs)

        # Actor は通常観測だけから計算する。
        # hidden hand はこの経路へ絶対に入れない。
        latent_pi = self.mlp_extractor.forward_actor(pi_features)

        # ============================================================
        # Critic に privileged hand を追加
        # ============================================================

        # CARD_EMPTY=-1 -> embedding index 0
        hand_ids = opponent_true_hands.long() + 1
        hand_ids = th.clamp(
            hand_ids,
            min=0,
            max=NUM_CARD_TYPES,
        )

        hand_features = self.privileged_hand_embedding(hand_ids)
        # (B, H, E)

        # batch 次元を残し、手札スロットと embedding 次元をまとめる。
        hand_features = hand_features.flatten(1)
        # (B, H*E)

        vf_features = th.cat(
            [vf_features, hand_features],
            dim=1,
        )
        # (B, features_dim + H*E)

        # 既存 critic MLP が期待する features_dim に戻す。
        vf_features = self.critic_fusion(vf_features)
        # (B, features_dim)

        latent_vf = self.mlp_extractor.forward_critic(vf_features)

        # privileged critic:
        # V(o_t, h_t)
        values = self.value_net(latent_vf)

        # ============================================================
        # Actor distribution
        # ============================================================
        distribution = self._get_action_dist_from_latent(latent_pi)

        # 非合法行動を除外してから action を選択する。
        if action_masks is not None:
            distribution.apply_masking(action_masks)

        actions = distribution.get_actions(
            deterministic=deterministic
        )

        log_prob = distribution.log_prob(actions)

        # GodField は Discrete action space なので最終的には (B,)。
        actions = actions.reshape(-1)

        return actions, values, log_prob

    def evaluate_actions(
        self,
        obs: th.Tensor,
        actions: th.Tensor,
        opponent_true_hands: th.Tensor,
        action_masks=None,
    ):
        """保存済み action を現在の policy / critic で再評価する。

        PPO train() から呼ばれ、
        log π_new(a_t | o_t), entropy, V(o_t, h_t)
        を計算する。
        """

        pi_features = self.pi_features_extractor(obs)
        vf_features = self.vf_features_extractor(obs)

        # Actor は通常観測のみ。
        latent_pi = self.mlp_extractor.forward_actor(pi_features)

        # Critic は通常観測 + true hand。
        hand_ids = opponent_true_hands.long() + 1
        hand_ids = th.clamp(
            hand_ids,
            min=0,
            max=NUM_CARD_TYPES,
        )

        hand_features = self.privileged_hand_embedding(hand_ids)
        hand_features = hand_features.flatten(1)

        vf_features = th.cat(
            [vf_features, hand_features],
            dim=1,
        )

        vf_features = self.critic_fusion(vf_features)

        latent_vf = self.mlp_extractor.forward_critic(vf_features)
        values = self.value_net(latent_vf)

        distribution = self._get_action_dist_from_latent(latent_pi)

        if action_masks is not None:
            distribution.apply_masking(action_masks)

        # forward() と違い action は新しく sample しない。
        # rollout buffer に保存済みの action の log probability を再計算する。
        log_prob = distribution.log_prob(actions)
        entropy = distribution.entropy()

        return values, log_prob, entropy

    def predict_values(
        self,
        obs: th.Tensor,
        opponent_true_hands: th.Tensor,
    ) -> th.Tensor:
        """Critic の value のみを計算する。

        主に rollout 末尾で GAE bootstrap 用の
        V(o_T, h_T) を計算するために使う。
        """

        vf_features = self.vf_features_extractor(obs)

        hand_ids = opponent_true_hands.long() + 1
        hand_ids = th.clamp(
            hand_ids,
            min=0,
            max=NUM_CARD_TYPES,
        )

        hand_features = self.privileged_hand_embedding(hand_ids)
        hand_features = hand_features.flatten(1)

        vf_features = th.cat(
            [vf_features, hand_features],
            dim=1,
        )

        vf_features = self.critic_fusion(vf_features)

        latent_vf = self.mlp_extractor.forward_critic(vf_features)

        return self.value_net(latent_vf)
    
class AmpPrivilegedMaskableActorCriticPolicy(
    PrivilegedMaskableActorCriticPolicy
):
    def _autocast(self):
        return th.autocast(
            "cuda",
            dtype=th.bfloat16,
            enabled=th.cuda.is_available(),
        )

    def forward(
        self,
        obs,
        opponent_true_hands,
        deterministic=False,
        action_masks=None,
    ):
        with self._autocast():
            actions, values, log_prob = super().forward(
                obs,
                opponent_true_hands,
                deterministic=deterministic,
                action_masks=action_masks,
            )

        return (
            actions,
            values.float(),
            log_prob.float(),
        )

    def evaluate_actions(
        self,
        obs,
        actions,
        opponent_true_hands,
        action_masks=None,
    ):
        with self._autocast():
            values, log_prob, entropy = super().evaluate_actions(
                obs,
                actions,
                opponent_true_hands,
                action_masks=action_masks,
            )

        return (
            values.float(),
            log_prob.float(),
            entropy.float() if entropy is not None else None,
        )

    def predict_values(
        self,
        obs,
        opponent_true_hands,
    ):
        with self._autocast():
            values = super().predict_values(
                obs,
                opponent_true_hands,
            )

        return values.float()
    