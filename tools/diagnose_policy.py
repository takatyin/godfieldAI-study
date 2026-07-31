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
from godfield_rl.opponents import OPPONENT_KINDS, make_opponent  # noqa: E402

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

# 相手向き。自分に使うと、自分の展開済み奇跡や手札を捨てることになる。
# 買うは相手から買うと相手の手札を1枚削れるぶん有利。
#
# 「売る」はここに入れない。何を売るかで正解が変わるため（自分に不要で高価な
# ものを相手に売れば有利だが、自分にも重要なものや安いものを売るのは明確な損）。
# 一律に「相手が正解」として測ると、正しい手まで誤りに数えてしまう。
OPPONENT_ONLY_CARD_NAMES = (
    "女神の石けん", "夜空のホウキ", "買う",
)

# 「そのカードが効く局面か」の判定に使う観測の位置。
SICKNESS_COLD, SICKNESS_FEVER = 1, 2          # 0 は「病なし」
CURSE_FOG, CURSE_FLASH = 0, 1                 # 霧, 閃光（multi-hot）

# カードごとに、効く条件が違う。全体の平均だけを見ると
# 「どちらに使っても何も起きない局面」に薄められて、肝心の
# 「効く局面でどちらを選んでいるか」が見えなくなる。
#
# 夜空のホウキ（神器を捨てる）と女神の石けん（習得済み奇跡を捨てる）は、
# 神器の展開状況も習得済み奇跡も観測に入っていないため判定できない（types.h の
# Observation を参照）。ここに載せられないこと自体が結果の読み方に効く。
RELEVANCE_KIND_BY_CARD = {
    "スマイルの貝がら": "smile_shell",   # 風邪・熱病・霧・閃光を払う
    "ハートの貝がら": "heart_shell",     # 全ての災いを払う
    "スマイルのしずく": "hp", "ハートのしずく": "hp",
    "ロマンスウォーター": "hp", "天の川のおいしい水": "hp",
    "スマイルの花": "mp", "ハートの花": "mp", "ロマンスの香木": "mp",
}

# 効く局面かどうかで分けたときの内訳。相手側は霧だと観測が 0 埋めされるので、
# 判定できない分を別に数えて、勝手に「効かない」に混ぜないようにする。
BUCKET_SELF, BUCKET_OPP_ONLY, BUCKET_NEITHER, BUCKET_FOGGED, BUCKET_UNKNOWN = 0, 1, 2, 3, 4
BUCKET_LABELS = ("自分に効く", "相手だけに効く", "どちらにも効かない")


def _relevance(obs: np.ndarray) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """種類ごとに (自分に効くか, 相手に効くか) の真偽値を作ります。"""
    ns, nc = fc.NUM_SICKNESS_TYPES, fc.NUM_CURSE_TYPES
    s, c = fc.SICKNESS_START, fc.CURSES_START
    sick = (obs[:, s : s + ns], obs[:, s + ns : s + 2 * ns])
    curse = (obs[:, c : c + nc], obs[:, c + nc : c + 2 * nc])
    stat = obs[:, fc.STAT_START : fc.STAT_START + fc.STAT_LEN]

    def smile_shell(i):
        return (sick[i][:, [SICKNESS_COLD, SICKNESS_FEVER]].max(axis=1) > 0.5) | (
            curse[i][:, [CURSE_FOG, CURSE_FLASH]].max(axis=1) > 0.5
        )

    def heart_shell(i):
        return (sick[i][:, 1:].max(axis=1) > 0.5) | (curse[i].max(axis=1) > 0.5)

    # 上限に張り付いていなければ回復・補充の余地がある
    return {
        "smile_shell": (smile_shell(0), smile_shell(1)),
        "heart_shell": (heart_shell(0), heart_shell(1)),
        "hp": (stat[:, 0] < 1.0, stat[:, 1] < 1.0),
        "mp": (stat[:, 2] < 1.0, stat[:, 3] < 1.0),
    }


KIND_BY_CARD_ID = {
    c["id"]: RELEVANCE_KIND_BY_CARD[c["name"]]
    for c in CARDS
    if c["name"] in RELEVANCE_KIND_BY_CARD
}


# 上書き実験の一覧。まとめて上書きすると遭遇数の多いカードに埋もれて個々の効果が
# 打ち消し合うので、カード単位でも測る（実際、相手向きをまとめると +0.3% だが、
# 女神の石けん単独では +1.6% だった）。
FOCUS: dict[str, tuple[tuple[str, ...], str]] = {
    "自分向き まとめて": (SELF_ONLY_CARD_NAMES, "self"),
    "相手向き まとめて": (OPPONENT_ONLY_CARD_NAMES, "opp"),
    **{name: ((name,), "opp") for name in OPPONENT_ONLY_CARD_NAMES},
    **{name: ((name,), "self") for name in ("スマイルの貝がら", "ハートの貝がら", "スマイルの花")},
}


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


def _focus_spec(names: tuple[str, ...], direction: str):
    right, wrong = (
        (ACTION_TARGET_SELF, ACTION_TARGET_OPP) if direction == "self"
        else (ACTION_TARGET_OPP, ACTION_TARGET_SELF)
    )
    return _card_ids(names), right, wrong


def run(learner, *, num_envs: int, steps: int, seed: int, opponent: str = "strategic",
        focus: dict[str, tuple[tuple[str, ...], str]] | None = None,
        apply: str | None = None):
    """1回まわして、対象選択の統計・エピソード長・勝敗を集めます。

    focus には「対象を間違えたら数えたいカード群」を名前つきで渡します。渡した
    ぶんだけ、間違いが起きた局を別に記録します。apply にその名前を渡すと、
    数えるだけでなく実際に正しい側へ上書きします。学習し直さずに「直す価値」を
    測るための実験です。

    全局の勝率差だけを見ると、出番の少ないカードほど効果が薄まって測定限界に
    埋もれます（夜空のホウキは全体の 2.6% の局にしか出ない）。間違いが起きた局
    だけを取り出して比べれば、そこは薄まりません。上書きの有無で局の選び方が
    変わらないよう、apply しない実行でも同じ条件で局を拾っています。

    相手は既定で strategic。heuristic は対象選択が常に「相手」で固定という
    強い偏りがあり、勝率が9割を超えてしまって指標にならない（上振れも下振れも
    飽和して見えない）。上書き実験の差もそこで潰れる。
    """
    focus = focus or {}
    specs = {label: _focus_spec(*args) for label, args in focus.items()}
    env = GodFieldVectorEnv(num_envs, opponent=make_opponent(opponent, seed=seed + 1))
    env.seed(seed)
    obs = env.reset()

    per_card: dict[int, list[int]] = defaultdict(lambda: [0, 0])  # id -> [遭遇, 相手を選んだ]
    prob_to_opp: dict[int, list[float]] = defaultdict(list)
    # id -> 局面の種類ごとの [遭遇, 相手を選んだ]
    per_bucket: dict[int, list[list[int]]] = defaultdict(lambda: [[0, 0] for _ in range(5)])
    ep_steps = np.zeros(num_envs, dtype=np.int64)
    lengths: list[int] = []
    results: list[float] = []
    # 間違いが起きた局かどうかを focus ごとに追う。効果はその局にしか出ない以上、
    # 全局の勝率差は出番の少なさで薄まる。該当局だけを取り出せば薄まらない。
    flagged = {label: np.zeros(num_envs, dtype=bool) for label in specs}
    hits = dict.fromkeys(specs, 0)
    flagged_results: dict[str, list[float]] = {label: [] for label in specs}

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
            relevance = _relevance(obs[idx])
            fogged = obs[idx, fc.CURSES_START + CURSE_FOG] > 0.5
            for j, (card_id, opp, p) in enumerate(
                zip(staged, chose_opp, probs[idx, ACTION_TARGET_OPP])
            ):
                card_id = int(card_id)
                per_card[card_id][0] += 1
                per_card[card_id][1] += int(opp)
                prob_to_opp[card_id].append(float(p))

                kind = KIND_BY_CARD_ID.get(card_id)
                if kind is None:
                    bucket = BUCKET_UNKNOWN
                elif relevance[kind][0][j]:
                    bucket = BUCKET_SELF
                elif fogged[j]:
                    # 霧だと相手の状態が観測に入らないので、効くかどうか判定できない
                    bucket = BUCKET_FOGGED
                else:
                    bucket = BUCKET_OPP_ONLY if relevance[kind][1][j] else BUCKET_NEITHER
                per_bucket[card_id][bucket][0] += 1
                per_bucket[card_id][bucket][1] += int(opp)

        if specs:
            staged_all = obs[:, fc.STAGED_CARDS_START].astype(int)
            in_phase = obs[:, fc.PHASE_START + PHASE_TARGET_SELECT] > 0.5
            for label, (card_ids, right, wrong) in specs.items():
                bad = (
                    in_phase
                    & np.isin(staged_all, list(card_ids))
                    & masks[:, right]
                    & (actions == wrong)
                )
                hits[label] += int(bad.sum())
                flagged[label] |= bad
                if label == apply:
                    actions = np.where(bad, right, actions)

        obs, rewards, dones, _ = env.step(actions)
        ep_steps += 1
        for i in np.flatnonzero(dones):
            lengths.append(int(ep_steps[i]))
            results.append(float(rewards[i]))
            ep_steps[i] = 0
            for label in specs:
                if flagged[label][i]:
                    flagged_results[label].append(float(rewards[i]))
                    flagged[label][i] = False

    env.close()
    return {
        "per_card": per_card,
        "per_bucket": per_bucket,
        "prob_to_opp": prob_to_opp,
        "lengths": np.array(lengths),
        "results": np.array(results),
        "hits": hits,
        "flagged_results": {k: np.array(v) for k, v in flagged_results.items()},
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


def _print_by_relevance(stats) -> None:
    """効く局面かどうかで分けて、対象選択を見ます。

    全体の平均だけでは「どちらに使っても何も起きない局面」に薄められてしまい、
    肝心の「効く局面で自分を選べているか」が判定できません。
    """
    per_bucket = stats["per_bucket"]
    print("\n■ そのカードが効く局面かどうかで分けた「相手を選んだ」割合")
    print("  （災いを払う貝がらは自分に災いが無ければ、どちらに使っても何も起きない）")
    header = "".join(f"{label:>18}" for label in BUCKET_LABELS)
    print(f"\n  {'カード':<20}{header}")

    fogged_total = 0
    for card_id, buckets in sorted(per_bucket.items(), key=lambda kv: -sum(b[0] for b in kv[1])):
        if card_id not in KIND_BY_CARD_ID:
            continue
        fogged_total += buckets[BUCKET_FOGGED][0]
        cells = ""
        for bucket in (BUCKET_SELF, BUCKET_OPP_ONLY, BUCKET_NEITHER):
            n, opp = buckets[bucket]
            cells += f"{f'{opp / n:.1%} ({n})':>18}" if n else f"{'-':>18}"
        print(f"  {CARD_BY_ID[card_id]['name']:<20}{cells}")

    if fogged_total:
        print(f"\n  ＊ 自分が霧のため相手の状態を判定できず除外: {fogged_total} 回")
    unknown = sorted(
        (CARD_BY_ID[cid]["name"] for cid, b in per_bucket.items()
         if cid not in KIND_BY_CARD_ID and b[BUCKET_UNKNOWN][0] >= 100),
    )
    if unknown:
        print(f"  ＊ 効く条件が観測に無く判定できないカード: {'、'.join(unknown)}")


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
    parser.add_argument("--opponent", choices=list(OPPONENT_KINDS), default="strategic",
                        help="対戦相手。heuristic は弱すぎて勝率が飽和し指標にならない")
    parser.add_argument("--device", default=None, help="既定はGPUがあればcuda")
    parser.add_argument("--amp", action="store_true",
                        help="推論をbfloat16で行う（CUDAのみ・さらに高速）")
    args = parser.parse_args()

    device = args.device or default_device()
    learner = load_learner(args.model_path, device=device, amp=args.amp)
    common = dict(num_envs=args.num_envs, steps=args.steps, seed=args.seed,
                  opponent=args.opponent, focus=FOCUS)

    started = time.perf_counter()
    base = run(learner, apply=None, **common)
    _print_target_select(base)
    _print_by_relevance(base)
    _print_episodes(base)

    def rate(results) -> tuple[float, int]:
        return ((results > 0).mean(), results.size) if results.size else (float("nan"), 0)

    def se(p1, n1, p2, n2) -> float:
        return float(np.sqrt(p1 * (1 - p1) / max(n1, 1) + p2 * (1 - p2) / max(n2, 1)))

    base_wr, base_n = rate(base["results"])

    print("\n■ 対象の間違いを直したときの勝率の変化")
    print("  ＊ ±は標準誤差。差がこれに埋もれているときは「効果が無い」のではなく")
    print("     「この試行数では測れていない」。")
    print("  ＊ 全局の差は出番の少なさで薄まる。夜空のホウキは全体の数%の局にしか")
    print("     出ないので、間違いが起きた局だけを取り出した右側のほうが感度が高い。")
    print(f"\n  {'直した対象':<20}{'回数':>7}{'全局の差':>14}"
          f"{'該当局':>8}{'該当局の勝率':>15}{'差':>15}")

    for label, spec in FOCUS.items():
        fixed = run(learner, apply=label, **common)
        fixed_wr, fixed_n = rate(fixed["results"])
        # 該当局＝そのカードで対象を間違えた局。上書きの有無で選び方が変わらない
        before, before_n = rate(base["flagged_results"][label])
        after, after_n = rate(fixed["flagged_results"][label])
        print(
            f"  {label:<20}{fixed['hits'][label]:>7}"
            f"{f'{fixed_wr - base_wr:+.1%} ± {se(base_wr, base_n, fixed_wr, fixed_n):.1%}':>14}"
            f"{before_n:>8}{f'{before:.1%} -> {after:.1%}':>15}"
            f"{f'{after - before:+.1%} ± {se(before, before_n, after, after_n):.1%}':>15}"
        )

    print(f"\n  上書きなしの全局勝率: {base_wr:.1%}（{base_n} 局）")
    print(f"\n（対 {args.opponent} / {device} / {args.num_envs}環境 x {args.steps}ステップ"
          f" x {len(FOCUS) + 1}回{' / bf16' if args.amp else ''}"
          f" / {time.perf_counter() - started:.1f}秒）")


if __name__ == "__main__":
    main()
