"""報酬シェーピング（ポテンシャルベース）。

## なぜポテンシャルベースなのか

終端の勝敗（±1）だけでは、1手ごとの良し悪しが学習者に伝わりません。実際、
gen50 のモデルは対象選択フェイズで 100%「相手」を選ぶまで潰れており、回復系の
雑貨を相手に使っていました（`tools/diagnose_policy.py` で確認できます）。

ここで素朴に「相手を回復させたら減点」のような報酬を足すと、**最適方策そのものが
変わってしまいます**。勝つことより減点を避けることを学ぶ余地が生まれるからです。

ポテンシャルベースのシェーピング（PBRS）はその心配がありません。状態だけの関数
Φ(s) を用意して

    r' = r + γ·Φ(s') − Φ(s)

の形にすると、経路上の Φ が打ち消し合って合計が `γ^T·Φ(s_T) − Φ(s_0)` にしかならず、
**最適方策は元の報酬と完全に一致する**ことが証明されています
（Ng, Harada & Russell 1999）。つまり「シェーピングを稼いで勝たない」方策は
原理的に得をしません。報酬ハッキングの心配があるのは、この形でない場合です。

## ただし万能ではない

PBRS が保証するのは**最適方策が変わらないこと**だけで、有限時間の学習が
どこへ収束するかまでは保証しません。Φ の形が悪いと、悪い癖を早く覚えます。

- **HP差**: 勝敗に直結し、ゼロサム。安全な軸
- **MP・お金**: 奇跡を撃つ／取引するための資源であって、多いほど良いわけではない。
  重みを大きくすると「温存するほど良い」と誤って教える。既定は 0

いずれも必ず「自分 − 相手」の差にします。絶対値だと双方が伸びる局面まで報われます。

## 真の状態を使う理由

Φ は観測ではなく `EnvPool.get_player_stats()`（真の値）から作ります。観測は霧が
かかると相手の HP/MP/お金が 0 に潰れるため、そこからポテンシャルを作ると
**霧の付与・解除だけで巨大な偽の報酬**が出ます。学習者が見るのはあくまで観測で、
報酬の計算にだけ真の状態を使う、という切り分けです（学習時の特権情報であり、
方策には渡りません）。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch

from godfield_rl.hand_value_model import HandValueModel

# HP / MP / お金 の上限。観測の正規化（/100）と揃える必要はなく、
# ここでは「差が最大でも ±1 程度になる」ようにするための除数。
STAT_SCALE = 99.0

# HandValueModel の potential には HP 差由来の変化が重複して含まれている。
# hand_value_model_2/best_model.pt と、その学習に使った dataset の episode 単位
# validation split で
#
#   ΔΦ_NN = intercept + BETA * ΔΦ_HP + residual
#
# を最小二乗回帰して得た傾き。ここで Φ_NN は [-1, 1] clip 後、Φ_HP は
# (learner_hp - opponent_hp) / STAT_SCALE である。切片 -0.009846 は HP と
# 共変する成分ではないため引かない。checkpoint や clip 幅を変更した場合は、
# 同じ validation 手順でこの値を再推定すること。
HAND_VALUE_HP_RESIDUAL_BETA = 0.524088152132

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HAND_VALUE_MODEL_DIR = REPO_ROOT / "runs" / "hand_value_model"


@dataclass(frozen=True)
class PotentialShaper:
    """Φ(s) = Σ w_k · (自分の資源k − 相手の資源k) / 99 を計算します。

    Args:
        hp: HP差の重み。まずはここだけを使うことを推奨します。
        mp: MP差の重み。「温存するほど良い」と教えかねないので小さく。
        money: 所持金差の重み。同上。
        hand: 手札価値の重み(手札価値は実装予定)
        gamma: 割引率。PPO の gamma と必ず同じ値にしてください。ずれると
            打ち消し合いが崩れ、最適方策が変わらないという保証が失われます。
        hand_value_shaper: HandValueModel によるポテンシャル。指定した場合は
            `alpha * Φ_hand` を資源ポテンシャルへ加算します。合成後の shaping には
            このクラスの gamma が共通して使われます。
    """

    hp: float = 0.2
    mp: float = 0.0
    money: float = 0.0
    hand: float = 0.0
    gamma: float = 0.995
    hand_value_shaper: HandValuePotentialShaper | None = None

    @property
    def enabled(self) -> bool:
        return (
            self.hp != 0.0
            or self.mp != 0.0
            or self.money != 0.0
            or self.hand != 0.0
            or self.hand_value_shaper is not None
        )

    def potential(
        self,
        stats: np.ndarray,
        learner_seat: int,
        my_hands: np.ndarray | None = None,
        opp_hands: np.ndarray | None = None,
        obs: np.ndarray | None = None,
    ) -> np.ndarray:
        """Args:
            stats: (環境数, 6) の [p0_hp, p0_mp, p0_money, p1_hp, p1_mp, p1_money]。
            learner_seat: 学習者の席。
        Returns:
            (環境数,) の float32。
        """
        me = 0 if learner_seat == 0 else 3
        opp = 3 - me
        s = stats.astype(np.float32)
        diff = (s[:, me : me + 3] - s[:, opp : opp + 3]) / STAT_SCALE
        weights = np.array([self.hp, self.mp, self.money], dtype=np.float32)
        phi = diff @ weights

        if self.hand_value_shaper is not None:
            if obs is None or my_hands is None or opp_hands is None:
                raise ValueError(
                    "obs, my_hands, and opp_hands are required when "
                    "hand_value_shaper is enabled"
                )
            hand_phi = self.hand_value_shaper.potential(
                obs,
                stats,
                my_hands,
                opp_hands,
            )
            # NN potential から HP potential と線形に重複する変化を除き、
            # shape_hp と shape_hand が同じ HP 報酬を二重に与えないようにする。
            hp_residualized_hand_phi = (
                hand_phi - HAND_VALUE_HP_RESIDUAL_BETA * diff[:, 0]
            )
            phi = (
                phi
                + self.hand_value_shaper.alpha * hp_residualized_hand_phi
            )

        return phi.astype(np.float32, copy=False)

    def shape(
        self,
        prev_potential: np.ndarray,
        next_potential: np.ndarray,
        terminated: np.ndarray,
    ) -> np.ndarray:
        """r' に加算する分 `γ·Φ(s') − Φ(s)` を返します。

        終端では Φ(s') を 0 として扱います。終端状態から先は遷移が無いため、
        ここに値を残すと「終わり方」に応じた偏りが入り、PBRS の保証が崩れます。
        （実装上も、自動リセット後の新しい局の Φ を拾ってしまう事故を防げます。）
        """
        next_phi = np.where(terminated, 0.0, next_potential)
        return (self.gamma * next_phi - prev_potential).astype(np.float32)


@dataclass
class HandValuePotentialShaper:
    """学習済み HandValueModel の予測値をポテンシャル Φ(s) として使います。"""

    model: HandValueModel
    gamma: float = 0.995
    alpha: float = 0.2
    device: str = "cpu"
    clip_value: float | None = 1.0

    def __post_init__(self) -> None:
        if self.clip_value is not None and self.clip_value <= 0:
            raise ValueError("clip_value must be positive or None")
        self.model.to(self.device)
        self.model.eval()

    def potential(
        self,
        obs: np.ndarray,
        stats: np.ndarray,
        my_hands: np.ndarray,
        opp_hands: np.ndarray,
    ) -> np.ndarray:
        """モデルでバッチのポテンシャルを推論し、shape (B,) で返します。"""
        obs_tensor = torch.as_tensor(obs, dtype=torch.float32, device=self.device)
        stats_tensor = torch.as_tensor(stats, dtype=torch.float32, device=self.device)
        my_hands_tensor = torch.as_tensor(
            my_hands, dtype=torch.long, device=self.device
        )
        opp_hands_tensor = torch.as_tensor(
            opp_hands, dtype=torch.long, device=self.device
        )

        with torch.no_grad():
            value = self.model(
                obs_tensor,
                stats_tensor,
                my_hands_tensor,
                opp_hands_tensor,
            )
            if self.clip_value is not None:
                phi = torch.clamp(
                    value,
                    min=-self.clip_value,
                    max=self.clip_value,
                )
            else:
                phi = value

        return phi.detach().cpu().numpy().astype(np.float32, copy=False)

    def shape(
        self,
        prev_potential: np.ndarray,
        next_potential: np.ndarray,
        terminated: np.ndarray,
    ) -> np.ndarray:
        """alpha * (gamma * Φ(s') - Φ(s)) を返します。"""
        next_phi = np.where(terminated, 0.0, next_potential)
        return (
            self.alpha * (self.gamma * next_phi - prev_potential)
        ).astype(np.float32)


def load_latest_hand_value_model(
    model_dir: Path = DEFAULT_HAND_VALUE_MODEL_DIR,
    device: str = "cpu",
) -> HandValueModel:
    """最新の連番runにある best_model.pt からモデルを復元します。"""
    model_dir = Path(model_dir).expanduser().resolve()
    candidates: list[tuple[int, Path]] = []
    for path in model_dir.glob("hand_value_model_*"):
        suffix = path.name.removeprefix("hand_value_model_")
        if path.is_dir() and suffix.isdigit():
            candidates.append((int(suffix), path))

    if not candidates:
        raise FileNotFoundError(
            f"hand value model run not found under: {model_dir}"
        )

    _, latest_run = max(candidates, key=lambda item: item[0])
    checkpoint_path = latest_run / "best_model.pt"
    if not checkpoint_path.is_file():
        raise FileNotFoundError(
            f"best hand value model not found: {checkpoint_path}"
        )

    checkpoint = torch.load(
        checkpoint_path,
        map_location=device,
        weights_only=True,
    )
    if not isinstance(checkpoint, dict):
        raise ValueError(f"invalid checkpoint format: {checkpoint_path}")

    model_config = checkpoint.get("model_config")
    model_state_dict = checkpoint.get("model_state_dict")
    if not isinstance(model_config, dict) or not isinstance(model_state_dict, dict):
        raise ValueError(
            "checkpoint must contain model_config and model_state_dict: "
            f"{checkpoint_path}"
        )

    model = HandValueModel(**model_config)
    model.load_state_dict(model_state_dict)
    model.to(device)
    model.eval()
    return model


def make_shaper(
    hp: float,
    mp: float,
    money: float,
    gamma: float,
    hand: float = 0.0,
    *,
    hand_value_model_dir: Path = DEFAULT_HAND_VALUE_MODEL_DIR,
    hand_device: str = "cpu",
    hand_clip_value: float | None = 1.0,
) -> PotentialShaper | None:
    """設定からshaperを作り、hand有効時は最新のbest modelを読み込みます。"""
    hand_value_shaper = None
    if hand != 0.0:
        model = load_latest_hand_value_model(
            model_dir=hand_value_model_dir,
            device=hand_device,
        )
        hand_value_shaper = HandValuePotentialShaper(
            model=model,
            gamma=gamma,
            alpha=hand,
            device=hand_device,
            clip_value=hand_clip_value,
        )

    shaper = PotentialShaper(
        hp=hp,
        mp=mp,
        money=money,
        hand=hand,
        gamma=gamma,
        hand_value_shaper=hand_value_shaper,
    )
    return shaper if shaper.enabled else None
