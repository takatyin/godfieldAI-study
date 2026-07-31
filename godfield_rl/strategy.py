"""人手で書いた戦略にもとづく相手方策（StrategicOpponent）。

既存の `HeuristicOpponent` は「決定系の行動を優先し、あとは手札からランダム」という
だけのもので、対象選択で常に「相手」を選ぶ偏りがありました。回復系の雑貨を相手に
使うため、これを初期対戦相手にした学習者も同じ間違いを覚えます
（実測: 対象選択の100%で「相手」を選ぶまで潰れていた）。

こちらは指定された戦略をそのまま実装したものです。学習の初期対戦相手と、
強さの基準に使います。

## 戦略

- **強い奇跡**は手札にあってMPが足りるなら積極的に使う（展開済みでも撃ち続ける）
- **買う**は所持金10以上なら優先。買えるなら買う
- **両替**はHPが20未満になったら使う。配分は下の `exchange_allocation` を参照
- **武器**はプラスがあるだけ重ねてから撃つ
- **防具**は被弾量を超えない範囲でいちばん近くなる組み合わせ。守1・2から先に使う
- **雑貨**は女神の石けん・夜空のホウキだけ相手に、それ以外は自分に使う
- **売る**は値段15以上の神器だけ相手に売る

## ランダム性

決定ごとに `explore_rate`（既定20%）でルールを外し、合法手から一様に選びます。
完全に決定的だと学習者が1つの相手に過適合するのと、リーグの初期メンバーとして
多様性が無いためです。

## 展開済みの奇跡について

この実装では、使った奇跡はクリーンアップで「展開」され、**カードは手札スロットに
残ったまま再使用できます**（実測で確認済み）。したがって「未展開なら使う／展開済み
でも連打」はどちらも同じ行動になり、展開状態で分岐する必要はありません。
"""

from __future__ import annotations

import numpy as np

import godfield_core
from godfield_rl import feature_config as fc
from godfield_rl.cards import card_id, card_ids, feature

# ---------------------------------------------------------------------------
# 戦略で名指しするカード。名前は assets/godfield_cards.json の表記に合わせること
# （存在しない名前を書くと card_id が例外を投げる）。
# ---------------------------------------------------------------------------

# 相手に撃つ強い攻撃奇跡
STRONG_ATTACK_MIRACLES = card_ids("＜氷＞", "＜闇＞", "＜大木＞", "＜岩＞", "＜炎＞", "＜吸収＞", "＜滝＞")
# 攻撃に重ねる強いプラス奇跡
STRONG_PLUS_MIRACLES = card_ids("＜火の玉＞", "＜流星＞", "＜オーラ＞", "＜蜃気楼＞")
# 自分に撃つ強い奇跡
STRONG_SELF_MIRACLES = card_ids("＜泉＞", "＜財宝＞")
# 相手に使う雑貨（これ以外の雑貨は自分に使う）
OPPONENT_SUNDRIES = card_ids("女神の石けん", "夜空のホウキ")

STRONG_MIRACLES = STRONG_ATTACK_MIRACLES | STRONG_PLUS_MIRACLES | STRONG_SELF_MIRACLES

ID_EXCHANGE = card_id("両替")
ID_SELL = card_id("売る")
ID_BUY = card_id("買う")
ID_SMILE_SHELL = card_id("スマイルの貝がら")

# しきい値
BUY_MIN_MONEY = 10      # 所持金がこれ以上なら「買う」を優先
EXCHANGE_HP_THRESHOLD = 20   # HPがこれ未満になったら「両替」を使う
SELL_MIN_PRICE = 15     # 値段がこれ以上の神器だけ相手に売る
CHEAP_ARMOR_DEF = 2     # 守がこれ以下の防具は優先的に消費する
BUY_MAX_PRICE = 10      # 提示されたカードがこの値段以内なら必ず買う
DISCARD_HAND_SIZE = 17  # 手札がこれを超えたら「捨てる」を選ぶ

# 手札に何枚まで残すか。これを超えたぶんが捨てる候補になる。
# 両替は2枚、取引カードと安い貝がらは1枚あれば足りる。
DISCARD_KEEP_LIMITS = {
    ID_EXCHANGE: 2,
    ID_BUY: 1,
    ID_SELL: 1,
    ID_SMILE_SHELL: 1,
}

A = godfield_core.ActionType
ACTION_TARGET_OPP = int(A.ACTION_TARGET_OPP)
ACTION_TARGET_SELF = int(A.ACTION_TARGET_SELF)
ACTION_CONFIRM = int(A.ACTION_CONFIRM)
ACTION_PRAY = int(A.ACTION_PRAY)
ACTION_DISCARD = int(A.ACTION_DISCARD)
ACTION_HAND_0 = int(A.ACTION_SELECT_HAND_0)
ACTION_NUM_0 = int(A.ACTION_NUM_0)

P = godfield_core.GamePhase
PHASE_MAIN = int(P.PHASE_MAIN)
PHASE_TARGET_SELECT = int(P.PHASE_MAIN_TARGET_SELECT)
PHASE_ATTACK_PLUS = int(P.PHASE_ATTACK_PLUS)
PHASE_MIRACLE_PLUS = int(P.PHASE_MIRACLE_PLUS)
PHASE_GROUP_WEAPON = int(P.PHASE_GROUP_WEAPON)
PHASE_GROUP_MIRACLE = int(P.PHASE_GROUP_MIRACLE_PLUS)
PHASE_DEFENSE = int(P.PHASE_DEFENSE)
PHASE_MIRACLE_DEFENSE = int(P.PHASE_MIRACLE_DEFENSE)
PHASE_EXCHANGE_HP = int(P.PHASE_EXCHANGE_HP)
PHASE_EXCHANGE_MP = int(P.PHASE_EXCHANGE_MP)
PHASE_BUY = int(P.PHASE_BUY)
PHASE_SELL_SELECT = int(P.PHASE_SELL_SELECT)
PHASE_DISCARD = int(P.PHASE_DISCARD)

ACTION_DEAL_YES = int(A.ACTION_DEAL_YES)
ACTION_DEAL_NO = int(A.ACTION_DEAL_NO)

STAT_SCALE = 100.0  # 観測は HP/MP/お金 を /100 で正規化している
MAX_STAT = 99       # HP / MP / お金 の上限


def exchange_allocation(total: int) -> tuple[int, int, int]:
    """両替の配分 (HP, MP, お金) を返します。合計は必ず保存されます。

    合計40以下なら全部HP。それを超えたぶんは MP に15まで、次にお金に10まで、
    さらに余ったらHPへ戻します。HPを先に確保するのは、両替を使うのが
    「HPが20を切ったとき」だからです（MPを先に取るとHPが減って本末転倒になる）。

        合計50 -> HP40 / MP10 / 金 0
        合計60 -> HP40 / MP15 / 金 5
        合計70 -> HP45 / MP15 / 金10
        合計80 -> HP55 / MP15 / 金10

    各ステータスの上限は99です。HPに戻しきれないぶんは MP -> お金 の順に
    こぼします（上限を無視して切り捨てると合計が保存されず、両替で資源が
    消えてしまう）。
    """
    total = int(np.clip(total, 0, 3 * MAX_STAT))
    if total <= 40:
        return total, 0, 0

    rest = total - 40
    mp = min(15, rest)
    rest -= mp
    money = min(10, rest)
    rest -= money

    hp = 40 + rest                      # 余りはHPへ戻す
    # 上限を超えたぶんを MP -> お金 の順にこぼす
    overflow = max(0, hp - MAX_STAT)
    hp -= overflow
    add_mp = min(overflow, MAX_STAT - mp)
    mp += add_mp
    money += overflow - add_mp
    return hp, mp, money


class StrategicOpponent:
    """人手の戦略で指す相手。

    Args:
        seed: 乱数の種。
        explore_rate: 決定ごとにルールを外して合法手から選ぶ確率。
    """

    def __init__(self, seed: int = 0, explore_rate: float = 0.2):
        self._rng = np.random.default_rng(seed)
        self.explore_rate = explore_rate

    # -- 補助 ---------------------------------------------------------------

    def _random_legal(self, masks: np.ndarray) -> np.ndarray:
        return np.argmax(self._rng.random(masks.shape) * masks, axis=1).astype(np.int32)

    @staticmethod
    def _phase(obs_row: np.ndarray) -> int:
        onehot = obs_row[fc.PHASE_START : fc.PHASE_START + fc.PHASE_LEN]
        return int(np.argmax(onehot))

    @staticmethod
    def _hand(obs_row: np.ndarray) -> np.ndarray:
        return obs_row[fc.HAND_CARDS_START : fc.HAND_CARDS_START + fc.MAX_HAND_SIZE].astype(int)

    @staticmethod
    def _stats(obs_row: np.ndarray) -> tuple[int, int, int]:
        """(HP, MP, お金)。観測は /100 で正規化されている。"""
        s = obs_row[fc.STAT_START : fc.STAT_START + 6] * STAT_SCALE
        return int(round(s[0])), int(round(s[2])), int(round(s[4]))

    @staticmethod
    def _staged(obs_row: np.ndarray) -> np.ndarray:
        s = obs_row[fc.STAGED_CARDS_START : fc.STAGED_CARDS_START + fc.MAX_HAND_SIZE].astype(int)
        return s[s >= 0]

    @staticmethod
    def _incoming_damage(obs_row: np.ndarray) -> int:
        """被弾しようとしている攻撃力。MISC ブロックの先頭。"""
        return int(round(obs_row[fc.MISC_START] * STAT_SCALE))

    def _hand_choices(self, mask_row: np.ndarray, hand: np.ndarray) -> list[int]:
        """選べる手札スロットのうち、カードが入っているもの。"""
        return [
            i for i in range(fc.MAX_HAND_SIZE)
            if mask_row[ACTION_HAND_0 + i] and hand[i] >= 0
        ]

    def _pick(self, slots: list[int]) -> int:
        return ACTION_HAND_0 + int(self._rng.choice(slots))

    # -- フェイズごとの方針 --------------------------------------------------

    def _act_main(self, obs_row, mask_row) -> int | None:
        hand = self._hand(obs_row)
        hp, mp, money = self._stats(obs_row)
        slots = self._hand_choices(mask_row, hand)
        if not slots:
            return None

        def slots_of(ids) -> list[int]:
            return [i for i in slots if hand[i] in ids]

        # 0. 手札が溢れそうなら捨てる。枚数は観測に無いので手札配列から数える
        #    （相手の枚数は観測に入らないが、自分の空きスロットは -1 で分かる）。
        if int(np.sum(hand >= 0)) > DISCARD_HAND_SIZE and mask_row[ACTION_DISCARD]:
            return ACTION_DISCARD

        # 1. HPが低いなら両替
        if hp < EXCHANGE_HP_THRESHOLD:
            picks = [i for i in slots if hand[i] == ID_EXCHANGE]
            if picks:
                return self._pick(picks)

        # 2. お金があるなら買う
        if money >= BUY_MIN_MONEY:
            picks = [i for i in slots if hand[i] == ID_BUY]
            if picks:
                return self._pick(picks)

        # 3. 強い攻撃奇跡（MPが足りるもの）
        picks = [i for i in slots_of(STRONG_ATTACK_MIRACLES) if feature(hand[i], "mp_cost") <= mp]
        if picks:
            return self._pick(picks)

        # 4. 強い自分向け奇跡
        picks = [i for i in slots_of(STRONG_SELF_MIRACLES) if feature(hand[i], "mp_cost") <= mp]
        if picks:
            return self._pick(picks)

        # 5. 値段の高い神器を売る
        picks = [
            i for i in slots
            if hand[i] == ID_SELL and self._has_expensive_item(hand, slots)
        ]
        if picks:
            return self._pick(picks)

        # 6. 武器を使う（プラスは攻撃フェイズで重ねる）
        picks = [i for i in slots if feature(hand[i], "type") == "weapon"]
        if picks:
            return self._pick(picks)

        # 7. 雑貨を使う
        picks = [i for i in slots if feature(hand[i], "type") == "sundry"]
        if picks:
            return self._pick(picks)

        return self._pick(slots)

    @staticmethod
    def _has_expensive_item(hand: np.ndarray, slots: list[int]) -> bool:
        return any(
            feature(hand[i], "price") >= SELL_MIN_PRICE
            for i in range(fc.MAX_HAND_SIZE)
            if hand[i] >= 0 and hand[i] not in (ID_SELL, ID_BUY, ID_EXCHANGE)
        )

    # -- 取引と廃棄 ----------------------------------------------------------
    #
    # ここに方針が無いと act() の既定（ランダムな合法手）がそのまま採用される。
    # 実測では取引と廃棄で判断の 8.9% がランダムに落ちており、無料のカードを
    # 半々でしか買わない・防具を捨てる、といった手を教えてしまっていた。

    def _act_buy(self, obs_row, mask_row) -> int | None:
        """提示されたカードを買うか断るか。

        奇跡と防具は必ず買い、それ以外も10円以内なら買う。手札が満杯でも買う
        （満杯だと自分のカードが1枚ランダムに置き換わるが、相手の手札を1枚
        減らせるほうが大きい）。
        """
        if not (mask_row[ACTION_DEAL_YES] and mask_row[ACTION_DEAL_NO]):
            return None
        offered = self._opponent_staged(obs_row)
        if offered < 0:
            # 何が提示されたか読めない局面（反射など）。仕様の既定に合わせて断る。
            return ACTION_DEAL_NO
        kind = feature(offered, "type")
        if kind in ("miracle", "defense") or feature(offered, "price") <= BUY_MAX_PRICE:
            return ACTION_DEAL_YES
        return ACTION_DEAL_NO

    def _act_sell_select(self, obs_row, mask_row) -> int | None:
        """何を出品するか。値段の高い神器から出す。"""
        hand = self._hand(obs_row)
        slots = self._hand_choices(mask_row, hand)
        sellable = [
            i for i in slots
            if hand[i] not in (ID_SELL, ID_BUY, ID_EXCHANGE)
            and feature(hand[i], "price") >= SELL_MIN_PRICE
        ]
        # 15円以上が無くても出品はしなければならないので、その場合は
        # 手持ちで一番高いものを出す（None を返すとランダムに落ちる）。
        candidates = sellable or [i for i in slots if hand[i] not in (ID_SELL, ID_BUY)]
        if not candidates:
            return None
        best = max(feature(hand[i], "price") for i in candidates)
        return self._pick([i for i in candidates if feature(hand[i], "price") == best])

    def _act_discard(self, obs_row, mask_row) -> int | None:
        """何を捨てるか。余った取引カードと弱い奇跡から捨てる。

        優先順位は、両替を2枚・買う・売る・スマイルの貝がらを1枚ずつ残して
        余りを捨て、次に強い奇跡でない奇跡を捨てる。武器と防具は残す。
        """
        hand = self._hand(obs_row)
        slots = self._hand_choices(mask_row, hand)
        if not slots:
            return None

        for card, keep in DISCARD_KEEP_LIMITS.items():
            picks = [i for i in slots if hand[i] == card]
            if len(picks) > keep:
                return self._pick(picks)

        weak_miracles = [
            i for i in slots
            if feature(hand[i], "type") == "miracle" and hand[i] not in STRONG_MIRACLES
        ]
        if weak_miracles:
            return self._pick(weak_miracles)

        # 上のどれにも当てはまらなくても、手札が溢れている以上どれかは捨てる。
        # ここで None を返すとランダムな合法手になり、防具まで捨ててしまう。
        # 防具・武器・強い奇跡は最後に回し、それ以外を値段の安い順に捨てる。
        # 奇跡は価格が0なので、価格だけで並べると強い奇跡が真っ先に捨てられる。
        def rank(slot: int) -> tuple[int, int]:
            card = hand[slot]
            keep_last = int(
                feature(card, "type") in ("defense", "weapon") or card in STRONG_MIRACLES
            )
            return (keep_last, feature(card, "price"))

        return ACTION_HAND_0 + min(slots, key=rank)

    @staticmethod
    def _opponent_staged(obs_row: np.ndarray) -> int:
        """相手が場に出しているカードの先頭。売買で提示されたカードがここに入る。"""
        start = fc.OPP_STAGED_CARDS_START
        return int(obs_row[start])

    def _act_target_select(self, obs_row, mask_row) -> int | None:
        """対象選択。仮置きしたカードの性質で「自分」「相手」を分ける。

        既存の HeuristicOpponent が常に「相手」を選んでいたのがここです。
        """
        staged = self._staged(obs_row)
        if staged.size == 0:
            return None
        first = int(staged[0])

        # 売る・買うは相手に仕掛けてこそ意味がある
        if first in (ID_SELL, ID_BUY):
            return ACTION_TARGET_OPP if mask_row[ACTION_TARGET_OPP] else ACTION_TARGET_SELF

        # 相手の手札・奇跡を削る雑貨だけ相手へ
        if first in OPPONENT_SUNDRIES:
            return ACTION_TARGET_OPP if mask_row[ACTION_TARGET_OPP] else ACTION_TARGET_SELF

        # 攻撃力を持つものは相手へ
        if feature(first, "attack_power") > 0:
            return ACTION_TARGET_OPP if mask_row[ACTION_TARGET_OPP] else ACTION_TARGET_SELF

        # それ以外（回復・MP回復・お金・状態異常回復など）は自分へ
        return ACTION_TARGET_SELF if mask_row[ACTION_TARGET_SELF] else ACTION_TARGET_OPP

    def _act_attack_plus(self, obs_row, mask_row) -> int | None:
        """武器の重ねがけ。プラスがあるだけ重ねてから撃つ。"""
        hand = self._hand(obs_row)
        _, mp, _ = self._stats(obs_row)
        slots = self._hand_choices(mask_row, hand)

        # 強いプラス奇跡を優先し、次にその他のプラス
        strong = [i for i in slots if hand[i] in STRONG_PLUS_MIRACLES and feature(hand[i], "mp_cost") <= mp]
        if strong:
            return self._pick(strong)
        if slots:
            return self._pick(slots)
        if mask_row[ACTION_TARGET_OPP]:
            return ACTION_TARGET_OPP
        return None

    def _act_defense(self, obs_row, mask_row) -> int | None:
        """防具の選択。被弾量を超えない範囲で、いちばん近い守を積む。

        過剰ガードは防具の無駄なので、いま積んでいる守が被弾量に届いていない
        あいだだけ重ねます。同じだけ寄与するなら守の小さい防具から使い、
        良い防具を温存します。
        """
        hand = self._hand(obs_row)
        slots = self._hand_choices(mask_row, hand)
        if not slots:
            return ACTION_CONFIRM if mask_row[ACTION_CONFIRM] else None

        incoming = self._incoming_damage(obs_row)
        current = int(round(obs_row[fc.MISC_START + 1] * STAT_SCALE))
        if current >= incoming:
            return ACTION_CONFIRM if mask_row[ACTION_CONFIRM] else self._pick(slots)

        need = incoming - current
        # 足りない分をちょうど埋める防具を探す。無ければ最も近いもの。
        # 守が小さいものから見るので、同点なら安い防具が選ばれる。
        by_def = sorted(slots, key=lambda i: (feature(hand[i], "defense_power"), i))
        cheap = [i for i in by_def if 0 < feature(hand[i], "defense_power") <= CHEAP_ARMOR_DEF]
        if cheap:
            return self._pick([cheap[0]])

        enough = [i for i in by_def if feature(hand[i], "defense_power") >= need]
        if enough:
            return ACTION_HAND_0 + enough[0]
        return ACTION_HAND_0 + by_def[-1]

    def _act_exchange(self, obs_row, mask_row, phase) -> int | None:
        """両替の数値選択。HP -> MP -> お金 の順に決める。"""
        hp, mp, money = self._stats(obs_row)
        want_hp, want_mp, _ = exchange_allocation(hp + mp + money)
        want = want_hp if phase == PHASE_EXCHANGE_HP else want_mp
        # 合法な数値のうち、希望に最も近いものを選ぶ
        legal_nums = np.flatnonzero(mask_row[ACTION_NUM_0 : ACTION_NUM_0 + 100])
        if legal_nums.size == 0:
            return None
        return ACTION_NUM_0 + int(legal_nums[np.argmin(np.abs(legal_nums - want))])

    # -- 本体 ---------------------------------------------------------------

    def _act_row(self, obs_row: np.ndarray, mask_row: np.ndarray) -> int | None:
        phase = self._phase(obs_row)

        if phase == PHASE_MAIN:
            return self._act_main(obs_row, mask_row)
        if phase == PHASE_TARGET_SELECT:
            return self._act_target_select(obs_row, mask_row)
        if phase in (PHASE_ATTACK_PLUS, PHASE_MIRACLE_PLUS, PHASE_GROUP_WEAPON, PHASE_GROUP_MIRACLE):
            return self._act_attack_plus(obs_row, mask_row)
        if phase in (PHASE_DEFENSE, PHASE_MIRACLE_DEFENSE):
            return self._act_defense(obs_row, mask_row)
        if phase in (PHASE_EXCHANGE_HP, PHASE_EXCHANGE_MP):
            return self._act_exchange(obs_row, mask_row, phase)
        if phase == PHASE_BUY:
            return self._act_buy(obs_row, mask_row)
        if phase == PHASE_SELL_SELECT:
            return self._act_sell_select(obs_row, mask_row)
        if phase == PHASE_DISCARD:
            return self._act_discard(obs_row, mask_row)
        return None

    def act(self, observations: np.ndarray, action_masks: np.ndarray) -> np.ndarray:
        masks = action_masks.astype(bool)
        actions = self._random_legal(masks)          # 既定はランダムな合法手
        explore = self._rng.random(len(actions)) < self.explore_rate

        for i in range(len(actions)):
            if explore[i]:
                continue                              # 20%はルールを外す
            chosen = self._act_row(observations[i], masks[i])
            # 合法でない答えが返ったら既定（ランダム）のままにする。方策の想定と
            # 合法手がずれても学習を止めないため。
            if chosen is not None and masks[i][chosen]:
                actions[i] = chosen

        return actions.astype(np.int32)
