"""学習済みモデルの「どこで間違えているか」を実測して表示する。

測り方そのものは `godfield_rl.diagnostics` にあります。ここは表示だけです。

使い方（GPUがあれば既定で使い、環境は512並列でまとめて推論します）::

    uv run python tools/diagnose_policy.py models/league_v3/best_worker_0/best_model.zip
    uv run python tools/diagnose_policy.py MODEL --steps 2000 --amp
    uv run python tools/diagnose_policy.py MODEL --only 夜空のホウキ --steps 6000

出力は4つ。

1. 対象選択フェイズで「相手」を選んだ割合（カード別）
2. そのカードが効く局面かどうかで分けた同じ割合
   （全体の平均だけでは「どちらでも同じ局面」に薄められて判定できない）
3. 1エピソードあたりの意思決定回数と、その長さでの割引率
4. 対象を間違える手が勝率をどれだけ損なっているか。間違えた行動を正しい側へ
   上書きして比較する（学習し直さずに「直す価値」を測れる）
"""

from __future__ import annotations

import argparse
import time

import numpy as np

from godfield_rl.cards import card_info, card_name
from godfield_rl.diagnostics import (
    BUCKET_FOGGED,
    BUCKET_LABELS,
    BUCKET_NEITHER,
    BUCKET_OPP_ONLY,
    BUCKET_SELF,
    BUCKET_UNKNOWN,
    FOCUS,
    OPPONENT_ONLY_CARD_NAMES,
    SELF_ONLY_CARD_NAMES,
    kind_by_card_id,
    run,
)
from godfield_rl.evaluation import default_device, load_policy
from godfield_rl.opponents import OPPONENT_KINDS


def print_target_select(stats, top: int = 20) -> None:
    per_card = stats["per_card"]
    total = sum(n for n, _ in per_card.values())
    opp = sum(o for _, o in per_card.values())
    print(f"\n■ 対象選択フェイズ（自分・相手の両方を選べる局面）: {total} 回")
    if not total:
        print("  遭遇しませんでした")
        return
    print(f"  うち「相手」を選んだ: {opp} 回 ({opp / total:.1%})")
    print(f"\n  {'カード':<20}{'種別':<8}{'遭遇':>7}{'相手を選んだ':>12}{'平均確率':>10}")
    for cid, (n, o) in sorted(per_card.items(), key=lambda kv: -kv[1][0])[:top]:
        name = card_name(cid)
        if name in SELF_ONLY_CARD_NAMES:
            kind = "自分向き"
        elif name in OPPONENT_ONLY_CARD_NAMES:
            kind = "相手向き"
        else:
            kind = card_info(cid).get("type", "?")
        mean_p = float(np.mean(stats["prob_to_opp"][cid]))
        print(f"  {name:<20}{kind:<8}{n:>7}{o / n:>11.1%}{mean_p:>10.3f}")


def print_by_relevance(stats) -> None:
    """効く局面かどうかで分けて、対象選択を見ます。

    全体の平均だけでは「どちらに使っても何も起きない局面」に薄められてしまい、
    肝心の「効く局面で自分を選べているか」が判定できません。
    """
    per_bucket = stats["per_bucket"]
    known = kind_by_card_id()
    print("\n■ そのカードが効く局面かどうかで分けた「相手を選んだ」割合")
    print("  （災いを払う貝がらは自分に災いが無ければ、どちらに使っても何も起きない）")
    header = "".join(f"{label:>18}" for label in BUCKET_LABELS)
    print(f"\n  {'カード':<20}{header}")

    fogged_total = 0
    for cid, buckets in sorted(per_bucket.items(), key=lambda kv: -sum(b[0] for b in kv[1])):
        if cid not in known:
            continue
        fogged_total += buckets[BUCKET_FOGGED][0]
        cells = ""
        for bucket in (BUCKET_SELF, BUCKET_OPP_ONLY, BUCKET_NEITHER):
            n, opp = buckets[bucket]
            cells += f"{f'{opp / n:.1%} ({n})':>18}" if n else f"{'-':>18}"
        print(f"  {card_name(cid):<20}{cells}")

    if fogged_total:
        print(f"\n  ＊ 自分が霧のため相手の状態を判定できず除外: {fogged_total} 回")
    unknown = sorted(
        card_name(cid) for cid, b in per_bucket.items()
        if cid not in known and b[BUCKET_UNKNOWN][0] >= 100
    )
    if unknown:
        print(f"  ＊ 効く条件が観測に無く判定できないカード: {'、'.join(unknown)}")


def print_episodes(stats, gammas=(0.99, 0.995, 0.999)) -> None:
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


def _rate(results) -> tuple[float, int]:
    return ((results > 0).mean(), results.size) if results.size else (float("nan"), 0)


def _se(p1, n1, p2, n2) -> float:
    """2つの勝率の差の標準誤差。"""
    return float(np.sqrt(p1 * (1 - p1) / max(n1, 1) + p2 * (1 - p2) / max(n2, 1)))


def print_override_experiments(learner, base, focus, common) -> None:
    base_wr, base_n = _rate(base["results"])

    print("\n■ 対象の間違いを直したときの勝率の変化")
    print("  ＊ ±は標準誤差。差がこれに埋もれているときは「効果が無い」のではなく")
    print("     「この試行数では測れていない」。")
    print("  ＊ 全局の差は出番の少なさで薄まる。夜空のホウキは全体の数%の局にしか")
    print("     出ないので、間違いが起きた局だけを取り出した右側のほうが感度が高い。")
    print(f"\n  {'直した対象':<20}{'回数':>7}{'全局の差':>14}"
          f"{'該当局':>8}{'該当局の勝率':>15}{'差':>15}")

    for label in focus:
        fixed = run(learner, apply=label, **common)
        fixed_wr, fixed_n = _rate(fixed["results"])
        # 該当局＝そのカードで対象を間違えた局。上書きの有無で選び方が変わらない
        before, before_n = _rate(base["flagged_results"][label])
        after, after_n = _rate(fixed["flagged_results"][label])
        print(
            f"  {label:<20}{fixed['hits'][label]:>7}"
            f"{f'{fixed_wr - base_wr:+.1%} ± {_se(base_wr, base_n, fixed_wr, fixed_n):.1%}':>14}"
            f"{before_n:>8}{f'{before:.1%} -> {after:.1%}':>15}"
            f"{f'{after - before:+.1%} ± {_se(before, before_n, after, after_n):.1%}':>15}"
        )

    print(f"\n  上書きなしの全局勝率: {base_wr:.1%}（{base_n} 局）")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("model_path", help="学習済みモデル（.zip）へのパス")
    parser.add_argument("--num-envs", type=int, default=512,
                        help="並列環境数。方策の推論をまとめる単位なので、大きいほど速い")
    parser.add_argument("--steps", type=int, default=1000, help="環境を進めるステップ数")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--opponent", choices=list(OPPONENT_KINDS), default="strategic",
                        help="対戦相手。heuristic は弱すぎて勝率が飽和し指標にならない")
    parser.add_argument("--only", nargs="*", choices=list(FOCUS), default=None,
                        help="上書き実験を絞る。1件に絞れば --steps を大きく取れて、"
                             "出番の少ないカードでも標準誤差を詰められる")
    parser.add_argument("--device", default=None, help="既定はGPUがあればcuda")
    parser.add_argument("--amp", action="store_true",
                        help="推論をbfloat16で行う（CUDAのみ・さらに高速）")
    args = parser.parse_args()

    focus = {k: v for k, v in FOCUS.items() if args.only is None or k in args.only}
    device = args.device or default_device()
    learner = load_policy(args.model_path, device=device, amp=args.amp)
    common = dict(num_envs=args.num_envs, steps=args.steps, seed=args.seed,
                  opponent=args.opponent, focus=focus)

    started = time.perf_counter()
    base = run(learner, apply=None, **common)
    print_target_select(base)
    print_by_relevance(base)
    print_episodes(base)
    print_override_experiments(learner, base, focus, common)

    print(f"\n（対 {args.opponent} / {device} / {args.num_envs}環境 x {args.steps}ステップ"
          f" x {len(focus) + 1}回{' / bf16' if args.amp else ''}"
          f" / {time.perf_counter() - started:.1f}秒）")


if __name__ == "__main__":
    main()
