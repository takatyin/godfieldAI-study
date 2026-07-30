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

from godfield_rl.evaluation import play_both_seats, resolve_policy


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("policy", help="評価したい方策（名前 または .zip のパス）")
    parser.add_argument("--vs", default="strategic", help="対戦相手（名前 または .zip）")
    parser.add_argument("--games", type=int, default=1000, help="各席での対戦数")
    parser.add_argument("--num-envs", type=int, default=64)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()

    a = resolve_policy(args.policy, seed=args.seed, device=args.device)
    b = resolve_policy(args.vs, seed=args.seed + 1, device=args.device)

    fwd, rev, win_rate = play_both_seats(
        a, b, games=args.games, num_envs=args.num_envs, seed=args.seed
    )
    print(f"{args.policy} が席0: {fwd}")
    print(f"{args.vs} が席0: {rev}")
    print(f"\n席を平均した {args.policy} の勝率: {win_rate:.1%}")


if __name__ == "__main__":
    main()
