"""bfloat16 の自動混合精度（AMP）で方策を動かすためのラッパー。

Transformer の注意は系列長の2乗でメモリを食うため、履歴を 128 に伸ばした時点で
`batch_size=8192` は 24GB に載らなくなりました（実測: fp32 だと上限 6,144）。
bf16 にすると逆伝播のために保持する活性が半分になり、載るうえに速くなります。

勾配計算だけを切り出した実測（RTX 4070 / 系列長201 / 1024バッチ、
`tools/measure_vram.py`）::

    d128 h4 L2 ff256   fp32  3.16GB  323ms   -> 24GBでの最大バッチ 6,144
    d128 h4 L2 ff256   bf16  2.04GB  169ms   -> 9,472

SB3 の学習ループを通した実測（256環境 / n_steps=32 / batch=2048）でも同じ比::

    d128 h4 L2 ff256   fp32  6.31GB  1,456 steps/sec
    d128 h4 L2 ff256   bf16  4.08GB  2,750 steps/sec   （1.89倍速・VRAM 35%減）

なお同じ実測で d192 h8 L4 は 12GB のカードに載らず（bf16 でも 12.95GB）、
速度が 12〜83 steps/sec まで落ちた。これはスワップの数字であって性能ではないので、
速度を比べるときは必ず「載っている構成どうし」で見ること。

## fp16 ではなく bf16 を使う理由

bf16 は指数部の幅が fp32 と同じなので、値の範囲は fp32 とほぼ変わりません。
そのため fp16 で必要になる GradScaler（勾配のスケーリングと inf 検出）が要らず、
実装も「autocast で包むだけ」で済みます。仮数部は減りますが、PPO の損失は
もともと確率比のクリップで頭打ちにしているので、精度よりも範囲のほうが重要です。

## 何を fp32 に戻すか

autocast は行列積などを bf16 で計算しますが、**損失の集約と最適化は fp32 のまま**に
します。`evaluate_actions` の戻り値（価値・対数尤度・エントロピー）を fp32 へ
キャストして返すのはそのためで、こうすると SB3 側の train() には一切手を入れずに
済みます（SB3 の train() を丸ごと写経すると、上流の更新に追従できなくなる）。
"""

from __future__ import annotations

import torch
from sb3_contrib.common.maskable.policies import MaskableActorCriticPolicy


class AmpMaskableActorCriticPolicy(MaskableActorCriticPolicy):
    """順伝播を bfloat16 の autocast で走らせる方策。

    CUDA が無い環境では autocast を無効にするので、CPU でもそのまま動きます
    （テストや可視化サーバーが CPU で走ることがあるため）。
    """

    def _autocast(self):
        return torch.autocast("cuda", dtype=torch.bfloat16, enabled=torch.cuda.is_available())

    def forward(self, obs, deterministic: bool = False, action_masks=None):
        with self._autocast():
            actions, values, log_prob = super().forward(obs, deterministic=deterministic, action_masks=action_masks)
        return actions, values.float(), log_prob.float()

    def evaluate_actions(self, obs, actions, action_masks=None):
        with self._autocast():
            values, log_prob, entropy = super().evaluate_actions(obs, actions, action_masks=action_masks)
        # 損失の集約と最適化は fp32 で行う。ここを bf16 のまま返すと、
        # 平均を取る段階で仮数部の不足が効いてくる。
        return (
            values.float(),
            log_prob.float(),
            entropy.float() if entropy is not None else None,
        )

    def predict_values(self, obs):
        with self._autocast():
            values = super().predict_values(obs)
        return values.float()


def policy_class(use_amp: bool):
    """`MaskablePPO` に渡す方策クラスを返します。

    use_amp が False のときは文字列 "MlpPolicy" を返し、既定の方策をそのまま
    使わせます（AMP を使わない実行が、ラッパー経由になって挙動が変わらないように）。
    """
    return AmpMaskableActorCriticPolicy if use_amp else "MlpPolicy"
