"""学習済みモデルの「どこで間違えているか」を実測する診断ツール。

勝率だけを見ていると、方策が特定の局面で潰れていても気付けません。実際、
gen50 の Transformer / MLP はどちらも対象選択フェイズで **100%「相手」を選ぶ**まで
潰れており、回復系の雑貨を相手に使っていました（勝率は 85% 出ていた）。

使い方（GPUがあれば既定で使い、環境は512並列でまとめて推論します）::

    uv run python tools/diagnose_policy.py models/league_v2/best_worker_0/best_model.zip
    uv run python tools/diagnose_policy.py MODEL --steps 2000 --amp

出力は3つ。

1. 対象選択フェイズで「相手」を選んだ割合（カード別）
2. 対象を間違える手が、勝率をどれだけ損なっているか。自分向き・相手向きの
   両方向で、間違えた行動を正しい側へ上書きして比較する
   （学習し直さずに「直す価値」を測れる）
3. 1エピソードあたりの意思決定回数と、その長さでの割引率
   （終端報酬がどれだけ薄まっているか＝信用割当が問題かどうかの判断材料）
"""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import defaultdict

import numpy as np

import godfield_core

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

with open(os.path.join(PROJECT_ROOT, "assets", "godfield_cards.json"), encoding="utf-8") as _f:
    CARDS = json.load(_f)
if godfield_core.get_registry_size() == 0:
    godfield_core.init_game_logic(CARDS)

from godfield_rl import feature_config as fc  # noqa: E402
from godfield_rl.env_wrapper import GodFieldVectorEnv  # noqa: E402
from godfield_rl.evaluation import default_device, load_policy  # noqa: E402
from godfield_rl.opponents import make_opponent  # noqa: E402

CARD_BY_ID = {c["id"]: c for c in CARDS}
ACTION_TARGET_OPP = int(godfield_core.ActionType.ACTION_TARGET_OPP)
ACTION_TARGET_SELF = int(godfield_core.ActionType.ACTION_TARGET_SELF)
PHASE_TARGET_SELECT = int(godfield_core.GamePhase.PHASE_MAIN_TARGET_SELECT)

# 対象を間違えると損をするカード。カードデータからは機械的に判別できないので名指しする
# （説明文に「HP」を含むだけでは攻撃カードも拾ってしまう）。
#
# 自分向き。相手に使うと相手を利する。
# 貝がらは回復ではなく災いを払うカードなので、こちらに災いが無い局面では
# どちらを選んでも何も起きない。確率が 0.5 付近に留まりやすいのはそのため。
SELF_ONLY_CARD_NAMES = (
    "スマイルのしずく", "ハートのしずく", "ロマンスウォーター", "天の川のおいしい水",
    "スマイルの花", "ハートの花", "ロマンスの香木",
    "スマイルの貝がら", "ハートの貝がら",
    "守護封印のつぼ",
)

# 相手向き。自分に使うと自分の奇跡・神器を捨てたり、取引を相手に渡さない分だけ損をする。
OPPONENT_ONLY_CARD_NAMES = (
    "女神の石けん", "夜空のホウキ", "売る", "買う",
)


def _card_ids(names: tuple[str, ...]) -> set[int]:
    ids = {c["id"] for c in CARDS if c["name"] in names}
    missing = set(names) - {CARD_BY_ID[i]["name"] for i in ids}
    if missing:
        raise KeyError(f"カード名がカードデータに見つかりません: {sorted(missing)}")
    return ids


def load_learner(path: str, device: str | None = None, amp: bool = False):
    """特徴抽出器の種類は保存済みモデルから復元されるので、指定は不要です。"""
    return load_policy(os.path.join(PROJECT_ROOT, path), device=device, amp=amp)


def _target_select_mask(obs: np.ndarray, masks: np.ndarray) -> np.ndarray:
    """対象選択フェイズで、自分・相手の両方を選べる環境の添字。"""
    in_phase = obs[:, fc.PHASE_START + PHASE_TARGET_SELECT] > 0.5
    both = masks[:, ACTION_TARGET_OPP] & masks[:, ACTION_TARGET_SELF]
    return np.flatnonzero(in_phase & both)


def run(learner, *, num_envs: int, steps: int, seed: int, override: str | None):
    """1回まわして、対象選択の統計・エピソード長・勝敗を集めます。

    override に "self" / "opp" を渡すと、そのカード群で対象を間違えた行動を
    正しい側へ上書きします。学習し直さずに「直す価値」を測るための実験です。
    """
    forced_ids, right_action, wrong_action = {
        None: (set(), 0, 0),
        "self": (_card_ids(SELF_ONLY_CARD_NAMES), ACTION_TARGET_SELF, ACTION_TARGET_OPP),
        "opp": (_card_ids(OPPONENT_ONLY_CARD_NAMES), ACTION_TARGET_OPP, ACTION_TARGET_SELF),
    }[override]
    env = GodFieldVectorEnv(num_envs, opponent=make_opponent("heuristic", seed=seed + 1))
    env.seed(seed)
    obs = env.reset()

    per_card: dict[int, list[int]] = defaultdict(lambda: [0, 0])  # id -> [遭遇, 相手を選んだ]
    prob_to_opp: dict[int, list[float]] = defaultdict(list)
    ep_steps = np.zeros(num_envs, dtype=np.int64)
    lengths: list[int] = []
    results: list[float] = []
    overridden = 0

    for _ in range(steps):
        masks = env.action_masks()
        idx = _target_select_mask(obs, masks)

        # 行動と確率は同じ分布から取れるので、順伝播は1回で済ませる（以前は
        # predict と get_distribution で2回まわしていた）。deterministic な行動は
        # 確率の argmax と同じもの。
        probs = learner.action_probs(obs, masks)
        actions = probs.argmax(axis=1).astype(np.int32)

        if idx.size:
            staged = obs[idx, fc.STAGED_CARDS_START].astype(int)
            chose_opp = actions[idx] == ACTION_TARGET_OPP
            for card_id, opp, p in zip(staged, chose_opp, probs[idx, ACTION_TARGET_OPP]):
                per_card[int(card_id)][0] += 1
                per_card[int(card_id)][1] += int(opp)
                prob_to_opp[int(card_id)].append(float(p))

        if forced_ids:
            staged_all = obs[:, fc.STAGED_CARDS_START].astype(int)
            in_phase = obs[:, fc.PHASE_START + PHASE_TARGET_SELECT] > 0.5
            bad = (
                in_phase
                & np.isin(staged_all, list(forced_ids))
                & masks[:, right_action]
                & (actions == wrong_action)
            )
            overridden += int(bad.sum())
            actions = np.where(bad, right_action, actions)

        obs, rewards, dones, _ = env.step(actions)
        ep_steps += 1
        for i in np.flatnonzero(dones):
            lengths.append(int(ep_steps[i]))
            results.append(float(rewards[i]))
            ep_steps[i] = 0

    env.close()
    return {
        "per_card": per_card,
        "prob_to_opp": prob_to_opp,
        "lengths": np.array(lengths),
        "results": np.array(results),
        "overridden": overridden,
    }


def _print_target_select(stats, top: int = 20) -> None:
    per_card = stats["per_card"]
    total = sum(n for n, _ in per_card.values())
    opp = sum(o for _, o in per_card.values())
    print(f"\n■ 対象選択フェイズ（自分・相手の両方を選べる局面）: {total} 回")
    if not total:
        print("  遭遇しませんでした")
        return
    print(f"  うち「相手」を選んだ: {opp} 回 ({opp / total:.1%})")
    print(f"\n  {'カード':<20}{'種別':<8}{'遭遇':>7}{'相手を選んだ':>12}{'平均確率':>10}")
    for card_id, (n, o) in sorted(per_card.items(), key=lambda kv: -kv[1][0])[:top]:
        card = CARD_BY_ID.get(card_id, {})
        name = card.get("name", f"id{card_id}")
        if name in SELF_ONLY_CARD_NAMES:
            kind = "自分向き"
        elif name in OPPONENT_ONLY_CARD_NAMES:
            kind = "相手向き"
        else:
            kind = card.get("type", "?")
        mean_p = float(np.mean(stats["prob_to_opp"][card_id]))
        print(f"  {name:<20}{kind:<8}{n:>7}{o / n:>11.1%}{mean_p:>10.3f}")


def _print_episodes(stats, gammas=(0.99, 0.995, 0.999)) -> None:
    lengths, results = stats["lengths"], stats["results"]
    print(f"\n■ エピソード: {lengths.size} 局")
    if not lengths.size:
        return
    print(f"  学習者の意思決定回数/局: 平均 {lengths.mean():.0f} / 中央 {np.median(lengths):.0f}"
          f" / 最大 {lengths.max()}")
    for g in gammas:
        print(f"    gamma={g}: 局の開始時点で終端報酬は {g ** lengths.mean():.3f} 倍に減衰")
    print(f"  勝率 {(results > 0).mean():.1%} / 引分 {(results == 0).mean():.1%}"
          f" / 敗北 {(results < 0).mean():.1%}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("model_path", help="学習済みモデル（.zip）へのパス")
    parser.add_argument("--num-envs", type=int, default=512,
                        help="並列環境数。方策の推論をまとめる単位なので、大きいほど速い")
    parser.add_argument("--steps", type=int, default=1000, help="環境を進めるステップ数")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--device", default=None, help="既定はGPUがあればcuda")
    parser.add_argument("--amp", action="store_true",
                        help="推論をbfloat16で行う（CUDAのみ・さらに高速）")
    args = parser.parse_args()

    device = args.device or default_device()
    learner = load_learner(args.model_path, device=device, amp=args.amp)
    common = dict(num_envs=args.num_envs, steps=args.steps, seed=args.seed)

    started = time.perf_counter()
    base = run(learner, override=None, **common)
    _print_target_select(base)
    _print_episodes(base)

    def win_rate(stats) -> float:
        return (stats["results"] > 0).mean() if stats["results"].size else float("nan")

    base_wr = win_rate(base)
    for override, title, names in (
        ("self", "自分に使うべきカードを相手に使う", SELF_ONLY_CARD_NAMES),
        ("opp", "相手に使うべきカードを自分に使う", OPPONENT_ONLY_CARD_NAMES),
    ):
        fixed = run(learner, override=override, **common)
        fixed_wr = win_rate(fixed)
        print(f"\n■ 「{title}」間違いを上書きした場合")
        print(f"  対象: {'、'.join(names)}")
        print(f"  上書き回数: {fixed['overridden']}")
        print(f"  勝率 {base_wr:.1%} -> {fixed_wr:.1%}  （差 {fixed_wr - base_wr:+.1%}）")

    print(f"\n（{device} / {args.num_envs}環境 x {args.steps}ステップ x 3回"
          f"{' / bf16' if args.amp else ''} / {time.perf_counter() - started:.1f}秒）")


if __name__ == "__main__":
    main()
