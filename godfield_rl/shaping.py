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

import numpy as np

# HP / MP / お金 の上限。観測の正規化（/100）と揃える必要はなく、
# ここでは「差が最大でも ±1 程度になる」ようにするための除数。
STAT_SCALE = 99.0


@dataclass(frozen=True)
class PotentialShaper:
    """Φ(s) = Σ w_k · (自分の資源k − 相手の資源k) / 99 を計算します。

    Args:
        hp: HP差の重み。まずはここだけを使うことを推奨します。
        mp: MP差の重み。「温存するほど良い」と教えかねないので小さく。
        money: 所持金差の重み。同上。
        gamma: 割引率。PPO の gamma と必ず同じ値にしてください。ずれると
            打ち消し合いが崩れ、最適方策が変わらないという保証が失われます。
    """

    hp: float = 0.2
    mp: float = 0.0
    money: float = 0.0
    gamma: float = 0.995

    @property
    def enabled(self) -> bool:
        return self.hp != 0.0 or self.mp != 0.0 or self.money != 0.0

    def potential(self, stats: np.ndarray, learner_seat: int) -> np.ndarray:
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
        return diff @ weights

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


def make_shaper(hp: float, mp: float, money: float, gamma: float) -> PotentialShaper | None:
    """重みがすべて0なら None を返します（シェーピングなし）。"""
    shaper = PotentialShaper(hp=hp, mp=mp, money=money, gamma=gamma)
    return shaper if shaper.enabled else None
