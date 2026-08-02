"""「買う」「売る」の判断を測り、直したときに勝率がどれだけ変わるかを出す。

測り方そのものは `godfield_rl.trade_analysis` にあります。ここは表示だけです。

出力は2つ。

1. 人が見て答えの割れない局面での振る舞い
   （無料の奇跡を買っているか、高額な札を出品しているか、など）
2. その判断を正しい方へ上書きしたときの勝率の変化（`--value`）

2 が無いと見た目の悪い数字に引きずられます。実際「自分に売っている 42.4%」は
上書きすると勝率が **下がりました**（−1.0pt）。売ると相手にカードが渡るので、
無選別に相手へ売るのは良い札の献上になるためです。

使い方::

    uv run python tools/diagnose_trade.py models/league_v5/worker_0_gen_30.zip
    uv run python tools/diagnose_trade.py MODEL --baseline
    uv run python tools/diagnose_trade.py MODEL --value --games 3000
"""

from __future__ import annotations

import argparse
import time

import numpy as np

from godfield_rl.cards import feature
from godfield_rl.evaluation import default_device, resolve_policy
from godfield_rl.opponents import OPPONENT_KINDS, make_opponent
from godfield_rl.trade_analysis import (
    BUY_BUCKETS,
    TradeStats,
    collect,
    measure_value,
    price_of,
    sell_card_id,
    top_cards,
)


def print_buy(stats: TradeStats) -> None:
    rows = stats.buys
    print(f"\n□ 買う: 受諾判断 {len(rows):,} 回")
    if stats.unreadable:
        print(f"  ※ 公開札を観測から読めなかった局面が {stats.unreadable} 件あります")
    if not rows:
        print("  遭遇しませんでした")
        return

    print(f"  全体の受諾率: {sum(1 for b in rows if b.bought) / len(rows):.1%}\n")
    print(f"  {'状況':<16}{'件数':>8}{'買った':>9}{'期待':>8}   よく出た札")
    for name, matches, expected in BUY_BUCKETS:
        n, rate = stats.buy_rate(matches)
        if not n:
            continue
        cards = [b.card for b in rows
                 if matches(feature(b.card, "type", ""), price_of(b.card)) and b.affordable]
        print(f"  {name:<16}{n:>8,}{rate:>8.1%}{expected:>8}   {top_cards(cards)}")

    short = [b for b in rows if not b.affordable]
    if short:
        print(f"\n  （所持金不足で買えない局面 {len(short):,} 件は除外）")


def print_sell(stats: TradeStats) -> None:
    rows = stats.sells
    print(f"\n□ 売る: 出品するカードの選択 {len(rows):,} 回（選択肢が2つ以上）")
    if stats.sold_to_self:
        rate = sum(stats.sold_to_self) / len(stats.sold_to_self)
        print(f"  自分に売った割合: {rate:.1%}（{len(stats.sold_to_self):,} 回中）")
    if not rows:
        print("  遭遇しませんでした")
        return

    def line(label: str, sel) -> None:
        if len(sel) < 30:
            return
        picked = np.mean([price_of(s.picked) for s in sel])
        avail = np.mean([np.mean([price_of(c) for c in s.choices]) for s in sel])
        best = np.mean([s.best_price for s in sel])
        took = np.mean([s.took_best for s in sel])
        print(f"  {label:<26}{len(sel):>7,}{picked:>9.1f}{avail:>10.1f}{best:>9.1f}{took:>11.1%}")

    print(f"\n  {'状況':<26}{'件数':>7}{'選んだ額':>9}{'平均':>10}{'最高額':>9}{'最高を選択':>11}")
    line("全体", rows)
    line("相手の 金+MP が5未満", [s for s in rows if s.opponent_can_pay < 5])
    line("相手の 金+MP が20以上", [s for s in rows if s.opponent_can_pay >= 20])

    poor = [s for s in rows if s.opponent_can_pay < 5]
    if len(poor) >= 30:
        dealt = np.mean([s.damage(price_of(s.picked)) for s in poor])
        best = np.mean([s.damage(s.best_price) for s in poor])
        print(f"\n  相手が払えないときに与えた HP ダメージ: 平均 {dealt:.1f}"
              f"（最高額を選んでいれば {best:.1f}）")


def print_value(base: float, base_se: float, results) -> None:
    print(f"\n□ 直したときの勝率（基準 {base:.1%} ± {base_se:.1f}pt）\n")
    print(f"  {'上書きした判断':<34}{'勝率':>8}{'差':>12}{'上書き回数':>12}")
    for r in results:
        mark = "" if r.significant else "  ※誤差の範囲"
        print(f"  {r.label:<34}{r.win_rate:8.1%}"
              f"{r.delta:+8.1f}±{r.delta_stderr:.1f}pt{r.changed:>12,}{mark}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("policy", help="評価したい方策（名前 または .zip のパス）")
    parser.add_argument("--vs", default="strategic", choices=list(OPPONENT_KINDS))
    parser.add_argument("--games", type=int, default=1500)
    parser.add_argument("--num-envs", type=int, default=256)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--device", default=None)
    parser.add_argument("--amp", action="store_true")
    parser.add_argument("--baseline", action="store_true",
                        help="人手の方策も並べて出す（比較用。正解ではない）")
    parser.add_argument("--value", action="store_true",
                        help="判断を直したときの勝率の変化も測る（時間がかかる）")
    args = parser.parse_args()

    device = args.device or default_device()
    started = time.perf_counter()
    sell_id = sell_card_id()

    policy = resolve_policy(args.policy, seed=args.seed, device=device, amp=args.amp)
    foe = make_opponent(args.vs, seed=args.seed + 1)

    print(f"\n■ {args.policy}")
    stats = collect(policy, foe, games=args.games, num_envs=args.num_envs, seed=args.seed)
    print_buy(stats)
    print_sell(stats)

    if args.baseline:
        ref = make_opponent("strategic", seed=args.seed + 2)
        print("\n■ 人手の方策（参考。正解ではない）")
        ref_stats = collect(ref, make_opponent(args.vs, seed=args.seed + 3),
                            games=args.games, num_envs=args.num_envs, seed=args.seed)
        print_buy(ref_stats)
        print_sell(ref_stats)

    if args.value:
        base, base_se, results = measure_value(
            policy, foe, sell_id, games=args.games, num_envs=args.num_envs, seed=args.seed
        )
        print_value(base, base_se, results)

    print(f"\n（{device} / {time.perf_counter() - started:.0f}秒）")


if __name__ == "__main__":
    main()
