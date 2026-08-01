"""環境の内部で相手の手番を指す方策。

`GodFieldVectorEnv` は学習者の意思決定点だけを SB3 に見せ、相手の手番はこのモジュールの
方策で消化します。これにより PPO から見たロールアウトが単一エージェントのものになり、
連続する遷移が同じエージェントに属します（交互に混ざると GAE が相手視点の価値を
符号反転せずにブートストラップしてしまう）。

方策は観測とマスクの「バッチ」を受け取ります。C++ の InternalState を Python へ
コピーすると1環境あたり数KBの転送になるため、観測配列だけで判断できる形にしています。
"""

from __future__ import annotations

from typing import Protocol

import numpy as np
import torch

import godfield_core
from godfield_rl import feature_config as fc

# 「相手を対象 / 買う / 承諾」と「自分を対象 / 買わない / 確定」。フェイズにより意味が変わる
ACTION_TARGET_OPP = int(godfield_core.ActionType.ACTION_TARGET_OPP)
ACTION_TARGET_SELF = int(godfield_core.ActionType.ACTION_TARGET_SELF)


class Opponent(Protocol):
    """相手方策のインターフェース。"""

    def act(self, observations: np.ndarray, action_masks: np.ndarray) -> np.ndarray:
        """観測とマスクのバッチから、各環境の行動を返します。

        Args:
            observations: (N, 特徴量数) 現在の手番プレイヤー視点の観測。
            action_masks: (N, 行動数) bool の合法手マスク。
        Returns:
            (N,) int32 の行動列。
        """
        ...


class RandomOpponent:
    """合法手から一様ランダムに選ぶ相手。学習の下限を測るベースライン。"""

    def __init__(self, seed: int = 0):
        self._rng = np.random.default_rng(seed)

    def act(self, observations: np.ndarray, action_masks: np.ndarray) -> np.ndarray:
        # 各行の合法手から1つ選ぶ。マスクに乱数を掛けて最大値を取ることでループを避ける。
        scores = self._rng.random(action_masks.shape) * action_masks
        return np.argmax(scores, axis=1).astype(np.int32)


class HeuristicOpponent:
    """単純な方針で指す相手。学習の初期対戦相手と、強さの基準に使います。

    1. 決定系の行動（相手を対象 / 自分を対象・確定）が可能ならそれを優先する
    2. 次に、手札の空でないスロットを選ぶ
    3. どれも該当しなければ合法手からランダムに選ぶ

    【既知の偏り】1. は対象選択で**常に「相手を対象」**を選びます（SELF を先に
    書いてから OPP で上書きしているため）。武器なら正しいものの、回復系の雑貨を
    相手に使ってしまうため、これを模倣した学習者も同じ間違いを覚えます。実測では
    学習済みモデルが対象選択の 100%（19,542回）で「相手」を選んでおり、これを
    「自分」に直すだけで対ヒューリスティック勝率が +5% 変わりました。
    ここを変えると学習の初期条件が変わるので、モデルを作り直す前提で触ること。
    """

    def __init__(self, seed: int = 0):
        self._rng = np.random.default_rng(seed)

    def act(self, observations: np.ndarray, action_masks: np.ndarray) -> np.ndarray:
        hand_start = fc.HAND_CARDS_START
        hand = observations[:, hand_start : hand_start + fc.MAX_HAND_SIZE]

        # 3. 既定はランダムな合法手
        actions = np.argmax(self._rng.random(action_masks.shape) * action_masks, axis=1)

        # 2. 手札のカードを使う手を優先（空スロットの選択は避ける）
        hand_actions = action_masks[:, : fc.MAX_HAND_SIZE] & (hand != -1)
        has_hand = hand_actions.any(axis=1)
        if has_hand.any():
            picked = np.argmax(self._rng.random(hand_actions.shape) * hand_actions, axis=1)
            actions = np.where(has_hand, picked, actions)

        # 1. 決定系を最優先（仮置きや防御を確定させ、手番を進める）
        for decisive in (ACTION_TARGET_SELF, ACTION_TARGET_OPP):
            actions = np.where(action_masks[:, decisive], decisive, actions)

        return actions.astype(np.int32)


class FrozenOpponent:
    """保存された学習済みモデル（方策）を用いて行動を決定する相手。

    `deterministic` は用途によって変える必要があります。

    - 自己対戦のプールに入れる相手: `False`（既定）。確率的に指すことで対戦の
      多様性が生まれ、同じ局面ばかりを学習するのを避けられます。
    - 人間と対戦させる相手（可視化サーバー）: `True`。探索のためのブレは不要で、
      方策が最も良いと考える手だけを指させたい。

    推論は `MaskablePPO.predict` ではなく `policy.get_distribution` を直に呼びます。
    predict は観測の形をその都度調べ直す（ベクトル環境かどうかの判定、転置の要否）
    ぶんだけ Python 側が重く、こちらは形の分かったバッチしか渡さないので不要です。
    分布を1つ作れば行動も確率も取れるため、両方要る診断ツールで順伝播が1回で済みます。
    """

    def __init__(self, model, deterministic: bool = False, amp: bool = False):
        self.model = model
        self.deterministic = deterministic
        self.device = model.policy.device
        # bf16 は CUDA でしか意味がない。学習と違い推論は勾配を持たないので、
        # 既定は fp32 のまま（自己対戦の相手の手が精度で変わらないように）。
        self._amp = amp and self.device.type == "cuda"
        model.policy.set_training_mode(False)

    def _autocast(self):
        return torch.autocast("cuda", dtype=torch.bfloat16, enabled=self._amp)

    def _distribution(self, observations: np.ndarray, action_masks: np.ndarray):
        obs = torch.as_tensor(observations, dtype=torch.float32, device=self.device)
        masks = torch.as_tensor(np.asarray(action_masks), dtype=torch.bool, device=self.device)
        return self.model.policy.get_distribution(obs, action_masks=masks)

    def act(self, observations: np.ndarray, action_masks: np.ndarray) -> np.ndarray:
        with torch.inference_mode(), self._autocast():
            dist = self._distribution(observations, action_masks)
            actions = dist.get_actions(deterministic=self.deterministic)
        return actions.cpu().numpy().astype(np.int32)

    def action_probs(self, observations: np.ndarray, action_masks: np.ndarray) -> np.ndarray:
        """(N, 行動数) の行動確率。マスク済みなので合法手だけに質量が乗ります。"""
        with torch.inference_mode(), self._autocast():
            dist = self._distribution(observations, action_masks)
            probs = dist.distribution.probs
        return probs.float().cpu().numpy()


class PoolOpponent:
    """複数の相手方策の中から、ステップ単位（バッチ単位）でランダムに選んで推論する相手。

    GPUのバッチ効率を保つため、act() が呼ばれるたびに1つのモデルが選ばれ、
    そのモデルがバッチ内の全環境の相手をまとめて担当します。

    【錨（anchor）と分身（snapshot）を分ける理由】

    以前は両方を1つのリストに入れて一様に選んでいました。プールは
    「人手の戦略1体 + 自分の過去5体」だったので、人手の戦略と当たるのは約17%、
    残り83%は自分の過去と戦っていたことになります。

    自分の過去は自分と同じ弱点を持つため、その弱点は一度も罰されません。実測でも
    37M ステップ学習したモデルは、学習相手（人手の戦略の旧版・ヒューリスティック）
    には 71% / 93% と強い一方、一度も戦っていない相手には 45% しか勝てず、
    しかも「買う」を選ぶ確率が gen4 から gen36 までほとんど動きませんでした。

    そこで、外部の固定方策を「錨」として分け、当たる割合を直接指定できるように
    します。閉じた自己対戦から抜け出すための舵です。

    【錨を弱い順に並べて、少しずつ強い方へ移す】

    強い錨だけで最初から学習すると、勝敗がほぼ定数になって行動の良し悪しが差として
    出ません。実測では、初期化直後のネットの勝率は

        対 random 49.4% / 対 heuristic 26.0% / 対 strategic 3.3%

    で、人手の戦略が相手だと1,000局中33勝しかできません。しかも分身が現れるのは
    最初の保存（既定で1Mステップ）以降なので、それまでは錨が100%を占めます。

    そこで錨は**弱い順に並べたリスト**として持ち、学習の進み具合に応じて重みを
    梯子の上へ移します。`curriculum_end` に達した時点で最強の錨だけになります
    （そこから先は比率1）。進み具合は SelfPlayCallback が更新します。
    """

    def __init__(
        self,
        anchors: list[Opponent] | None = None,
        snapshots: list[Opponent] | None = None,
        seed: int = 0,
        anchor_ratio: float = 0.5,
        curriculum_end: float = 0.3,
    ):
        """Args:
            anchors: 学習を通じて固定の相手。**弱い順に並べる**こと。
            snapshots: 自己対戦のプール。SelfPlayCallback が入れ替えます。
            anchor_ratio: 錨と当たる確率。分身がまだ1体も無い間は常に錨を使います。
            curriculum_end: 学習の何割の時点で最強の錨だけになるか。
                0 にすると最初から最強の錨だけを使います。
        """
        if not 0.0 <= anchor_ratio <= 1.0:
            raise ValueError(f"anchor_ratio は 0..1 で指定してください: {anchor_ratio}")
        if not 0.0 <= curriculum_end <= 1.0:
            raise ValueError(f"curriculum_end は 0..1 で指定してください: {curriculum_end}")
        self.anchors = list(anchors or [])
        self.snapshots = list(snapshots or [])
        self.anchor_ratio = anchor_ratio
        self.curriculum_end = curriculum_end
        # 学習の進み具合 0..1。SelfPlayCallback が毎ステップ更新する。
        self.progress = 0.0
        self._rng = np.random.default_rng(seed)

    @property
    def opponents(self) -> list[Opponent]:
        """錨と分身をまとめた一覧（表示・件数確認用）。"""
        return self.anchors + self.snapshots

    def anchor_weights(self) -> np.ndarray:
        """今の進み具合での、錨ごとの選ばれる確率。

        梯子の上を連続に動く点として扱い、隣り合う2体だけに質量を置きます。
        段階的に切り替えるより、相手が急に変わって方策が崩れることが少なくて済みます。
        """
        n = len(self.anchors)
        weights = np.zeros(n)
        if n == 0:
            return weights
        if n == 1:
            weights[0] = 1.0
            return weights

        t = 1.0 if self.curriculum_end <= 0.0 else min(1.0, self.progress / self.curriculum_end)
        position = t * (n - 1)
        low = int(np.floor(position))
        if low >= n - 1:
            weights[-1] = 1.0
            return weights
        frac = position - low
        weights[low] = 1.0 - frac
        weights[low + 1] = frac
        return weights

    def select(self) -> Opponent:
        """この呼び出しで相手を務める方策を1つ選びます。"""
        if not self.anchors and not self.snapshots:
            raise RuntimeError("対戦相手のプールが空です。")
        if not self.anchors:
            return self._rng.choice(self.snapshots)
        if self.snapshots and self._rng.random() >= self.anchor_ratio:
            return self._rng.choice(self.snapshots)
        return self.anchors[self._rng.choice(len(self.anchors), p=self.anchor_weights())]

    def describe_anchors(self) -> str:
        """今の錨の配分を1行で表します（ログ用）。"""
        return " / ".join(
            f"{type(a).__name__}:{w:.0%}"
            for a, w in zip(self.anchors, self.anchor_weights())
        )

    def act(self, observations: np.ndarray, action_masks: np.ndarray) -> np.ndarray:
        return self.select().act(observations, action_masks)


OPPONENT_KINDS = ("random", "heuristic", "strategic")


def make_opponent(kind: str, seed: int = 0) -> Opponent:
    """名前から相手方策を作ります。"""
    if kind == "random":
        return RandomOpponent(seed)
    if kind == "heuristic":
        return HeuristicOpponent(seed)
    if kind == "strategic":
        # strategy はカードマスタを読むので、必要になったときだけ import する。
        from godfield_rl.strategy import StrategicOpponent

        return StrategicOpponent(seed)
    raise ValueError(f"未知の相手方策です: {kind!r} ({' / '.join(OPPONENT_KINDS)} のいずれか)")
