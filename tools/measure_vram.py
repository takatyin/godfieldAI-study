"""学習1ステップ（順伝播＋逆伝播）のVRAM使用量を実測する。

Transformer の注意は系列長の2乗でメモリを食うため、履歴を伸ばすと
バッチサイズを下げないと載らなくなります。「載るかどうか」は推測ではなく
測ってから決めるべきなので、このツールで実測します。

バッチサイズに対してほぼ線形に増えるので、小さいGPUで測った値からでも
目的のVRAMに収まるバッチサイズを見積もれます。

使い方::

    uv run python tools/measure_vram.py
    uv run python tools/measure_vram.py --budget-gb 24 --batch-sizes 1024 2048 4096
"""

from __future__ import annotations

import argparse
import time

import numpy as np
import torch
from sb3_contrib import MaskablePPO

import godfield_core
from godfield_rl.cards import all_cards
from godfield_rl.env_wrapper import GodFieldVectorEnv
from godfield_rl.feature_extractor import (
    GodFieldFeatureExtractor,
    GodFieldTransformerExtractor,
)
from godfield_rl.opponents import make_opponent

GB = 1024 ** 3


def build_policy(use_transformer: bool, **kwargs):
    all_cards()
    env = GodFieldVectorEnv(8, opponent=make_opponent("heuristic"))
    if use_transformer:
        policy_kwargs = dict(
            features_extractor_class=GodFieldTransformerExtractor,
            features_extractor_kwargs=kwargs,
        )
    else:
        policy_kwargs = dict(
            features_extractor_class=GodFieldFeatureExtractor,
            features_extractor_kwargs=dict(card_embed_dim=16, features_dim=256),
        )
    model = MaskablePPO(
        "MlpPolicy", env, n_steps=8, batch_size=32, device="cuda",
        verbose=0, policy_kwargs=policy_kwargs,
    )
    env.close()
    return model.policy


def measure(policy, batch_size: int, obs_dim: int, amp: bool = False) -> tuple[float, float]:
    """1ミニバッチぶんの順伝播＋逆伝播でのピークVRAM（GB）と所要時間（ms）。

    amp=True なら bfloat16 の autocast で計測します。bf16 は fp16 と違い
    指数部が fp32 と同じなので GradScaler が要らず、RLの損失でも桁溢れしにくい。
    """
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()

    obs = torch.randn(batch_size, obs_dim, device="cuda")
    masks = torch.ones(batch_size, godfield_core.ACTION_SPACE_SIZE, dtype=torch.bool, device="cuda")
    actions = torch.zeros(batch_size, dtype=torch.long, device="cuda")

    def one_step() -> None:
        with torch.autocast("cuda", dtype=torch.bfloat16, enabled=amp):
            values, log_prob, entropy = policy.evaluate_actions(obs, actions, action_masks=masks)
            loss = values.mean() + log_prob.mean() + entropy.mean()
        # 損失のスケールは fp32 に戻してから逆伝播する
        loss.float().backward()
        policy.zero_grad(set_to_none=True)

    one_step()   # ウォームアップ（初回はカーネル選択で余分に確保する）
    torch.cuda.synchronize()
    torch.cuda.reset_peak_memory_stats()
    t0 = time.perf_counter()
    for _ in range(3):
        one_step()
    torch.cuda.synchronize()
    ms = (time.perf_counter() - t0) / 3 * 1000

    peak = torch.cuda.max_memory_allocated() / GB
    torch.cuda.empty_cache()
    return peak, ms


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--budget-gb", type=float, default=24.0, help="目標VRAM（GB）")
    parser.add_argument("--batch-sizes", type=int, nargs="+", default=[512, 1024, 2048])
    parser.add_argument("--safety", type=float, default=0.8,
                        help="見積もりに掛ける安全率（断片化と推論ぶんの余裕）")
    parser.add_argument("--grad-checkpointing", action="store_true",
                        help="勾配チェックポイントを有効にして測る（run_league.sh の既定）")
    args = parser.parse_args()

    if not torch.cuda.is_available():
        raise SystemExit("GPUがありません")

    obs_dim = godfield_core.OBSERVATION_FEATURE_SIZE - godfield_core.ACTION_SPACE_SIZE
    seq_len = 1 + godfield_core.MAX_HAND_SIZE * 4 + godfield_core.HISTORY_LENGTH
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"HISTORY_LENGTH={godfield_core.HISTORY_LENGTH} / 系列長={seq_len} / 観測={obs_dim}")
    print(f"目標VRAM={args.budget_gb}GB（安全率 {args.safety}）\n")

    ckpt = args.grad_checkpointing
    suffix = " +ckpt" if ckpt else ""
    configs = [
        ("MLP", False, {}),
        (f"Transformer d128 h4 L2 ff256{suffix}", True,
         dict(d_model=128, nhead=4, num_layers=2, dim_feedforward=256, features_dim=256,
              grad_checkpointing=ckpt)),
        (f"Transformer d192 h8 L4 ff768{suffix}", True,
         dict(d_model=192, nhead=8, num_layers=4, dim_feedforward=768, features_dim=256,
              grad_checkpointing=ckpt)),
        (f"Transformer d256 h8 L6 ff1024{suffix}", True,
         dict(d_model=256, nhead=8, num_layers=6, dim_feedforward=1024, features_dim=256,
              grad_checkpointing=ckpt)),
    ]

    print(f"{'構成':<30}{'精度':<7}"
          + "".join(f"{b:>10}" for b in args.batch_sizes)
          + f"{'→予算内の最大':>14}{'1更新':>9}")
    for label, use_tf, kw in configs:
        policy = build_policy(use_tf, **kw)
        for amp in (False, True):
            peaks, times = [], []
            for b in args.batch_sizes:
                try:
                    p, ms = measure(policy, b, obs_dim, amp=amp)
                except torch.cuda.OutOfMemoryError:
                    p, ms = float("nan"), float("nan")
                    torch.cuda.empty_cache()
                peaks.append(p)
                times.append(ms)
            cells = "".join(f"{p:>9.2f}G" if p == p else f"{'OOM':>10}" for p in peaks)

            # バッチサイズに対する線形近似から、目標VRAMに収まる最大バッチを見積もる
            valid = [(b, p) for b, p in zip(args.batch_sizes, peaks) if p == p]
            if len(valid) >= 2:
                bs = np.array([b for b, _ in valid], dtype=float)
                gb = np.array([p for _, p in valid], dtype=float)
                slope, intercept = np.polyfit(bs, gb, 1)
                fit = int((args.budget_gb * args.safety - intercept) / slope) if slope > 0 else 0
                est = f"{max(0, (fit // 256) * 256):>13,}"
            else:
                est = f"{'測定不足':>14}"
            last = next((t for t in reversed(times) if t == t), float("nan"))
            print(f"{label:<30}{'bf16' if amp else 'fp32':<7}{cells}{est}"
                  + (f"{last:>8.0f}ms" if last == last else f"{'-':>9}"))
        del policy
        torch.cuda.empty_cache()

    print("\n※ 見積もりは「勾配計算のピーク」に対するもの。実際にはロールアウト中の")
    print("   推論と、自己対戦なら相手モデルのぶんも同じGPUに載る点に注意。")
    print("※ SB3 の RolloutBuffer は numpy（CPU側）なので、num_envs が効くのは")
    print("   主にシステムRAMのはず。ただしこれは実装から読んだだけで未実測。")
    print("※ 大きい構成の所要時間は、12GBのGPUで測ると確保に失敗して再試行が")
    print("   混ざるため当てにならない。速度は載る構成の値だけを見ること。")


if __name__ == "__main__":
    main()
