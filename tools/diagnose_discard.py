"""「相手の何かを捨てさせる」カードが、撃つ瞬間に本当に効く局面なのかを数える。

女神の石けんは対象の展開済み奇跡を2枚、夜空のホウキは対象の未展開・未使用の
手札を3枚捨てます。対象がそれを持っていなければ、どちらに撃っても何も起きません。

`diagnose_policy.py` の上書き実験で差が出ないとき、それが「方策が正しいから」なのか
「そもそも効く局面が少ないから」なのかは、勝率だけでは分かりません。ここでは
撃つ瞬間の真の状態を読んで、その2つを切り分けます。

観測からは「展開済みか、単に公開されただけか」を区別できない（Observation に
is_deployed が無い）ため、EnvPool.get_state() で真の状態を読みます。1環境ずつの
Python 呼び出しになりますが、対象のカードは出番が少ないので実用になります。

使い方::

    uv run python tools/diagnose_discard.py models/league_v2/best_worker_0/best_model.zip
"""

from __future__ import annotations

import argparse
import time

import numpy as np

from godfield_rl import feature_config as fc
from godfield_rl.cards import all_cards, card_id
from godfield_rl.diagnostics import (
    ACTION_TARGET_OPP,
    ACTION_TARGET_SELF,
    PHASE_TARGET_SELECT,
)
from godfield_rl.env_wrapper import GodFieldVectorEnv
from godfield_rl.evaluation import default_device, load_policy
from godfield_rl.opponents import OPPONENT_KINDS, make_opponent

MIRACLE_IDS = {c["id"] for c in all_cards() if c.get("type") == "miracle"}

# カード名 -> (説明, そのカードが捨てられる枚数を数える関数)
def _deployed_miracles(state, player: int) -> int:
    return sum(
        1 for slot in range(fc.MAX_HAND_SIZE)
        if state.get_true_hand(player, slot) in MIRACLE_IDS
        and state.get_is_deployed(player, slot)
    )


def _plain_hand(state, player: int) -> int:
    return sum(
        1 for slot in range(fc.MAX_HAND_SIZE)
        if state.get_true_hand(player, slot) >= 0
        and not state.get_is_deployed(player, slot)
        and not state.get_is_used(player, slot)
    )


TARGETS = {
    "女神の石けん": ("展開済みの奇跡を2枚捨てる", _deployed_miracles),
    "夜空のホウキ": ("未展開・未使用の手札を3枚捨てる", _plain_hand),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("model_path", help="学習済みモデル（.zip）へのパス")
    parser.add_argument("--num-envs", type=int, default=256)
    parser.add_argument("--steps", type=int, default=4000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--opponent", choices=list(OPPONENT_KINDS), default="strategic")
    parser.add_argument("--device", default=None, help="既定はGPUがあればcuda")
    args = parser.parse_args()

    device = args.device or default_device()
    learner = load_policy(args.model_path, device=device)
    env = GodFieldVectorEnv(args.num_envs, opponent=make_opponent(args.opponent, seed=args.seed + 1))
    env.seed(args.seed)
    obs = env.reset()
    pool = env.core_env

    watched = {card_id(name): name for name in TARGETS}
    records: dict[int, list[tuple[int, int, int]]] = {cid: [] for cid in watched}

    started = time.perf_counter()
    for _ in range(args.steps):
        masks = env.action_masks()
        actions = learner.action_probs(obs, masks).argmax(axis=1).astype(np.int32)

        staged = obs[:, fc.STAGED_CARDS_START].astype(int)
        selectable = (
            (obs[:, fc.PHASE_START + PHASE_TARGET_SELECT] > 0.5)
            & masks[:, ACTION_TARGET_OPP]
            & masks[:, ACTION_TARGET_SELF]
        )
        for cid, name in watched.items():
            count_fn = TARGETS[name][1]
            for i in np.flatnonzero(selectable & (staged == cid)):
                state = pool.get_state(int(i))
                me = state.current_actor_id
                records[cid].append((
                    count_fn(state, me),
                    count_fn(state, 1 - me),
                    int(actions[i] == ACTION_TARGET_OPP),
                ))

        obs, _, _, _ = env.step(actions)
    env.close()

    for cid, name in watched.items():
        arr = np.array(records[cid])
        print(f"\n■ {name}（{TARGETS[name][0]}）を撃つ瞬間: {len(arr)} 回")
        if not len(arr):
            print("  遭遇しませんでした")
            continue
        mine, theirs, chose_opp = arr[:, 0], arr[:, 1], arr[:, 2].astype(bool)
        print(f"  自分が対象を持っている: {(mine > 0).mean():>6.1%}（平均 {mine.mean():.2f} 枚）")
        print(f"  相手が対象を持っている: {(theirs > 0).mean():>6.1%}（平均 {theirs.mean():.2f} 枚）")
        print(f"\n  {'局面':<24}{'回数':>7}{'相手を選んだ':>13}")
        for cond, label in (
            ((mine > 0) & (theirs > 0), "双方が持っている"),
            ((mine == 0) & (theirs > 0), "相手だけが持っている"),
            ((mine > 0) & (theirs == 0), "自分だけが持っている"),
            ((mine == 0) & (theirs == 0), "どちらも持っていない"),
        ):
            n = int(cond.sum())
            rate = f"{chose_opp[cond].mean():.1%}" if n else "-"
            print(f"  {label:<24}{n:>7}{rate:>13}")

    print(f"\n（対 {args.opponent} / {device} / {args.num_envs}環境 x {args.steps}ステップ"
          f" / {time.perf_counter() - started:.1f}秒）")


if __name__ == "__main__":
    main()
