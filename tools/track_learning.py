"""世代ごとのチェックポイントを並べて、対象選択が収束しているかを見る。

`diagnose_policy.py` は1つのモデルを詳しく調べますが、それだけでは
「この値はもう収束したのか、まだ動いている途中なのか」が判定できません。
たとえばスマイルの花（MP+5）の 16.4% は、学習が足りないのか、
エントロピー項（ent_coef）と釣り合った収束値なのかが1点では区別できません。

リーグ学習は `worker_N_gen_M.zip` をプールに貯めていくので、それを世代順に
並べて同じ測定を掛ければ、推移として答えが出ます。

使い方（学習を回しているサーバー上で実行するのが速い）::

    uv run python tools/track_learning.py "models/league_v2/worker_1_gen_*.zip"
    uv run python tools/track_learning.py POOL/*.zip --steps 800
"""

from __future__ import annotations

import argparse
import glob
import re
import time

# diagnose_policy は import 時にカードマスタを読み込む（何度呼んでも安全）
from diagnose_policy import (
    BUCKET_SELF,
    CARD_BY_ID,
    KIND_BY_CARD_ID,
    OPPONENT_KINDS,
    default_device,
    load_learner,
    run,
)

# 既定で追う顔ぶれ。効果量の大きいものから小さいものまで入れてあるので、
# 「効果が小さいカードほど高い確率で釣り合う」のかどうかが読み取れる。
TRACKED = (
    "ロマンスウォーター",   # HP+15
    "ハートのしずく",       # HP+10
    "スマイルのしずく",     # HP+5
    "ロマンスの香木",       # MP+15
    "ハートの花",           # MP+10
    "スマイルの花",         # MP+5
    "スマイルの貝がら",     # 災いを払う
    "ハートの貝がら",
    "夜空のホウキ",         # 相手向き
    "女神の石けん",
)


def _generation(path: str) -> tuple[int, int]:
    """worker_N_gen_M.zip から (M, N) を取り出して並べ替えに使います。"""
    gen = re.search(r"gen_?(\d+)", path)
    worker = re.search(r"worker_?(\d+)", path)
    return (int(gen.group(1)) if gen else 0, int(worker.group(1)) if worker else 0)


def _expand(patterns: list[str]) -> list[str]:
    paths: list[str] = []
    for pattern in patterns:
        # シェルが展開しない環境（PowerShell）でもグロブを使えるようにする
        matched = sorted(glob.glob(pattern))
        paths.extend(matched or [pattern])
    return sorted(dict.fromkeys(paths), key=_generation)


def _rate(buckets, bucket_index: int) -> str:
    n, opp = buckets[bucket_index]
    return f"{opp / n:.1%}" if n else "-"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("models", nargs="+", help="チェックポイント（グロブ可）")
    parser.add_argument("--num-envs", type=int, default=512)
    parser.add_argument("--steps", type=int, default=400,
                        help="1モデルあたりのステップ数。推移を見るだけなので少なくてよい")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--opponent", choices=list(OPPONENT_KINDS), default="strategic",
                        help="対戦相手。heuristic は弱すぎて勝率が飽和し指標にならない")
    parser.add_argument("--device", default=None, help="既定はGPUがあればcuda")
    parser.add_argument("--amp", action="store_true", help="推論をbfloat16で行う")
    args = parser.parse_args()

    paths = _expand(args.models)
    if not paths:
        raise SystemExit("チェックポイントが1つも見つかりませんでした")

    device = args.device or default_device()
    started = time.perf_counter()

    labels: list[str] = []
    overall: list[dict] = []
    for path in paths:
        gen, worker = _generation(path)
        labels.append(f"w{worker}g{gen}")
        learner = load_learner(path, device=device, amp=args.amp)
        overall.append(
            run(learner, num_envs=args.num_envs, steps=args.steps,
                seed=args.seed, opponent=args.opponent)
        )

    tracked_ids = [cid for cid, c in CARD_BY_ID.items() if c["name"] in TRACKED]
    tracked_ids.sort(key=lambda cid: TRACKED.index(CARD_BY_ID[cid]["name"]))

    header = "".join(f"{label:>10}" for label in labels)
    print(f"\n■ 対象選択で「相手」を選んだ割合の推移\n\n  {'カード':<20}{header}")
    for cid in tracked_ids:
        cells = ""
        for stats in overall:
            n, opp = stats["per_card"].get(cid, (0, 0))
            cells += f"{f'{opp / n:.1%}' if n else '-':>10}"
        print(f"  {CARD_BY_ID[cid]['name']:<20}{cells}")

    relevant = [cid for cid in tracked_ids if cid in KIND_BY_CARD_ID]
    print(f"\n■ うち「自分に効く局面」に限った同じ割合\n\n  {'カード':<20}{header}")
    for cid in relevant:
        cells = "".join(
            f"{_rate(stats['per_bucket'][cid], BUCKET_SELF):>10}" for stats in overall
        )
        print(f"  {CARD_BY_ID[cid]['name']:<20}{cells}")

    win_rates = "".join(
        f"{(stats['results'] > 0).mean():>10.1%}" if stats["results"].size else f"{'-':>10}"
        for stats in overall
    )
    print(f"\n■ 対 {args.opponent} 勝率\n\n  {'':<20}{win_rates}")

    print(f"\n（{device} / {args.num_envs}環境 x {args.steps}ステップ x {len(paths)}モデル"
          f"{' / bf16' if args.amp else ''} / {time.perf_counter() - started:.1f}秒）")


if __name__ == "__main__":
    main()
