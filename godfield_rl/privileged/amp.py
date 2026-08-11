import torch as th

from godfield_rl.privileged.policy import (
    PrivilegedMaskableActorCriticPolicy,
)


class AmpPrivilegedMaskableActorCriticPolicy(PrivilegedMaskableActorCriticPolicy):
    """Privileged critic policy を bf16 autocast で動かす。"""

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

        return actions, values.float(), log_prob.float()

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


def privileged_policy_class(use_amp: bool):
    return AmpPrivilegedMaskableActorCriticPolicy if use_amp else PrivilegedMaskableActorCriticPolicy
