"""「買う」「売る」の判断を、人が見て答えの割れない局面に絞って測る。

【なぜこの形なのか】

以前は「所持金がいくらのときに取引カードを何%選ぶか」を測り、人手の方策との
一致度で良し悪しを判断していました。これは誤りです。人手の方策は一つの妥当な
指し方であって最適方策ではなく、取引の開始判断だけを人手に合わせると勝率は
2.3pt 下がりました。

そこで2段構えにしています。

  1. 人が見て答えが割れない局面だけを取り出し、そこでの振る舞いを数える
  2. その振る舞いを「正しい方」へ**上書きして勝率がどれだけ変わるか**を測る

2 が無いと、見た目の悪い数字に引きずられます。実際「自分に売っている 42.4%」は
一見ひどいのですが、上書きすると勝率は **下がりました**（−1.0pt）。売ると相手に
カードが渡るので、無選別に相手へ売るのは良い札の献上になるためです。

【買う: 公開された1枚を買うか断るか】

`phase_handlers.cpp` の `step_phase_buy_select_mirror` / `step_phase_buy` より:

  1. A が「買う」を相手 B に使う
  2. B の手札から売れる札が **1枚ランダムに公開** され、A に見えるようになる
  3. A が受諾（ACTION_DEAL_YES）か辞退（ACTION_DEAL_NO）を選ぶ
  4. 受諾すると A は代金を B に払い、その札を受け取る

奇跡は30枚すべて値段0なので無料。5円未満の防具も、その値段で防御手段が確実に
1枚増えます。ここで断っていれば、値段や種別を見られていない証拠になります。

【売る: どの札を誰に売るか】

`combat_resolution.cpp` の `execute_sell_resolution` / `execute_money_deduction` より:

  1. 売り手が自分の手札から1枚選ぶ（PHASE_SELL_SELECT）
  2. 対象を選ぶ（自分 / 相手）
  3. **買い手に拒否権は無い**（スーパーミラーで反射する以外は確定）
  4. 支払いは **お金 → MP → HP** の順。足りなければ HP が直接削れる

売るは換金手段であると同時に武器です。相手の お金+MP が値段に届かないとき、
高額な札を売りつけると差額がそのまま HP ダメージになります。
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field

import numpy as np

import godfield_core
from godfield_rl import feature_config as fc
from godfield_rl.cards import all_cards, card_id, card_name, feature
from godfield_rl.evaluation import play_both_seats, split_observation

PHASE_BUY = int(godfield_core.GamePhase.PHASE_BUY)
PHASE_SELL_SELECT = int(godfield_core.GamePhase.PHASE_SELL_SELECT)
PHASE_TARGET_SELECT = int(godfield_core.GamePhase.PHASE_MAIN_TARGET_SELECT)
ACTION_DEAL_YES = int(godfield_core.ACTION_DEAL_YES)
ACTION_TARGET_OPP = int(godfield_core.ACTION_TARGET_OPP)
ACTION_TARGET_SELF = int(godfield_core.ACTION_TARGET_SELF)

# 観測のステータスは100で割って渡されている
STAT_SCALE = 100.0

# (ラベル, 判定, 期待する向き)
#
# 「明らかに買うべき」の2つだけが判定の対象です。それ以外は人でも割れるので
# 良し悪しを問いません（高額を断るのは正しいので、そこだけ逆向きの期待）。
BUY_BUCKETS = (
    ("奇跡（無料）", lambda t, p: t == "miracle", "買う"),
    ("防具 5円未満", lambda t, p: t == "defense" and p < 5, "買う"),
    ("防具 5円以上", lambda t, p: t == "defense" and p >= 5, "—"),
    ("武器", lambda t, p: t == "weapon", "—"),
    ("雑貨", lambda t, p: t == "sundry", "—"),
    ("高額 15円以上", lambda t, p: p >= 15, "断る"),
)


def price_of(card: int) -> int:
    return int(feature(card, "price", 0) or 0)


def sell_card_id() -> int:
    """「売る」のカードID。カードマスタの読み込みも兼ねます。"""
    all_cards()
    return card_id("売る")


@dataclass
class BuyDecision:
    card: int      # 公開された札
    money: int     # 買う側の所持金
    bought: bool

    @property
    def affordable(self) -> bool:
        return self.money >= price_of(self.card)


@dataclass
class SellDecision:
    picked: int          # 出品した札
    choices: list[int]   # 選べた札
    opp_money: int
    opp_mp: int

    @property
    def best_price(self) -> int:
        return max(price_of(c) for c in self.choices)

    @property
    def took_best(self) -> bool:
        return price_of(self.picked) == self.best_price

    @property
    def opponent_can_pay(self) -> int:
        return self.opp_money + self.opp_mp

    def damage(self, price: int) -> int:
        """相手が払いきれないぶんは HP から引かれる。"""
        return max(0, price - self.opponent_can_pay)


@dataclass
class TradeStats:
    buys: list[BuyDecision] = field(default_factory=list)
    sells: list[SellDecision] = field(default_factory=list)
    sold_to_self: list[bool] = field(default_factory=list)
    unreadable: int = 0

    def buy_rate(self, matches) -> tuple[int, float]:
        """条件に合い、かつ所持金が足りる局面での受諾率。"""
        rows = [
            b for b in self.buys
            if matches(feature(b.card, "type", ""), price_of(b.card)) and b.affordable
        ]
        if not rows:
            return 0, float("nan")
        return len(rows), sum(1 for b in rows if b.bought) / len(rows)


class TradeProbe:
    """方策をそのまま通しつつ、取引まわりの局面だけを記録する。"""

    def __init__(self, policy, sell_id: int):
        self.policy = policy
        self.sell_id = sell_id
        self.stats = TradeStats()

    def act(self, obs: np.ndarray, masks: np.ndarray) -> np.ndarray:
        actions = self.policy.act(obs, masks)
        view = _View(obs)

        for i in view.rows(PHASE_BUY):
            offered = view.offered_card(i)
            if offered is None:
                self.stats.unreadable += 1
                continue
            self.stats.buys.append(
                BuyDecision(offered, view.my_money(i), int(actions[i]) == ACTION_DEAL_YES)
            )

        for i in view.rows(PHASE_SELL_SELECT):
            a = int(actions[i])
            choices = view.sellable(i, masks[i])
            if len(choices) < 2 or not 0 <= a < fc.MAX_HAND_SIZE:
                continue  # 選択肢が1つなら判断ではない
            picked = view.hand(i)[a]
            if picked < 0:
                continue
            self.stats.sells.append(
                SellDecision(int(picked), choices, view.opp_money(i), view.opp_mp(i))
            )

        for i in view.rows(PHASE_TARGET_SELECT):
            if self.sell_id in view.staged(i):
                self.stats.sold_to_self.append(int(actions[i]) == ACTION_TARGET_SELF)

        return actions


class TradeOverride:
    """取引の判断だけを「明らかに正しい方」へ差し替える。

    学習し直さずに「直す価値」を勝率で測るために使います。
    """

    def __init__(self, policy, sell_id: int, *, buy_obvious: bool = False,
                 sell_to_opponent: bool = False, sell_highest: bool = False):
        self.policy = policy
        self.sell_id = sell_id
        self.buy_obvious = buy_obvious
        self.sell_to_opponent = sell_to_opponent
        self.sell_highest = sell_highest
        self.changed = 0

    def act(self, obs: np.ndarray, masks: np.ndarray) -> np.ndarray:
        actions = self.policy.act(obs, masks)
        view = _View(obs)

        if self.buy_obvious:
            for i in view.rows(PHASE_BUY):
                card = view.offered_card(i)
                if card is None or not masks[i][ACTION_DEAL_YES]:
                    continue
                kind, price = feature(card, "type", ""), price_of(card)
                obvious = kind == "miracle" or (kind == "defense" and price < 5)
                if obvious and view.my_money(i) >= price:
                    self._set(actions, i, ACTION_DEAL_YES)

        if self.sell_highest:
            for i in view.rows(PHASE_SELL_SELECT):
                hand = view.hand(i)
                slots = [s for s in range(fc.MAX_HAND_SIZE) if masks[i][s] and hand[s] >= 0]
                if len(slots) < 2:
                    continue
                self._set(actions, i, max(slots, key=lambda s: price_of(int(hand[s]))))

        if self.sell_to_opponent:
            for i in view.rows(PHASE_TARGET_SELECT):
                if self.sell_id in view.staged(i) and masks[i][ACTION_TARGET_OPP]:
                    self._set(actions, i, ACTION_TARGET_OPP)

        return actions

    def _set(self, actions: np.ndarray, i: int, action: int) -> None:
        if int(actions[i]) != action:
            self.changed += 1
        actions[i] = action


class _View:
    """観測から必要な部分だけを取り出す薄いラッパー。"""

    def __init__(self, obs: np.ndarray):
        self.obs = obs
        self.phases = np.argmax(obs[:, fc.PHASE_START : fc.PHASE_START + fc.PHASE_LEN], axis=1)

    def rows(self, phase: int) -> np.ndarray:
        return np.flatnonzero(self.phases == phase)

    def hand(self, i: int) -> np.ndarray:
        s = fc.HAND_CARDS_START
        return self.obs[i, s : s + fc.MAX_HAND_SIZE].astype(int)

    def staged(self, i: int) -> np.ndarray:
        s = fc.STAGED_CARDS_START
        return self.obs[i, s : s + fc.MAX_HAND_SIZE].astype(int)

    def offered_card(self, i: int) -> int | None:
        """買う局面で公開された札。売り手の仮置き場に入る。"""
        s = fc.OPP_STAGED_CARDS_START
        block = self.obs[i, s : s + fc.MAX_HAND_SIZE]
        visible = block[block >= 0]
        return int(visible[0]) if visible.size else None

    def sellable(self, i: int, mask: np.ndarray) -> list[int]:
        hand = self.hand(i)
        return [int(hand[s]) for s in range(fc.MAX_HAND_SIZE) if mask[s] and hand[s] >= 0]

    def my_money(self, i: int) -> int:
        return int(round(self.obs[i, fc.STAT_START + 4] * STAT_SCALE))

    def opp_mp(self, i: int) -> int:
        return int(round(self.obs[i, fc.STAT_START + 3] * STAT_SCALE))

    def opp_money(self, i: int) -> int:
        return int(round(self.obs[i, fc.STAT_START + 5] * STAT_SCALE))


def collect(policy, opponent, *, games: int, num_envs: int = 256, seed: int = 0) -> TradeStats:
    """席を入れ替えて2回戦わせ、取引の判断を集めます。"""
    all_cards()
    probe = TradeProbe(policy, sell_card_id())
    for a, b, s in ((probe, opponent, seed), (opponent, probe, seed + 1000)):
        pool = godfield_core.EnvPool(num_envs)
        pool.reset(s)
        players = {0: a, 1: b}
        finished = 0
        for _ in range(games * 2000):
            obs, masks = split_observation(pool.get_observations(), num_envs)
            actors = pool.get_current_actors()
            actions = np.zeros(num_envs, dtype=np.int32)
            for seat, pol in players.items():
                idx = np.flatnonzero(actors == seat)
                if idx.size:
                    actions[idx] = pol.act(obs[idx], masks[idx])
            pool.step_all(actions)
            finished += int(pool.get_dones().sum())
            if finished >= games:
                break
    return probe.stats


@dataclass(frozen=True)
class ValueResult:
    """上書きしたときの勝率と、基準との差。"""

    label: str
    win_rate: float
    stderr: float
    delta: float
    delta_stderr: float
    changed: int

    @property
    def significant(self) -> bool:
        return abs(self.delta) > 2 * self.delta_stderr


def measure_value(policy, opponent, sell_id: int, *, games: int, num_envs: int = 256,
                  seed: int = 0) -> tuple[float, float, list[ValueResult]]:
    """判断を直したときに勝率がどれだけ変わるかを測ります。

    学習し直さずに「直す価値」が分かります。上書きの回数も返すので、
    「わずかな回数で大きく動く＝1回あたりの価値が高い」判断を見分けられます。
    """
    def play(pol):
        fwd, rev, wr = play_both_seats(pol, opponent, games=games, num_envs=num_envs, seed=seed)
        n = fwd.games + rev.games
        return wr, math.sqrt(wr * (1 - wr) / n) * 100

    base, base_se = play(policy)

    results = []
    for label, kwargs in (
        ("無料の奇跡・安い防具を必ず買う", dict(buy_obvious=True)),
        ("売る対象を必ず相手にする", dict(sell_to_opponent=True)),
        ("出品は必ず最高額の札にする", dict(sell_highest=True)),
        ("売るの2つを両方", dict(sell_to_opponent=True, sell_highest=True)),
        ("取引3つとも", dict(buy_obvious=True, sell_to_opponent=True, sell_highest=True)),
    ):
        override = TradeOverride(policy, sell_id, **kwargs)
        wr, se = play(override)
        results.append(ValueResult(
            label, wr, se, (wr - base) * 100,
            math.sqrt(base_se ** 2 + se ** 2), override.changed,
        ))
    return base, base_se, results


def top_cards(cards, n: int = 2) -> str:
    return " / ".join(name for name, _ in Counter(card_name(c) for c in cards).most_common(n))
