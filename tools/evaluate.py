"""2つの方策を戦わせて勝率を出す。

方策は名前（random / heuristic / strategic）でも、学習済みモデルの .zip でも
同じように指定できます。特徴抽出器の種類は .zip に保存されているので、
読み込み時に構成を言い直す必要はありません。

使い方::

    # 学習済みモデルの強さをヒューリスティック基準で測る
    uv run python tools/evaluate.py models/league_v2/best_worker_0/best_model.zip

    # 方策どうしを比べる
    uv run python tools/evaluate.py strategic --vs heuristic
    uv run python tools/evaluate.py a.zip --vs b.zip --games 2000
"""

from __future__ import annotations

import argparse
import time

from godfield_rl.evaluation import default_device, play_both_seats, resolve_policy


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("policy", help="評価したい方策（名前 または .zip のパス）")
    parser.add_argument("--vs", default="strategic", help="対戦相手（名前 または .zip）")
    parser.add_argument("--games", type=int, default=1000, help="各席での対戦数")
    parser.add_argument("--num-envs", type=int, default=512,
                        help="並列環境数。方策の推論をまとめる単位なので、大きいほど速い")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--device", default=None, help="既定はGPUがあればcuda")
    parser.add_argument("--amp", action="store_true",
                        help="推論をbfloat16で行う（CUDAのみ・さらに高速）")
    args = parser.parse_args()

    device = args.device or default_device()
    a = resolve_policy(args.policy, seed=args.seed, device=device, amp=args.amp)
    b = resolve_policy(args.vs, seed=args.seed + 1, device=device, amp=args.amp)

    started = time.perf_counter()
    fwd, rev, win_rate = play_both_seats(
        a, b, games=args.games, num_envs=args.num_envs, seed=args.seed
    )
    elapsed = time.perf_counter() - started
    print(f"{args.policy} が席0: {fwd}")
    print(f"{args.vs} が席0: {rev}")
    print(f"\n席を平均した {args.policy} の勝率: {win_rate:.1%}")
    print(f"（{device} / {args.num_envs}環境{' / bf16' if args.amp else ''}"
          f" / {elapsed:.1f}秒）")


if __name__ == "__main__":
    main()
