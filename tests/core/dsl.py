"""ゴッドフィールドのコアロジックを宣言的にテストするための DSL。

【なぜこの層があるのか】
従来のテストは `runner.state.set_true_hand(0, 0, card_id)` のような低レベル操作の
羅列で、盤面の意図が読み取りにくく、確率で分岐する挙動はシード総当たり探索
（最大 100,000 回）に頼っていました。

この DSL では
  1. 盤面を `Side(...)` で宣言する（スロット番号ではなくカード名で指定できる）
  2. 操作をカード名で書く（`g.attack("weapons/punch")`）
  3. 期待値を `g.expect(p1_hp=30, phase=...)` でまとめて宣言する
  4. 確率判定を `g.rng.bounce(success=True)` のように名前で固定する
ことで、テストが「何を検証しているか」だけを書けるようにしています。

C++ 側の乱数注入層（godfield_core/src/rng.h）と対になっています。
"""

from __future__ import annotations

import json
import os
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

import godfield_core
from godfield_core import (
    ActionType,
    CurseType,
    Element,
    EventType,
    GamePhase,
    RollKind,
    SicknessType,
)

# ============================================================================
# カード名とIDの相互変換 / Card name resolution
# ============================================================================

_ASSETS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "assets",
    "godfield_cards.json",
)

_cards: list[dict] | None = None
_by_id_str: dict[str, int] = {}
_by_jp_name: dict[str, int] = {}
_id_to_label: dict[int, str] = {}


def _load() -> list[dict]:
    """カードマスタを一度だけ読み込みます。"""
    global _cards
    if _cards is None:
        with open(_ASSETS, encoding="utf-8") as f:
            _cards = json.load(f)
        for c in _cards:
            if c.get("id_str"):
                _by_id_str[c["id_str"]] = c["id"]
            if c.get("name"):
                _by_jp_name[c["name"]] = c["id"]
            # 失敗メッセージには日本語名を出す（id_str だけだと実機と突き合わせにくい）
            _id_to_label[c["id"]] = c.get("name") or c.get("id_str") or f"#{c['id']}"
    return _cards


def all_cards() -> list[dict]:
    """全カードの生データを返します。"""
    return list(_load())


def card_id(card: str | int) -> int:
    """カード名（id_str または日本語名）または ID を ID に正規化します。"""
    if isinstance(card, int):
        return card
    _load()
    if card in _by_id_str:
        return _by_id_str[card]
    if card in _by_jp_name:
        return _by_jp_name[card]
    raise KeyError(
        f"カード '{card}' は assets/godfield_cards.json に存在しません。"
        " id_str（例 'weapons/punch'）か日本語名（例 '革の服'）で指定してください。"
    )


def card_name(cid: int) -> str:
    """カードIDを人間が読めるラベルに変換します（空スロットは '-'）。"""
    if cid == godfield_core.CARD_EMPTY:
        return "-"
    _load()
    return _id_to_label.get(cid, f"#{cid}")


def card_feature(card: str | int, key: str, default: Any = None) -> Any:
    """カードの属性値（attack_power, accuracy など）をマスタから取得します。"""
    cid = card_id(card)
    for c in _load():
        if c["id"] == cid:
            return c.get(key, default)
    raise KeyError(f"カードID {cid} が見つかりません")


# カードマスタの element は日本語1文字。C++ の card_registry.cpp の element_map と
# 同じ対応表であること（片方だけ変えると属性判定が静かにズレる）。
_ELEMENT_BY_NAME = {
    "": Element.ELEM_NONE,
    "火": Element.ELEM_FIRE,
    "水": Element.ELEM_WATER,
    "木": Element.ELEM_WOOD,
    "土": Element.ELEM_STONE,
    "光": Element.ELEM_LIGHT,
    "闇": Element.ELEM_DARKNESS,
}


def element_of(card: str | int) -> Element:
    """カードの属性を Element enum で返します。

    テストに属性を直書きすると、マスタ側の属性を変えたときに黙って通らなくなる
    （あるいは誤った属性を検証し続ける）ため、必ずマスタから引きます。
    """
    raw = card_feature(card, "element", "") or ""
    if raw not in _ELEMENT_BY_NAME:
        raise KeyError(f"未知の属性 '{raw}' です（カード: {card_name(card_id(card))}）")
    return _ELEMENT_BY_NAME[raw]


def cards_of_element(element: Element, card_type: str = "defense") -> list[int]:
    """指定した属性・種別のカードIDを全件返します（属性ごとの網羅テスト用）。"""
    return [
        c["id"]
        for c in _load()
        if c.get("type") == card_type and element_of(c["id"]) == element
    ]


def armor_of_element(element: Element) -> int:
    """指定した属性の防具を1枚返します。

    テストにカード名を直書きすると、そのカードのマスタ属性が変わったときに
    「別の属性を検証しているのに気付かない」ことになるため、属性から引きます。
    """
    found = cards_of_element(element, "defense")
    if not found:
        raise AssertionError(f"属性 {Element(element).name} の防具がカードマスタにありません")
    return found[0]


def cards_where(**criteria: Any) -> list[int]:
    """条件に一致する全カードのIDを返します（網羅テストの母集団を作るのに使う）。"""
    out = []
    for c in _load():
        if all(c.get(k) == v for k, v in criteria.items()):
            out.append(c["id"])
    return out


def dream_candidates(card: str | int) -> list[int]:
    """夢状態でそのカードが偽装されうる相手のカードID一覧（自分自身は含まない）。"""
    return list(godfield_core.get_dream_candidates(card_id(card)))


# ============================================================================
# 乱数の指示 / RNG scripting
# ============================================================================

# 閾値方式の判定（BOUNCE, GUARDIAN_LEAVE, SICKNESS_WORSEN, ACCURACY など）は
# C++ 側がすべて「roll が小さいほど発生する」向きで実装されている
#   - roll <  RATE      -> 発生する（BOUNCE / MARS_RING / GUARDIAN_LEAVE / ...）
#   - roll >= accuracy  -> 外れる（ACCURACY。つまり roll が小さいほど命中する）
# ため、下限=発生・上限=不発で統一できる。テストが個々の閾値の向きを知る必要はない。
HAPPENS = godfield_core.ROLL_MIN
NEVER = godfield_core.ROLL_MAX


class RngController:
    """確率判定を名前で固定するためのコントローラ。`Game.rng` から使います。

    force系（`force`）は回数を問わず固定し、script系（`script`）はちょうどその回数
    だけ判定されることを要求します（超えると例外）。どちらも、指示したのに一度も
    使われなければ conftest の autouse フィクスチャがテストを失敗させます。
    """

    # --- 低レベルAPI ---------------------------------------------------------

    def force(self, kind: RollKind, value: int, *, optional: bool = False) -> RngController:
        """以後その判定が常に value を返すようにします。

        `optional=True` は「検証対象ではなく、局面を決定的にするための背景固定」の印で、
        未消費検査の対象外になります。判定が起きるかどうかがテストの主題である場合は
        既定（False）のままにして、空振りを検出させてください。
        """
        godfield_core.rng_force(kind, value, optional)
        return self

    def script(
        self, kind: RollKind, values: Sequence[int], *, repeat_last: bool = False
    ) -> RngController:
        """その判定がちょうどこの順で行われることを指示します（回数超過は例外）。

        `repeat_last=True` にすると使い切った後は最後の値を繰り返します。
        「先頭の数回だけ意味を持たせ、残りは無害な値で埋めたい」場合に使います。
        """
        godfield_core.rng_script(kind, list(values), repeat_last)
        return self

    def pick_order(self, kind: RollKind, preferred: Sequence[int]) -> RngController:
        """シャッフル系の判定で、指定したスロットを先頭から順に並べます。"""
        godfield_core.rng_pick_order(kind, list(preferred))
        return self

    def forbid_unscripted(self) -> RngController:
        """指示のない乱数消費が起きたら例外にします（運に依存しないことの証明）。

        山札ドロー（DECK_DRAW）はクリーンアップで必ず発生するため、これを使う場合は
        `deck_always()` か `next_draws()` も併せて指定してください。
        """
        godfield_core.rng_forbid_unscripted(True)
        return self

    def consumed(self, kind: RollKind) -> int:
        """その判定が実際に何回行われたかを返します。"""
        return godfield_core.rng_consumed(kind)

    # --- 意味的ヘルパー -----------------------------------------------------
    # 閾値の向きの知識はここだけに置く。個々のテストには書かせない。

    def hits(self, *, always: bool = True) -> RngController:
        """命中率判定（accuracy < 100 の武器・守護神攻撃）を必中／必ず外すに固定します。"""
        return self.force(RollKind.ACCURACY, HAPPENS if always else NEVER)

    def bounce(self, *, success: bool) -> RngController:
        """＜弾く＞の成功判定を固定します。"""
        return self.force(RollKind.BOUNCE, HAPPENS if success else NEVER)

    def mars_ring(self, *, counters: bool) -> RngController:
        """火星の指輪の反撃発動を固定します。"""
        return self.force(RollKind.MARS_RING, HAPPENS if counters else NEVER)

    def guardian_leave(self, *, leaves: bool) -> RngController:
        """被ダメージ時の守護神離脱を固定します。"""
        return self.force(RollKind.GUARDIAN_LEAVE, HAPPENS if leaves else NEVER)

    def ascension_bow(self, *hits_seq: bool) -> RngController:
        """昇天弓の命中を固定します。複数渡すと発射ごとの命中／外れを順に指定します。"""
        if len(hits_seq) == 1:
            return self.force(RollKind.ASCENSION_BOW_HIT, HAPPENS if hits_seq[0] else NEVER)
        return self.script(
            RollKind.ASCENSION_BOW_HIT, [HAPPENS if h else NEVER for h in hits_seq]
        )

    def sickness_worsen(self, *worsens_seq: bool) -> RngController:
        """病気の悪化判定を固定します。複数渡すとターンごとの悪化／非悪化を順に指定します。"""
        if len(worsens_seq) == 1:
            return self.force(RollKind.SICKNESS_WORSEN, HAPPENS if worsens_seq[0] else NEVER)
        return self.script(
            RollKind.SICKNESS_WORSEN, [HAPPENS if w else NEVER for w in worsens_seq]
        )

    def guardian_act(self, *, acts: bool, action: int | None = None) -> RngController:
        """守護神が行動するかを固定し、`action`（1..5）で5種の行動のどれかを指定します。

        閾値表は C++ の constants.h から取得するため、確率配分を変更しても
        テスト側を書き換える必要はありません。
        """
        self.force(RollKind.GUARDIAN_ACT, HAPPENS if acts else NEVER)
        if action is not None:
            thresholds = godfield_core.GUARDIAN_ACT_CHOICE_THRESHOLDS
            if not 1 <= action <= len(thresholds):
                raise ValueError(f"action は 1..{len(thresholds)} で指定してください: {action}")
            # 行動1 は roll < thresholds[0]、行動N は thresholds[N-2] <= roll < thresholds[N-1]
            self.force(RollKind.GUARDIAN_ACT_CHOICE, 0 if action == 1 else thresholds[action - 2])
        return self

    def guardian_action_card(self, guardian: int, card: str | int) -> RngController:
        """守護神の行動を「行動カードの名前」で指定します。

        act_idx（1..5）をテストに直書きすると、C++ 側の行動カード表の並びを
        変えた瞬間に別の行動を黙って検証してしまいます。カード名から表を
        逆引きすることでそれを防ぎます。
        """
        cards = godfield_core.get_guardian_action_cards(int(guardian))
        if not cards:
            raise ValueError(
                f"守護神 {guardian} は行動カード表を持ちません"
                "（攻撃系6神と海王神のみ。月神は moon_miracle() を使ってください）。"
            )
        target = card_id(card)
        if target not in cards:
            raise ValueError(
                f"'{card_name(target)}' は守護神 {guardian} の行動ではありません。"
                f" 候補: {[card_name(c) for c in cards]}"
            )
        return self.guardian_act(acts=True, action=cards.index(target) + 1)

    def dream(
        self,
        real: str | int | None = None,
        *,
        disguised: bool,
        as_card: str | int | None = None,
    ) -> RngController:
        """夢状態でドローしたカードの見た目を固定します。

        `disguised=False` なら真のカードのまま見えます（それでも未確定のままです）。
        `disguised=True` なら偽装され、`real` と `as_card` を渡すと偽装先を名指しできます。
        偽装先の候補一覧は C++ から取得するため、カードデータが増減しても
        テストが黙って別のカードを検証してしまうことがありません。
        """
        self.force(RollKind.DREAM_DISGUISE, HAPPENS if disguised else NEVER)
        if as_card is None:
            return self
        if not disguised:
            raise ValueError("disguised=False では偽装先を指定できません。")
        if real is None:
            raise ValueError("偽装先の候補は真のカードごとに異なるため real も指定してください。")
        candidates = dream_candidates(real)
        target = card_id(as_card)
        if target not in candidates:
            raise ValueError(
                f"'{card_name(target)}' は '{card_name(card_id(real))}' の偽装先ではありません。"
                f" 候補: {[card_name(c) for c in candidates]}"
            )
        return self.force(RollKind.DREAM_FAKE_CARD, candidates.index(target))

    def phenomenon(self, ptype: int) -> RngController:
        """「運命のひも」で発生する超常現象を名指しします（PhenomenonType）。"""
        return self.force(RollKind.PHENOMENON, int(ptype))

    def guardian_pot(self, guardian: int) -> RngController:
        """守護神の壺で降臨する守護神を名指しします（GuardianType の 1..10）。"""
        return self.force(RollKind.GUARDIAN_POT, int(guardian))

    def moon_miracle(self, miracle: str | int) -> RngController:
        """月神が発動する奇跡をカード名で指定します。

        インデックスは C++ の MOON_MIRACLES から逆引きするため、配列の順序が
        変わっても別の奇跡を黙って検証してしまうことがありません。
        """
        target = card_id(miracle)
        miracles = godfield_core.get_moon_miracles()
        if target not in miracles:
            raise ValueError(
                f"'{card_name(target)}' は月神の発動候補ではありません。"
                f" 候補: {[card_name(m) for m in miracles]}"
            )
        return self.force(RollKind.MOON_MIRACLE, miracles.index(target))

    def next_draws(self, *cards: str | int, then: str | int | None = None) -> RngController:
        """山札から引かれるカードを順に指定します（回数超過は例外）。

        悪魔カードを混ぜるのは可（`draw_card_with_apocalypse` が効果を解決して
        再ドローするため、次の指示が消費されます）。

        `then` を渡すと、指定分を引き切った後は常にそのカードが引かれます。
        手札補充の回数を数えたくない場合に使います。
        """
        values = [card_id(c) for c in cards]
        if then is not None:
            tail = card_id(then)
            if card_feature(tail, "type") == "devil":
                raise ValueError(
                    f"then に悪魔カード '{card_name(tail)}' は指定できません（再ドローで無限ループになります）。"
                )
            values.append(tail)
        return self.script(RollKind.DECK_DRAW, values, repeat_last=then is not None)

    def deck_always(self, card: str | int) -> RngController:
        """山札から常に同じカードが引かれるようにします（補充が何回起きても良い場合）。

        手札補充のドローは起きる回数が局面依存で、テストの主題でもないため
        背景固定（未消費検査の対象外）として登録します。ドローが起きること自体を
        検証したい場合は `next_draws()` を使ってください（回数が厳密になります）。
        """
        cid = card_id(card)
        # draw_card_with_apocalypse は悪魔カードを引くと効果を適用して再ドローするループなので、
        # 悪魔を固定すると無限ループする。回数指定の next_draws() を使わせる。
        if card_feature(cid, "type") == "devil":
            raise ValueError(
                f"deck_always() に悪魔カード '{card_name(cid)}' は指定できません。"
                " 悪魔は引くたびに再ドローされるため無限ループになります。"
                " 代わりに next_draws('悪魔', '通常カード') のように回数を指定してください。"
            )
        return self.force(RollKind.DECK_DRAW, cid, optional=True)

    def apocalypse_draws(
        self, *outcomes: str | int | None, optional: bool = False, repeat_last: bool = False
    ) -> RngController:
        """終末の時のドローで出るものを順に指定します（`None` は通常の山札抽選）。

        悪魔を引くと効果が適用されたあと再ドローされるため、最後は必ず `None` を
        置いて通常抽選で終わらせてください（悪魔で終わると無限ループになります）。
        閾値は C++ の APOCALYPSE_DEVIL_THRESHOLDS から導出するので、確率配分を
        変更してもテスト側の書き換えは不要です。

        `optional=True` は「終末に入っていなければ抽選自体が起きない」ことを
        検証したい場合に使います（未消費検査の対象外になります）。
        `repeat_last=True` は、引いた悪魔で死亡してドローが打ち切られるなど、
        末尾の指示が消費されないことがある場合に使います。
        """
        devils = godfield_core.get_apocalypse_devils()
        thresholds = godfield_core.APOCALYPSE_DEVIL_THRESHOLDS
        values: list[int] = []
        for outcome in outcomes:
            if outcome is None:
                values.append(NEVER)  # どの悪魔の区間にも入らない = 通常抽選
                continue
            target = card_id(outcome)
            if target not in devils:
                raise ValueError(
                    f"'{card_name(target)}' は終末の時の悪魔ではありません。"
                    f" 候補: {[card_name(d) for d in devils]}"
                )
            idx = devils.index(target)
            # 区間 [thresholds[idx-1], thresholds[idx]) の下端を代表値にする
            values.append(0 if idx == 0 else thresholds[idx - 1])
        if optional:
            # 抽選が起きるかどうか自体が主題なので、未消費でも失敗にしない
            return self.force(RollKind.APOCALYPSE_DRAW, values[0], optional=True)
        return self.script(RollKind.APOCALYPSE_DRAW, values, repeat_last=repeat_last)

    def thump_thump_tear(self, *, heals: bool) -> RngController:
        """どきどきのなみだが回復（+10）か被弾（-10）かを固定します。"""
        return self.force(RollKind.THUMP_THUMP_TEAR, 0 if heals else 1)

    def discard_order(self, *slots: int) -> RngController:
        """ランダム破棄で捨てられる手札スロットの順序を指定します。"""
        return self.pick_order(RollKind.DISCARD_RANDOM_ORDER, list(slots))

    def discard_one(self, slot: int) -> RngController:
        """手札満杯で祈ったときに捨てられるスロットを指定します。"""
        return self.force(RollKind.DISCARD_ONE_SLOT, slot)

    def reveal_slot(self, *slots: int) -> RngController:
        """相手に公開されるスロットを指定します。"""
        return self.pick_order(RollKind.REVEAL_SLOT, list(slots))

    def hand_replace_slot(self, *slots: int) -> RngController:
        """手札満杯時に上書きされるスロットを指定します。"""
        return self.pick_order(RollKind.HAND_REPLACE_SLOT, list(slots))


# ============================================================================
# イベントログ / Event log
# ============================================================================


@dataclass(frozen=True)
class LoggedEvent:
    """イベント履歴の1件。`card` はカード名に解決済み。"""

    actor: int
    type: EventType
    card: str | None
    target: int | None
    value: float

    def __repr__(self) -> str:
        parts = [f"actor={self.actor}", f"{EventType(self.type).name}"]
        if self.card is not None:
            parts.append(f"card={self.card}")
        if self.target is not None:
            parts.append(f"target={self.target}")
        parts.append(f"value={self.value:g}")
        return "Ev(" + ", ".join(parts) + ")"


@dataclass(frozen=True)
class EventMatcher:
    """イベントの部分一致条件。指定しなかった項目は何でも一致します。"""

    type: EventType
    card: str | int | None = None
    actor: int | None = None
    target: int | None = None
    value: float | None = None

    def matches(self, ev: LoggedEvent) -> bool:
        if int(ev.type) != int(self.type):
            return False
        if self.card is not None and ev.card != card_name(card_id(self.card)):
            return False
        if self.actor is not None and ev.actor != self.actor:
            return False
        if self.target is not None and ev.target != self.target:
            return False
        if self.value is not None and abs(ev.value - self.value) > 1e-6:
            return False
        return True

    def __repr__(self) -> str:
        parts = [EventType(self.type).name]
        if self.card is not None:
            parts.append(f"card={card_name(card_id(self.card))}")
        if self.actor is not None:
            parts.append(f"actor={self.actor}")
        if self.target is not None:
            parts.append(f"target={self.target}")
        if self.value is not None:
            parts.append(f"value={self.value:g}")
        return "ev(" + ", ".join(parts) + ")"


def ev(
    type: EventType,
    card: str | int | None = None,
    actor: int | None = None,
    target: int | None = None,
    value: float | None = None,
) -> EventMatcher:
    """イベント期待値を作ります。`g.expect_events(ev(EventType.ATTACK_HIT, "weapons/punch"))`"""
    return EventMatcher(type=type, card=card, actor=actor, target=target, value=value)


# ============================================================================
# 盤面の宣言 / Board declaration
# ============================================================================


@dataclass
class Side:
    """片方のプレイヤーの初期状態。

    `hand` は先頭から順にスロット0,1,2...へ配置されます。`None` を混ぜると
    そのスロットを空にできるため、インデックス0以外の挙動も宣言的に書けます:

        hand=[None, None, "weapons/punch"]   # スロット2にパンチ

    `deployed` / `known_to_opp` / `used` は `hand` 内のスロット番号で指定します。
    """

    hp: int = 40
    mp: int = 0
    money: int = 0
    hand: Sequence[str | int | None] = field(default_factory=tuple)
    sickness: SicknessType = SicknessType.SICKNESS_NONE
    curses: Sequence[CurseType] = field(default_factory=tuple)
    guardian: int = 0
    deployed: Sequence[int] = field(default_factory=tuple)
    known_to_opp: Sequence[int] = field(default_factory=tuple)
    used: Sequence[int] = field(default_factory=tuple)
    pending_ascension_bows: int = 0


class Game:
    """1局面ぶんの InternalState を宣言的に組み立てて操作するラッパー。"""

    MAX_HAND = 18

    def __init__(
        self,
        p0: Side | None = None,
        p1: Side | None = None,
        *,
        phase: GamePhase = GamePhase.PHASE_MAIN,
        actor: int = 0,
        turn: int = 0,
        mushroom_turns: int = 0,
        seed: int = 0,
    ):
        self.state = godfield_core.InternalState()
        godfield_core.clear_state(self.state)
        # 指示のない判定は実乱数に落ちるため、既定シードを固定して再現性を確保する
        self.state.seed_rng(seed)
        self.state.current_phase = phase
        self.state.current_actor_id = actor
        self.state.current_turn = turn
        self.state.mushroom_turns = mushroom_turns
        self.state.is_done = False
        self.state.attacker_id = -1
        self.state.defender_id = -1
        self.state.pending_attack_power = 0
        self.state.pending_attack_element = Element.ELEM_NONE
        self.state.pending_attack_source_id = godfield_core.CARD_EMPTY

        self.rng = RngController()
        self._sides = (p0 or Side(), p1 or Side())
        for player, side in enumerate(self._sides):
            self._apply_side(player, side)

    # ------------------------------------------------------------------ setup

    def _apply_side(self, player: int, side: Side) -> None:
        s = self.state
        s.set_hp(player, side.hp)
        s.set_mp(player, side.mp)
        s.set_money(player, side.money)
        s.set_sickness(player, side.sickness)
        s.set_guardian(player, int(side.guardian))
        s.set_pending_ascension_bows(player, side.pending_ascension_bows)

        for ct in (CurseType.CURSE_FOG, CurseType.CURSE_FLASH,
                   CurseType.CURSE_DARK_CLOUD, CurseType.CURSE_DREAM):
            s.set_curses(player, ct, ct in side.curses)

        if len(side.hand) > self.MAX_HAND:
            raise ValueError(f"手札は最大 {self.MAX_HAND} 枚です: {len(side.hand)} 枚指定されました")

        for i in range(self.MAX_HAND):
            entry = side.hand[i] if i < len(side.hand) else None
            cid = godfield_core.CARD_EMPTY if entry is None else card_id(entry)
            s.set_true_hand(player, i, cid)
            s.set_apparent_hand(player, i, cid)
            s.set_is_known_to_opp(player, i, False)
            s.set_is_used(player, i, False)

        # 展開・公開・使用済みフラグは手札を置いた後に立てる（set_true_hand が確定状態を上書きするため）
        for slot in side.deployed:
            s.set_is_deployed(player, slot, True)
        for slot in side.known_to_opp:
            s.set_is_known_to_opp(player, slot, True)
        for slot in side.used:
            s.set_is_used(player, slot, True)

    # ----------------------------------------------------------- introspection

    def hp(self, player: int) -> int:
        return self.state.get_hp(player)

    def mp(self, player: int) -> int:
        return self.state.get_mp(player)

    def money(self, player: int) -> int:
        return self.state.get_money(player)

    def hand(self, player: int) -> list[str]:
        """手札にあるカード名のリスト（空スロットは除く）。"""
        return [
            card_name(self.state.get_true_hand(player, i))
            for i in range(self.MAX_HAND)
            if self.state.get_true_hand(player, i) != godfield_core.CARD_EMPTY
        ]

    def slot_of(self, player: int, card: str | int, nth: int = 0, *, include_used: bool = False) -> int:
        """カード名から手札スロット番号を引きます。同名が複数ある場合は nth で指定します。"""
        cid = card_id(card)
        found = 0
        for i in range(self.MAX_HAND):
            if self.state.get_true_hand(player, i) != cid:
                continue
            if not include_used and self.state.get_is_used(player, i):
                continue
            if found == nth:
                return i
            found += 1
        raise AssertionError(
            f"プレイヤー{player} の手札に '{card_name(cid)}'"
            f"{f'（{nth + 1}枚目）' if nth else ''} がありません。"
            f" 現在の手札: {self.hand(player)}"
        )

    def deployed_count(self, player: int) -> int:
        """場に展開されている奇跡の枚数。"""
        return sum(
            1 for i in range(self.MAX_HAND) if self.state.get_is_deployed(player, i)
        )

    def legal_actions(self) -> list[bool]:
        return godfield_core.get_legal_actions(self.state)

    def legal_cards(self, player: int | None = None) -> list[str]:
        """現在選択できる手札のカード名一覧。"""
        p = self.state.current_actor_id if player is None else player
        actions = self.legal_actions()
        out = []
        for i in range(self.MAX_HAND):
            if actions[int(ActionType.ACTION_SELECT_HAND_0) + i]:
                out.append(card_name(self.state.get_true_hand(p, i)))
        return out

    def event_log(self) -> list[LoggedEvent]:
        """イベント履歴を時系列順（古い順）に返します。

        make_observation がリングバッファを時系列順に展開してから返すため
        （game_logic.cpp の「リングバッファを時系列順に展開」参照）、
        未使用スロットの NONE を落とすだけでよい。履歴長は HISTORY_LENGTH=64 で、
        それを超えた分は C++ 側で捨てられている点に注意。
        """
        obs = godfield_core.get_observation(self.state, 0)
        out = []
        for e in obs.get_history():
            if int(e.event_type) == int(EventType.NONE):
                continue
            cid = int(e.card_id)
            out.append(
                LoggedEvent(
                    actor=int(e.actor),
                    type=EventType(int(e.event_type)),
                    card=None if cid < 0 else card_name(cid),
                    target=None if int(e.target_id) < 0 else int(e.target_id),
                    value=float(e.value),
                )
            )
        return out

    # ---------------------------------------------------------------- actions

    def step(self, action: ActionType) -> Game:
        """生のアクションを1つ実行します。"""
        godfield_core.step_game(self.state, action)
        return self

    def select(self, *cards: str | int, player: int | None = None) -> Game:
        """カード名を指定して仮置きします（スロット番号は自動で解決）。"""
        p = self.state.current_actor_id if player is None else player
        for c in cards:
            slot = self.slot_of(p, c)
            self.step(ActionType(int(ActionType.ACTION_SELECT_HAND_0) + slot))
        return self

    def select_slots(self, *slots: int) -> Game:
        """スロット番号を直接指定して仮置きします（同名カードの配置を検証する場合に使う）。"""
        for slot in slots:
            self.step(ActionType(int(ActionType.ACTION_SELECT_HAND_0) + slot))
        return self

    def confirm(self) -> Game:
        return self.step(ActionType.ACTION_CONFIRM)

    def target_opp(self) -> Game:
        return self.step(ActionType.ACTION_TARGET_OPP)

    def target_self(self) -> Game:
        return self.step(ActionType.ACTION_TARGET_SELF)

    def attack(self, *cards: str | int, to_self: bool = False) -> Game:
        """指定カード（武器プラス対応・複数可）で攻撃し、対象を選択します。"""
        self.select(*cards)
        return self.target_self() if to_self else self.target_opp()

    def attack_slots(self, *slots: int, to_self: bool = False) -> Game:
        """スロット番号を指定して攻撃します（同名カードを重ねる場合に使う）。"""
        self.select_slots(*slots)
        return self.target_self() if to_self else self.target_opp()

    def use(self, *cards: str | int, to_self: bool = False, confirm: bool = True) -> Game:
        """雑貨・奇跡などを使用し、対象選択と確定まで行います。"""
        self.select(*cards)
        self.target_self() if to_self else self.target_opp()
        return self.confirm() if confirm else self

    def defend(self, *cards: str | int, confirm: bool = True) -> Game:
        """指定カードを防御・反射用に仮置きして確定します。"""
        self.select(*cards)
        return self.confirm() if confirm else self

    def take_hit(self) -> Game:
        """防御をスルーしてダメージを受けます。"""
        return self.confirm()

    def pray(self) -> Game:
        return self.step(ActionType.ACTION_PRAY)

    def discard(self, *cards: str | int) -> Game:
        """「捨てる」を選び、指定カードを捨てて確定します。"""
        self.step(ActionType.ACTION_DISCARD)
        self.select(*cards)
        return self.confirm()

    def deal_yes(self) -> Game:
        return self.step(ActionType.ACTION_DEAL_YES)

    def deal_no(self) -> Game:
        return self.step(ActionType.ACTION_DEAL_NO)

    def num(self, n: int) -> Game:
        """数値選択（両替など）を行います。"""
        return self.step(ActionType(int(ActionType.ACTION_NUM_0) + n))

    def auto_advance(self, limit: int = 512) -> Game:
        """合法手が1つしかない局面を自動で消化します。"""
        for _ in range(limit):
            if self.state.is_done:
                return self
            single = godfield_core.get_single_legal_action(self.state)
            if single == -1:
                return self
            self.step(ActionType(single))
        raise AssertionError(f"auto_advance が {limit} ステップで収束しませんでした")

    # ------------------------------------------------------------- assertions

    _EXPECT_KEYS = {
        "phase": lambda g: g.state.current_phase,
        "actor": lambda g: g.state.current_actor_id,
        "turn": lambda g: g.state.current_turn,
        "attacker": lambda g: g.state.attacker_id,
        "defender": lambda g: g.state.defender_id,
        "is_done": lambda g: g.state.is_done,
        "p0_reward": lambda g: g.state.p0_reward,
        "p1_reward": lambda g: g.state.p1_reward,
        "pending_power": lambda g: g.state.pending_attack_power,
        "pending_element": lambda g: g.state.pending_attack_element,
        "pending_defense": lambda g: g.state.pending_defense_power,
        "pending_is_group": lambda g: g.state.pending_is_group_attack,
        "remaining_attacks": lambda g: g.state.remaining_attacks,
        "p0_hp": lambda g: g.hp(0),
        "p1_hp": lambda g: g.hp(1),
        "p0_mp": lambda g: g.mp(0),
        "p1_mp": lambda g: g.mp(1),
        "p0_money": lambda g: g.money(0),
        "p1_money": lambda g: g.money(1),
        "p0_guardian": lambda g: g.state.get_guardian(0),
        "p1_guardian": lambda g: g.state.get_guardian(1),
        "p0_sickness": lambda g: g.state.get_sickness(0),
        "p1_sickness": lambda g: g.state.get_sickness(1),
        "p0_bows": lambda g: g.state.get_pending_ascension_bows(0),
        "p1_bows": lambda g: g.state.get_pending_ascension_bows(1),
    }

    def expect(self, **expected: Any) -> Game:
        """複数の期待値を一度に検証します。不一致はすべてまとめて報告されます。

        使えるキー: phase, actor, turn, attacker, defender, is_done,
        p0_reward, p1_reward, pending_power, pending_element, pending_defense,
        pN_hp / pN_mp / pN_money / pN_guardian / pN_sickness / pN_bows,
        pN_curses（CurseType の集合）, pN_hand（カード名のリスト、順不同）。
        """
        failures: list[str] = []
        for key, want in expected.items():
            if key in self._EXPECT_KEYS:
                got = self._EXPECT_KEYS[key](self)
                if got != want:
                    failures.append(f"  {key}: 期待 {want!r} / 実際 {got!r}")
            elif key in ("p0_curses", "p1_curses"):
                player = int(key[1])
                got_set = {
                    ct
                    for ct in (CurseType.CURSE_FOG, CurseType.CURSE_FLASH,
                               CurseType.CURSE_DARK_CLOUD, CurseType.CURSE_DREAM)
                    if self.state.get_curses(player, ct)
                }
                want_set = set(want)
                if got_set != want_set:
                    failures.append(
                        f"  {key}: 期待 {sorted(c.name for c in want_set)}"
                        f" / 実際 {sorted(c.name for c in got_set)}"
                    )
            elif key in ("p0_hand", "p1_hand"):
                player = int(key[1])
                got_hand = Counter(self.hand(player))
                want_hand = Counter(card_name(card_id(c)) for c in want)
                if got_hand != want_hand:
                    failures.append(
                        f"  {key}: 期待 {sorted(want_hand.elements())}"
                        f" / 実際 {sorted(got_hand.elements())}"
                    )
            else:
                raise KeyError(
                    f"expect() は '{key}' を知りません。"
                    f" 使えるキー: {sorted(self._EXPECT_KEYS) + ['p0_curses', 'p1_curses', 'p0_hand', 'p1_hand']}"
                )
        if failures:
            raise AssertionError("期待した状態と一致しません:\n" + "\n".join(failures) + f"\n{self.describe()}")
        return self

    def expect_legal(self, cards: Iterable[str | int] = (), *, player: int | None = None) -> Game:
        """指定カードがすべて選択可能であることを検証します。"""
        p = self.state.current_actor_id if player is None else player
        actions = self.legal_actions()
        missing = []
        for c in cards:
            slot = self.slot_of(p, c)
            if not actions[int(ActionType.ACTION_SELECT_HAND_0) + slot]:
                missing.append(f"{card_name(card_id(c))}(スロット{slot})")
        if missing:
            raise AssertionError(
                f"選択できるべきカードが非合法です: {missing}\n"
                f"現在選択可能: {self.legal_cards(p)}\n{self.describe()}"
            )
        return self

    def expect_illegal(self, cards: Iterable[str | int] = (), *, player: int | None = None) -> Game:
        """指定カードがすべて選択不可であることを検証します。

        「このターンすでに使ったカード」も検証対象なので、使用済みスロットも探します。
        """
        p = self.state.current_actor_id if player is None else player
        actions = self.legal_actions()
        unexpected = []
        for c in cards:
            slot = self.slot_of(p, c, include_used=True)
            if actions[int(ActionType.ACTION_SELECT_HAND_0) + slot]:
                unexpected.append(f"{card_name(card_id(c))}(スロット{slot})")
        if unexpected:
            raise AssertionError(
                f"選択できないはずのカードが合法です: {unexpected}\n{self.describe()}"
            )
        return self

    def expect_actions(self, **allowed: bool) -> Game:
        """`pray` / `discard` / `confirm` / `target_opp` / `target_self` の可否を検証します。"""
        mapping = {
            "pray": ActionType.ACTION_PRAY,
            "discard": ActionType.ACTION_DISCARD,
            "confirm": ActionType.ACTION_CONFIRM,
            "target_opp": ActionType.ACTION_TARGET_OPP,
            "target_self": ActionType.ACTION_TARGET_SELF,
        }
        actions = self.legal_actions()
        failures = []
        for name, want in allowed.items():
            if name not in mapping:
                raise KeyError(f"expect_actions() は '{name}' を知りません: {sorted(mapping)}")
            got = actions[int(mapping[name])]
            if got != want:
                failures.append(f"  {name}: 期待 {want} / 実際 {got}")
        if failures:
            raise AssertionError("行動の可否が一致しません:\n" + "\n".join(failures) + f"\n{self.describe()}")
        return self

    def expect_events(self, *matchers: EventMatcher, exact: bool = False) -> Game:
        """イベント履歴を検証します。

        既定では「この順に現れる」部分列一致（間に他のイベントが挟まっても良い）。
        `exact=True` にすると履歴全体との完全一致を要求します（副作用の抜けや
        余剰イベントを検出できる）。
        """
        log = self.event_log()
        if exact:
            if len(log) != len(matchers) or not all(m.matches(e) for m, e in zip(matchers, log)):
                raise AssertionError(
                    "イベント履歴が完全一致しません:\n"
                    f"  期待({len(matchers)}件): {list(matchers)}\n"
                    f"  実際({len(log)}件): {log}"
                )
            return self
        idx = 0
        for m in matchers:
            while idx < len(log) and not m.matches(log[idx]):
                idx += 1
            if idx == len(log):
                raise AssertionError(
                    f"イベント {m!r} が見つかりません（この位置以降に）。\n実際の履歴: {log}"
                )
            idx += 1
        return self

    def expect_no_events(self, *matchers: EventMatcher) -> Game:
        """指定したイベントが1件も発生していないことを検証します。"""
        log = self.event_log()
        for m in matchers:
            hit = [e for e in log if m.matches(e)]
            if hit:
                raise AssertionError(f"発生しないはずのイベントがあります: {m!r} -> {hit}")
        return self

    def describe(self) -> str:
        """失敗メッセージ用の局面ダンプ。"""
        s = self.state
        lines = [
            "--- 局面 ---",
            f"phase={s.current_phase} actor={s.current_actor_id} turn={s.current_turn}"
            f" attacker={s.attacker_id} defender={s.defender_id} is_done={s.is_done}",
            f"pending: power={s.pending_attack_power} element={s.pending_attack_element}"
            f" defense={s.pending_defense_power}",
        ]
        for p in range(2):
            slots = []
            for i in range(self.MAX_HAND):
                cid = s.get_true_hand(p, i)
                if cid == godfield_core.CARD_EMPTY:
                    continue
                flags = ""
                if s.get_is_used(p, i):
                    flags += "使"
                if s.get_is_deployed(p, i):
                    flags += "展"
                if s.get_is_known_to_opp(p, i):
                    flags += "公"
                slots.append(f"[{i}]{card_name(cid)}{f'({flags})' if flags else ''}")
            lines.append(
                f"P{p}: HP={s.get_hp(p)} MP={s.get_mp(p)} 金={s.get_money(p)}"
                f" 病={SicknessType(s.get_sickness(p)).name} 守護神={s.get_guardian(p)}"
                f" 昇天弓={s.get_pending_ascension_bows(p)}"
            )
            lines.append(f"    手札: {' '.join(slots) if slots else '（なし）'}")
        return "\n".join(lines)
