"""学習済み方策の「どこで間違えているか」を測るための共通処理。

勝率だけを見ていると、方策が特定の局面で潰れていても気付けません。実際、
gen50 の Transformer / MLP はどちらも対象選択フェイズで **100%「相手」を選ぶ**まで
潰れており、回復系の雑貨を相手に使っていました（勝率は 85% 出ていた）。

以前この一式は `tools/diagnose_policy.py` に住んでいて、他のツールが
`sys.path` 頼みで import していました。スクリプトを import するのは壊れやすく、
共有したいのはツールではなく測り方なので、ここに置いています。
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np

import godfield_core
from godfield_rl import feature_config as fc
from godfield_rl.cards import all_cards, card_id
from godfield_rl.env_wrapper import GodFieldVectorEnv
from godfield_rl.opponents import make_opponent

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
    "スマイルのしずく",
    "ハートのしずく",
    "ロマンスウォーター",
    "天の川のおいしい水",
    "スマイルの花",
    "ハートの花",
    "ロマンスの香木",
    "スマイルの貝がら",
    "ハートの貝がら",
    "守護封印のつぼ",
)

# 相手向き。自分に使うと、自分の展開済み奇跡や手札を捨てることになる。
# 買うは相手から買うと相手の手札を1枚削れるぶん有利。
#
# 「売る」はここに入れない。何を売るかで正解が変わるため（自分に不要で高価な
# ものを相手に売れば有利だが、自分にも重要なものや安いものを売るのは明確な損）。
# 一律に「相手が正解」として測ると、正しい手まで誤りに数えてしまう。
OPPONENT_ONLY_CARD_NAMES = (
    "女神の石けん",
    "夜空のホウキ",
    "買う",
)

# 「そのカードが効く局面か」の判定に使う観測の位置。
SICKNESS_COLD, SICKNESS_FEVER = 1, 2  # 0 は「病なし」
CURSE_FOG, CURSE_FLASH = 0, 1  # 霧, 閃光（multi-hot）

# カードごとに、効く条件が違う。全体の平均だけを見ると
# 「どちらに使っても何も起きない局面」に薄められて、肝心の
# 「効く局面でどちらを選んでいるか」が見えなくなる。
RELEVANCE_KIND_BY_CARD = {
    "スマイルの貝がら": "smile_shell",  # 風邪・熱病・霧・閃光を払う
    "ハートの貝がら": "heart_shell",  # 全ての災いを払う
    "スマイルのしずく": "hp",
    "ハートのしずく": "hp",
    "ロマンスウォーター": "hp",
    "天の川のおいしい水": "hp",
    "スマイルの花": "mp",
    "ハートの花": "mp",
    "ロマンスの香木": "mp",
}

# 効く局面かどうかで分けたときの内訳。相手側は霧だと観測が 0 埋めされるので、
# 判定できない分を別に数えて、勝手に「効かない」に混ぜないようにする。
BUCKET_SELF, BUCKET_OPP_ONLY, BUCKET_NEITHER, BUCKET_FOGGED, BUCKET_UNKNOWN = 0, 1, 2, 3, 4
BUCKET_LABELS = ("自分に効く", "相手だけに効く", "どちらにも効かない")
NUM_BUCKETS = 5

# 上書き実験の一覧。まとめて上書きすると遭遇数の多いカードに埋もれて個々の効果が
# 打ち消し合うので、カード単位でも測る（実際、相手向きをまとめると +0.3% だが、
# 女神の石けん単独では +1.6% だった）。
FOCUS: dict[str, tuple[tuple[str, ...], str]] = {
    "自分向き まとめて": (SELF_ONLY_CARD_NAMES, "self"),
    "相手向き まとめて": (OPPONENT_ONLY_CARD_NAMES, "opp"),
    **{name: ((name,), "opp") for name in OPPONENT_ONLY_CARD_NAMES},
    **{name: ((name,), "self") for name in ("スマイルの貝がら", "ハートの貝がら", "スマイルの花")},
}


def kind_by_card_id() -> dict[int, str]:
    """カードID -> 効く条件の種類。判定できないカードは入りません。"""
    return {card_id(name): kind for name, kind in RELEVANCE_KIND_BY_CARD.items()}


def _card_ids(names: tuple[str, ...]) -> set[int]:
    return {card_id(n) for n in names}


def relevance(obs: np.ndarray) -> dict[str, tuple[np.ndarray, np.ndarray]]:
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


def target_select_rows(obs: np.ndarray, masks: np.ndarray) -> np.ndarray:
    """対象選択フェイズで、自分・相手の両方を選べる環境の添字。"""
    in_phase = obs[:, fc.PHASE_START + PHASE_TARGET_SELECT] > 0.5
    both = masks[:, ACTION_TARGET_OPP] & masks[:, ACTION_TARGET_SELF]
    return np.flatnonzero(in_phase & both)


def _focus_spec(names: tuple[str, ...], direction: str):
    right, wrong = (
        (ACTION_TARGET_SELF, ACTION_TARGET_OPP) if direction == "self" else (ACTION_TARGET_OPP, ACTION_TARGET_SELF)
    )
    return _card_ids(names), right, wrong


def run(
    learner,
    *,
    num_envs: int,
    steps: int,
    seed: int,
    opponent: str = "strategic",
    focus: dict[str, tuple[tuple[str, ...], str]] | None = None,
    apply: str | None = None,
) -> dict:
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
    all_cards()
    kind_by_id = kind_by_card_id()
    specs = {label: _focus_spec(*args) for label, args in (focus or {}).items()}
    env = GodFieldVectorEnv(num_envs, opponent=make_opponent(opponent, seed=seed + 1))
    env.seed(seed)
    obs = env.reset()

    per_card: dict[int, list[int]] = defaultdict(lambda: [0, 0])  # id -> [遭遇, 相手を選んだ]
    prob_to_opp: dict[int, list[float]] = defaultdict(list)
    # id -> 局面の種類ごとの [遭遇, 相手を選んだ]
    per_bucket: dict[int, list[list[int]]] = defaultdict(lambda: [[0, 0] for _ in range(NUM_BUCKETS)])
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
        idx = target_select_rows(obs, masks)

        # 行動と確率は同じ分布から取れるので、順伝播は1回で済ませる（以前は
        # predict と get_distribution で2回まわしていた）。deterministic な行動は
        # 確率の argmax と同じもの。
        probs = learner.action_probs(obs, masks)
        actions = probs.argmax(axis=1).astype(np.int32)

        if idx.size:
            staged = obs[idx, fc.STAGED_CARDS_START].astype(int)
            chose_opp = actions[idx] == ACTION_TARGET_OPP
            rel = relevance(obs[idx])
            fogged = obs[idx, fc.CURSES_START + CURSE_FOG] > 0.5
            for j, (cid, opp, p) in enumerate(zip(staged, chose_opp, probs[idx, ACTION_TARGET_OPP])):
                cid = int(cid)
                per_card[cid][0] += 1
                per_card[cid][1] += int(opp)
                prob_to_opp[cid].append(float(p))

                kind = kind_by_id.get(cid)
                if kind is None:
                    bucket = BUCKET_UNKNOWN
                elif rel[kind][0][j]:
                    bucket = BUCKET_SELF
                elif fogged[j]:
                    # 霧だと相手の状態が観測に入らないので、効くかどうか判定できない
                    bucket = BUCKET_FOGGED
                else:
                    bucket = BUCKET_OPP_ONLY if rel[kind][1][j] else BUCKET_NEITHER
                per_bucket[cid][bucket][0] += 1
                per_bucket[cid][bucket][1] += int(opp)

        if specs:
            staged_all = obs[:, fc.STAGED_CARDS_START].astype(int)
            in_phase = obs[:, fc.PHASE_START + PHASE_TARGET_SELECT] > 0.5
            for label, (card_ids_, right, wrong) in specs.items():
                bad = in_phase & np.isin(staged_all, list(card_ids_)) & masks[:, right] & (actions == wrong)
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
