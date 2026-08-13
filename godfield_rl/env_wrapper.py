from typing import Any

import numpy as np
from gymnasium.spaces import Box, Discrete
from stable_baselines3.common.vec_env import VecEnv

try:
    import godfield_core
except ImportError:
    raise ImportError("godfield_core is not built. Please run 'pip install -e .'")

from godfield_rl.cards import all_cards
from godfield_rl.opponents import HeuristicOpponent, Opponent
from godfield_rl.shaping import PotentialShaper

# C++ 側の constants.h を唯一の定義元とする（値をコピーすると観測レイアウトが黙ってズレる）
ACTION_SPACE_SIZE = godfield_core.ACTION_SPACE_SIZE


class GodFieldVectorEnv(VecEnv):
    """学習者を単一エージェントとして見せる VecEnv。

    ゴッドフィールドは2人ゲームですが、SB3 の PPO は単一エージェントMDPを前提にしています。
    手番が交互に現れるロールアウトをそのまま渡すと、GAE が `V(s_{t+1})` に相手視点の価値を
    使ってしまい、ゼロサムでは符号を反転させないと誤った価値目標になります。

    そこで相手の手番は `_advance_opponent_turns()` が環境の内部で消化し、SB3 には
    学習者の意思決定点だけを見せます。相手方策は差し替え可能で、自己対戦へ移行する際は
    凍結した自分のコピーを渡します（強さは維持したまま、データの並びだけを単一化する）。
    """

    def __init__(
        self,
        num_envs: int,
        opponent: Opponent | None = None,
        learner_seat: int = 0,
        shaper: PotentialShaper | None = None,
    ):
        self.num_envs = num_envs
        self.learner_seat = learner_seat
        self.opponent = opponent if opponent is not None else HeuristicOpponent()
        # ポテンシャルベースの報酬シェーピング（None なら終端の勝敗だけ）。
        # 詳細と、なぜこの形でないと最適方策が変わるのかは godfield_rl/shaping.py を参照。
        self.shaper = shaper
        self._prev_potential = np.zeros(num_envs, dtype=np.float32)
        # 相手の手番が終わらない場合に無限ループへ落ちないための上限。
        # 1手番は仮置き→確定など複数ステップになるため、環境数に依らず十分な回数を取る。
        self._max_opponent_steps = 256
        self._obs_dim = godfield_core.OBSERVATION_FEATURE_SIZE - ACTION_SPACE_SIZE
        self._obs_total = godfield_core.OBSERVATION_SIZE  # Total including padding
        self._mask_start = self._obs_dim  # Where action_mask starts in the feature array

        observation_space = Box(low=-np.inf, high=np.inf, shape=(self._obs_dim,), dtype=np.float32)
        action_space = Discrete(ACTION_SPACE_SIZE)

        super().__init__(num_envs, observation_space, action_space)

        # C++ 側の登録簿を初期化する（読み込み済みなら何もしない）
        all_cards()

        self.core_env = godfield_core.EnvPool(num_envs)
        self.seed_val = 42
        self.actions = None
        self._current_masks = None

    def _get_obs_and_masks(self):
        """Extract observations and action masks from C++ buffer."""
        obs_flat = self.core_env.get_observations()
        obs_raw = obs_flat.reshape(self.num_envs, self._obs_total)
        features = obs_raw[:, : godfield_core.OBSERVATION_FEATURE_SIZE]
        obs = features[:, : self._obs_dim].copy()
        masks = features[:, self._mask_start : self._mask_start + ACTION_SPACE_SIZE].copy()
        return obs, masks

    def seed(self, seed: int | None = None) -> list[int | None]:
        """次回 reset() で使用するシードを設定します。

        VecEnv の既定実装は各サブ環境に seed を配る前提で、この実装のように
        C++ 側がシードを一括管理する構成では届きません。override しないと
        MaskablePPO(seed=...) を指定しても環境の乱数が固定値のままになります。
        """
        if seed is not None:
            self.seed_val = seed
        return [seed] * self.num_envs

    def _potential(self) -> np.ndarray:
        """現在の Φ(s)。シェーピングを使わない場合は 0。

        観測ではなく真の状態から作ります。観測は霧がかかると相手の HP/MP/お金が
        0 に潰れるため、そこから作ると霧の付与・解除だけで偽の報酬が出ます。
        """
        if self.shaper is None:
            return self._prev_potential  # 使われないので確保済みのゼロ配列を返す
        return self.shaper.potential(
            self.core_env.get_player_stats(), 
            self.learner_seat,
            my_hands=self.core_env.get_true_hands(self.learner_seat),
            opp_hands=self.core_env.get_true_hands(1-self.learner_seat),
            )

    def reset(self) -> np.ndarray:
        self.core_env.reset(self.seed_val)
        # 開始直後に相手の手番から始まる環境があるため、学習者の手番まで進めてから返す
        self._advance_opponent_turns()
        obs, self._current_masks = self._get_obs_and_masks()
        self._prev_potential = self._potential()
        return obs

    def step_async(self, actions: np.ndarray) -> None:
        self.actions = actions

    def _advance_opponent_turns(self) -> None:
        """相手の手番を環境の内部で消化し、全環境を学習者の手番まで進めます。

        こうすることで SB3 に見えるロールアウトが単一エージェントのものになり、
        連続する遷移が同じエージェントに属します。交互に混ざったままだと GAE が
        相手視点の V(s') を符号反転せずにブートストラップしてしまいます。
        """
        for _ in range(self._max_opponent_steps):
            actors = self.core_env.get_current_actors()
            pending = np.flatnonzero(actors != self.learner_seat)
            if pending.size == 0:
                return

            obs, masks = self._get_obs_and_masks()
            actions = self.opponent.act(obs[pending], masks[pending].astype(bool))
            self.core_env.step_subset(pending.astype(np.int32), actions.astype(np.int32))

        raise RuntimeError("相手の手番が既定回数内に終わりませんでした。進行不能な状態に陥っている可能性があります。")

    def step_wait(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[dict[str, Any]]]:
        self.core_env.step_all(np.array(self.actions, dtype=np.int32))

        # 学習者の手で決着した分を先に確定させる（この後の相手手番の消化で上書きされる前に）
        terminated = self.core_env.get_dones().astype(bool).copy()
        rewards = self.core_env.get_rewards_for(self.learner_seat).copy()
        terminal_raw = self.core_env.get_terminal_observations_for(self.learner_seat).reshape(
            self.num_envs, self._obs_total
        )
        terminal_obs = terminal_raw[:, : self._obs_dim].copy()

        self._advance_opponent_turns()

        # 相手の手で決着した分を取り込む。学習者視点の報酬・終端観測を使う点が重要で、
        # 行動者視点（get_rewards）だと相手が勝ったときに符号が逆になる。
        opp_terminated = self.core_env.get_dones().astype(bool)
        if opp_terminated.any():
            opp_rewards = self.core_env.get_rewards_for(self.learner_seat)
            opp_terminal = self.core_env.get_terminal_observations_for(self.learner_seat).reshape(
                self.num_envs, self._obs_total
            )
            rewards = np.where(opp_terminated, opp_rewards, rewards)
            terminal_obs = np.where(opp_terminated[:, None], opp_terminal[:, : self._obs_dim], terminal_obs)
            terminated |= opp_terminated

        obs, self._current_masks = self._get_obs_and_masks()

        # シェーピングを足す前の勝敗（+1 / -1 / 0）。シェーピングを入れると報酬が
        # ちょうど ±1 でなくなるため、勝率の集計はこちらを見る必要がある。
        outcomes = rewards.copy()

        # ポテンシャルベースのシェーピング。相手の手番まで消化し終えた「次に学習者が
        # 選ぶ局面」で Φ(s') を取る（学習者の遷移は s -> s' なので、その間の相手の
        # 手番も含めて1つの遷移とみなす）。
        if self.shaper is not None:
            next_potential = self._potential()
            rewards = rewards + self.shaper.shape(self._prev_potential, next_potential, terminated)
            # 終端の環境は自動リセット済みなので、次の局の Φ を起点にする
            self._prev_potential = next_potential

        infos: list[dict[str, Any]] = [{} for _ in range(self.num_envs)]
        for i in np.flatnonzero(terminated):
            infos[i]["terminal_observation"] = terminal_obs[i].copy()
            infos[i]["TimeLimit.truncated"] = False
            infos[i]["game_outcome"] = float(outcomes[i])

        return obs, rewards, terminated, infos

    def action_masks(self) -> np.ndarray:
        """Return action masks for MaskablePPO.
        Returns:
            np.ndarray of shape (num_envs, ACTION_SPACE_SIZE) with dtype bool.
        """
        return self._current_masks.astype(bool)

    def get_opponent_true_hands(self) -> np.ndarray:
        """学習者視点の相手の真の手札を Privileged Critic 用に返す。

        通常観測には含めず、PrivilegedMaskablePPO が value を計算するときだけ
        明示的に取得する。形は ``(num_envs, MAX_HAND_SIZE)``。
        """
        return self.core_env.get_opponent_true_hands(self.learner_seat)

    def get_attr(self, attr_name: str, indices=None) -> list[Any]:
        return [getattr(self, attr_name, None)] * len(self._get_indices(indices))

    def set_attr(self, attr_name: str, value: Any, indices=None) -> None:
        setattr(self, attr_name, value)

    def env_method(self, method_name: str, *method_args, indices=None, **method_kwargs) -> list[Any]:
        if method_name == "action_masks":
            masks = self.action_masks()
            return [masks[i] for i in self._get_indices(indices)]
        # このクラスは全環境をC++側の1つのプールで束ねているため、サブ環境ごとの
        # インスタンスが存在しない。指定された数だけ呼び出して、副作用の回数が
        # 呼び出し側の期待とずれないようにする。
        method = getattr(self, method_name)
        return [method(*method_args, **method_kwargs) for _ in self._get_indices(indices)]

    def env_is_wrapped(self, wrapper_class: type, indices=None) -> list[bool]:
        return [False] * len(self._get_indices(indices))

    def close(self) -> None:
        pass
