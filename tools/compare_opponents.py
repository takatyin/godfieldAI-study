"""相手方策どうしを直接対戦させて勝率を測る。

学習の初期対戦相手を変えるときは、まず「その相手が実際に強いか」を確かめないと、
弱い相手に過適合した方策を作ってしまいます。

使い方::

    uv run python tools/compare_opponents.py
    uv run python tools/compare_opponents.py --a strategic --b heuristic --games 2000
"""

from __future__ import annotations

import argparse

import numpy as np

import godfield_core
from godfield_rl.cards import all_cards  # 登録簿の初期化も兼ねる
from godfield_rl.opponents import OPPONENT_KINDS, make_opponent


def play(kind_a: str, kind_b: str, games: int, num_envs: int, seed: int) -> dict:
    """A を席0、B を席1 として対戦させ、A から見た結果を返します。"""
    all_cards()
    pool = godfield_core.EnvPool(num_envs)
    pool.reset(seed)
    players = {0: make_opponent(kind_a, seed), 1: make_opponent(kind_b, seed + 1)}

    fdim = godfield_core.OBSERVATION_FEATURE_SIZE
    adim = godfield_core.ACTION_SPACE_SIZE

    wins = losses = draws = 0
    steps = 0
    while wins + losses + draws < games:
        steps += 1
        if steps > games * 2000:
            raise RuntimeError("決着が進みません。方策が同じ手を返し続けている可能性があります")

        obs_all = pool.get_observations().reshape(num_envs, -1)
        obs = obs_all[:, : fdim - adim]
        masks = obs_all[:, fdim - adim : fdim].astype(bool)
        actors = pool.get_current_actors()

        actions = np.zeros(num_envs, dtype=np.int32)
        for seat, policy in players.items():
            idx = np.flatnonzero(actors == seat)
            if idx.size:
                actions[idx] = policy.act(obs[idx], masks[idx])
        pool.step_all(actions)

        dones = pool.get_dones()
        if dones.any():
            rewards = pool.get_rewards_for(0)
            for i in np.flatnonzero(dones):
                r = rewards[i]
                if r > 0:
                    wins += 1
                elif r < 0:
                    losses += 1
                else:
                    draws += 1

    total = wins + losses + draws
    return {"games": total, "win": wins / total, "loss": losses / total, "draw": draws / total}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--a", default="strategic", choices=list(OPPONENT_KINDS))
    parser.add_argument("--b", default="heuristic", choices=list(OPPONENT_KINDS))
    parser.add_argument("--games", type=int, default=1000)
    parser.add_argument("--num-envs", type=int, default=64)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    # 席の有利不利を打ち消すため、入れ替えても測る
    fwd = play(args.a, args.b, args.games, args.num_envs, args.seed)
    rev = play(args.b, args.a, args.games, args.num_envs, args.seed + 1000)

    print(f"{args.a} が席0: {fwd['games']}局  勝 {fwd['win']:.1%} / 負 {fwd['loss']:.1%}"
          f" / 分 {fwd['draw']:.1%}")
    print(f"{args.b} が席0: {rev['games']}局  勝 {rev['win']:.1%} / 負 {rev['loss']:.1%}"
          f" / 分 {rev['draw']:.1%}")
    a_win = (fwd["win"] + rev["loss"]) / 2
    print(f"\n席を平均した {args.a} の勝率: {a_win:.1%}")


if __name__ == "__main__":
    main()
