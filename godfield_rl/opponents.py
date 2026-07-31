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
    """

    def __init__(self, opponents: list[Opponent] | None = None, seed: int = 0):
        self.opponents = opponents if opponents is not None else []
        self._rng = np.random.default_rng(seed)

    def add_opponent(self, opponent: Opponent):
        self.opponents.append(opponent)

    def act(self, observations: np.ndarray, action_masks: np.ndarray) -> np.ndarray:
        if not self.opponents:
            raise RuntimeError("対戦相手のプールが空です。")
        # プールからランダムに1つの対戦相手を選ぶ
        opponent = self._rng.choice(self.opponents)
        return opponent.act(observations, action_masks)


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
