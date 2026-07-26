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
    """godfield_rl.agents.heuristic_agent と同じ方針をバッチ処理で実装した相手。

    1. 決定系の行動（相手を対象 / 自分を対象・確定）が可能ならそれを優先する
    2. 次に、手札の空でないスロットを選ぶ
    3. どれも該当しなければ合法手からランダムに選ぶ
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


def make_opponent(kind: str, seed: int = 0) -> Opponent:
    """名前から相手方策を作ります。"""
    if kind == "random":
        return RandomOpponent(seed)
    if kind == "heuristic":
        return HeuristicOpponent(seed)
    raise ValueError(f"未知の相手方策です: {kind!r} (random / heuristic のいずれか)")
