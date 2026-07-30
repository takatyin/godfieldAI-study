"""学習済みモデルの「どこで間違えているか」を実測する診断ツール。

勝率だけを見ていると、方策が特定の局面で潰れていても気付けません。実際、
gen50 の Transformer / MLP はどちらも対象選択フェイズで **100%「相手」を選ぶ**まで
潰れており、回復系の雑貨を相手に使っていました（勝率は 85% 出ていた）。

使い方::

    uv run python tools/diagnose_policy.py assets/models/best_transformer_gen50.zip
    uv run python tools/diagnose_policy.py MODEL --steps 6000 --num-envs 64

出力は3つ。

1. 対象選択フェイズで「相手」を選んだ割合（カード別）
2. 自分に使うべきカードを相手に使う間違いが、勝率をどれだけ損なっているか
   （行動を上書きして比較する。学習し直さずに「直す価値」を測れる）
3. 1エピソードあたりの意思決定回数と、その長さでの割引率
   （終端報酬がどれだけ薄まっているか＝信用割当が問題かどうかの判断材料）
"""

from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict

import numpy as np
import torch

import godfield_core

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

with open(os.path.join(PROJECT_ROOT, "assets", "godfield_cards.json"), encoding="utf-8") as _f:
    CARDS = json.load(_f)
if godfield_core.get_registry_size() == 0:
    godfield_core.init_game_logic(CARDS)

from godfield_rl import feature_config as fc  # noqa: E402
from godfield_rl.env_wrapper import GodFieldVectorEnv  # noqa: E402
from godfield_rl.evaluation import load_policy  # noqa: E402
from godfield_rl.opponents import make_opponent  # noqa: E402

CARD_BY_ID = {c["id"]: c for c in CARDS}
ACTION_TARGET_OPP = int(godfield_core.ActionType.ACTION_TARGET_OPP)
ACTION_TARGET_SELF = int(godfield_core.ActionType.ACTION_TARGET_SELF)
PHASE_TARGET_SELECT = int(godfield_core.GamePhase.PHASE_MAIN_TARGET_SELECT)

# 相手に使うと相手を利するカード。カードデータからは機械的に判別できないので名指しする
# （説明文に「HP」を含むだけでは攻撃カードも拾ってしまう）。
SELF_ONLY_CARD_NAMES = (
    "スマイルのしずく", "ハートのしずく", "ロマンスウォーター", "天の川のおいしい水",
    "スマイルの花", "ハートの花", "ロマンスの香木",
    "スマイルの貝がら", "ハートの貝がら",
    "守護封印のつぼ",
)


def self_only_card_ids() -> set[int]:
    ids = {c["id"] for c in CARDS if c["name"] in SELF_ONLY_CARD_NAMES}
    missing = set(SELF_ONLY_CARD_NAMES) - {CARD_BY_ID[i]["name"] for i in ids}
    if missing:
        raise KeyError(f"カード名がカードデータに見つかりません: {sorted(missing)}")
    return ids


def load_model(path: str, device: str = "cpu"):
    """特徴抽出器の種類は保存済みモデルから復元されるので、指定は不要です。"""
    return load_policy(os.path.join(PROJECT_ROOT, path), device=device).model


def _target_select_mask(obs: np.ndarray, masks: np.ndarray) -> np.ndarray:
    """対象選択フェイズで、自分・相手の両方を選べる環境の添字。"""
    in_phase = obs[:, fc.PHASE_START + PHASE_TARGET_SELECT] > 0.5
    both = masks[:, ACTION_TARGET_OPP] & masks[:, ACTION_TARGET_SELF]
    return np.flatnonzero(in_phase & both)


def run(model, *, num_envs: int, steps: int, seed: int, override_self_only: bool):
    """1回まわして、対象選択の統計・エピソード長・勝敗を集めます。"""
    self_only = self_only_card_ids()
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
        actions, _ = model.predict(obs, action_masks=masks, deterministic=True)

        if idx.size:
            with torch.no_grad():
                dist = model.policy.get_distribution(
                    torch.as_tensor(obs[idx], dtype=torch.float32),
                    action_masks=torch.as_tensor(masks[idx]),
                )
                probs = dist.distribution.probs.numpy()[:, ACTION_TARGET_OPP]
            staged = obs[idx, fc.STAGED_CARDS_START].astype(int)
            chose_opp = actions[idx] == ACTION_TARGET_OPP
            for card_id, opp, p in zip(staged, chose_opp, probs):
                per_card[int(card_id)][0] += 1
                per_card[int(card_id)][1] += int(opp)
                prob_to_opp[int(card_id)].append(float(p))

        if override_self_only:
            staged_all = obs[:, fc.STAGED_CARDS_START].astype(int)
            in_phase = obs[:, fc.PHASE_START + PHASE_TARGET_SELECT] > 0.5
            bad = (
                in_phase
                & np.isin(staged_all, list(self_only))
                & masks[:, ACTION_TARGET_SELF]
                & (actions == ACTION_TARGET_OPP)
            )
            overridden += int(bad.sum())
            actions = np.where(bad, ACTION_TARGET_SELF, actions)

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
        kind = "自分向き" if name in SELF_ONLY_CARD_NAMES else card.get("type", "?")
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
    parser.add_argument("--num-envs", type=int, default=64)
    parser.add_argument("--steps", type=int, default=4000, help="環境を進めるステップ数")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()

    model = load_model(args.model_path, device=args.device)
    common = dict(num_envs=args.num_envs, steps=args.steps, seed=args.seed)

    base = run(model, override_self_only=False, **common)
    _print_target_select(base)
    _print_episodes(base)

    fixed = run(model, override_self_only=True, **common)
    base_wr = (base["results"] > 0).mean() if base["results"].size else float("nan")
    fixed_wr = (fixed["results"] > 0).mean() if fixed["results"].size else float("nan")
    print("\n■ 「自分に使うべきカードを相手に使う」間違いを上書きした場合")
    print(f"  対象: {'、'.join(SELF_ONLY_CARD_NAMES)}")
    print(f"  上書き回数: {fixed['overridden']}")
    print(f"  勝率 {base_wr:.1%} -> {fixed_wr:.1%}  （差 {fixed_wr - base_wr:+.1%}）")


if __name__ == "__main__":
    main()
