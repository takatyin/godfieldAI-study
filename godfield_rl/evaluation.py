"""対戦させて勝率を測るための共通処理。

同じ「N局まわして勝敗を数える」ループが evaluate_model.py・
tools/diagnose_policy.py・tools/compare_opponents.py に3つ別々に書かれていました。
勝敗の数え方や席の扱いが少しずつ違い、出てくる数字を突き合わせられませんでした。

ここに1つだけ置きます。学習済みモデルも人手の方策も同じ `Opponent`
（act(観測, マスク) のバッチ受け取り）として扱えるので、区別せずに戦わせられます。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

import godfield_core
from godfield_rl.cards import all_cards
from godfield_rl.opponents import FrozenOpponent, Opponent, make_opponent


@dataclass(frozen=True)
class MatchResult:
    """席0から見た結果。"""

    games: int
    wins: int
    losses: int
    draws: int

    @property
    def win_rate(self) -> float:
        return self.wins / self.games if self.games else float("nan")

    @property
    def loss_rate(self) -> float:
        return self.losses / self.games if self.games else float("nan")

    @property
    def draw_rate(self) -> float:
        return self.draws / self.games if self.games else float("nan")

    def __str__(self) -> str:
        return (f"{self.games}局  勝 {self.win_rate:.1%} / 負 {self.loss_rate:.1%}"
                f" / 分 {self.draw_rate:.1%}")


def split_observation(raw: np.ndarray, num_envs: int) -> tuple[np.ndarray, np.ndarray]:
    """EnvPool の生の観測を (特徴量, 合法手マスク) に分けます。

    この切り出しは env_wrapper・可視化サーバー・各ツールで繰り返し書かれていました。
    """
    fdim = godfield_core.OBSERVATION_FEATURE_SIZE
    adim = godfield_core.ACTION_SPACE_SIZE
    flat = raw.reshape(num_envs, -1)
    return flat[:, : fdim - adim], flat[:, fdim - adim : fdim].astype(bool)


def load_policy(path: str, device: str = "cpu", deterministic: bool = True) -> Opponent:
    """学習済みモデルを対戦相手として読み込みます。

    特徴抽出器の種類やハイパーパラメータは .zip に保存されているので、
    呼び出し側で指定する必要はありません（--use-transformer のような
    「読み込み時に構成を言い直す」引数は不要）。
    """
    from sb3_contrib import MaskablePPO

    try:
        model = MaskablePPO.load(path, device=device)
    except RuntimeError as exc:
        if "size mismatch" not in str(exc):
            raise
        raise RuntimeError(
            f"{path} は今の観測レイアウトでは読めません。\n"
            f"  観測が変わると学習済みモデルは使えなくなります。直近では"
            f" HISTORY_LENGTH を 64 から {godfield_core.HISTORY_LENGTH} に変えており、"
            f"それ以前のモデルは対象外です。\n"
            f"  学習し直したモデルを使ってください。\n"
            f"  元のエラー: {exc}"
        ) from exc
    return FrozenOpponent(model, deterministic=deterministic)


def resolve_policy(spec: str, seed: int = 0, device: str = "cpu") -> Opponent:
    """名前（random/heuristic/strategic）か .zip のパスから方策を作ります。"""
    if spec.endswith(".zip"):
        return load_policy(spec, device=device)
    return make_opponent(spec, seed=seed)


def play_match(
    seat0: Opponent,
    seat1: Opponent,
    *,
    games: int,
    num_envs: int = 64,
    seed: int = 0,
    max_steps_per_game: int = 2000,
) -> MatchResult:
    """2つの方策を戦わせ、席0から見た結果を返します。"""
    all_cards()
    pool = godfield_core.EnvPool(num_envs)
    pool.reset(seed)
    players = {0: seat0, 1: seat1}

    wins = losses = draws = 0
    for step in range(games * max_steps_per_game):
        obs, masks = split_observation(pool.get_observations(), num_envs)
        actors = pool.get_current_actors()

        actions = np.zeros(num_envs, dtype=np.int32)
        for seat, policy in players.items():
            idx = np.flatnonzero(actors == seat)
            if idx.size:
                actions[idx] = policy.act(obs[idx], masks[idx])
        pool.step_all(actions)

        dones = pool.get_dones()
        if dones.any():
            rewards = pool.get_rewards_for(0)
            for i in np.flatnonzero(dones):
                r = rewards[i]
                wins += r > 0
                losses += r < 0
                draws += r == 0
        if wins + losses + draws >= games:
            break
    else:
        raise RuntimeError(
            f"{step + 1} ステップ回しても {games} 局に届きませんでした"
            f"（{wins + losses + draws} 局）。方策が同じ手を返し続けている可能性があります"
        )

    return MatchResult(wins + losses + draws, int(wins), int(losses), int(draws))


def play_both_seats(
    a: Opponent, b: Opponent, *, games: int, num_envs: int = 64, seed: int = 0
) -> tuple[MatchResult, MatchResult, float]:
    """席を入れ替えて2回戦わせ、(順方向, 逆方向, aの平均勝率) を返します。

    先手・後手の有利不利を打ち消すためで、片側だけだと数ポイントずれます。
    """
    fwd = play_match(a, b, games=games, num_envs=num_envs, seed=seed)
    rev = play_match(b, a, games=games, num_envs=num_envs, seed=seed + 1000)
    return fwd, rev, (fwd.win_rate + rev.loss_rate) / 2
