"""学習の設定をひとまとめにしたもの。

以前は `train.py` の `main()` が引数定義・環境構築・モデル構築・コールバック設定を
すべて抱えており、200行を超えていました。設定を足すたびに `main()` が伸び、
「この値がどこで使われるのか」を追うのに関数全体を読む必要がありました。

ここに設定だけを集めて、組み立ては `godfield_rl.training` が受け持ちます。
コマンドライン引数の定義もここに置いてあるので、**設定項目の追加は
このファイルだけで完結**します。
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, fields

from godfield_rl.opponents import OPPONENT_KINDS

# リーグの共有プール。observation のレイアウトを変えたら過去のモデルは読めなく
# なるので、そのたびに新しいディレクトリへ移すこと（古いプールに書き足すと、
# 読めないモデルが混ざったまま気付きにくい）。run_league.sh の既定と揃えてある。
DEFAULT_POOL_DIR = "models/league_v2"


@dataclass(frozen=True)
class TrainingConfig:
    """1回の学習実行を決める設定。"""

    # --- 規模 -------------------------------------------------------------
    num_envs: int = 1000
    total_timesteps: int = 5_000_000
    seed: int = 42

    # --- PPO --------------------------------------------------------------
    lr: float = 5.845e-05
    n_steps: int = 256
    # batch_size は VRAM を決める値で、既定のネットワーク（下の d192 h8 L4）と
    # 対になっている。片方だけ変えると載らなくなるので注意。
    # 24GB での上限は tools/measure_vram.py の実測で
    #   d128 h4 L2  fp32 6,144 / bf16 9,472
    #   d192 h8 L4  fp32 1,792 / bf16 2,816
    #   d256 h8 L6  fp32   768 / bf16 1,536
    batch_size: int = 2048
    n_epochs: int = 10
    # エントロピー係数。以前の 0.00258 では方策が早期に尖り、いちど確率が0に
    # なった行動は二度とサンプルされないので勾配が流れなくなっていた
    # （対象選択が「常に相手」で固まった）。
    ent_coef: float = 0.01
    clip_range: float = 0.3
    gamma: float = 0.995

    # --- 報酬シェーピング（詳細は godfield_rl/shaping.py）-------------------
    shape_hp: float = 0.2
    shape_mp: float = 0.0
    shape_money: float = 0.0

    # --- ネットワーク ------------------------------------------------------
    use_transformer: bool = True
    d_model: int = 192
    nhead: int = 8
    num_layers: int = 4
    dim_feedforward: int = 768
    features_dim: int = 256
    amp: bool = True

    # --- 対戦相手 ----------------------------------------------------------
    opponent: str = "strategic"
    self_play: bool = False
    self_play_save_freq: int = 1_000_000
    pool_dir: str = DEFAULT_POOL_DIR
    worker_id: int = 0
    start_opponent_model: str | None = None

    # --- 記録 --------------------------------------------------------------
    tensorboard_log: str = "logs/tb"
    save_path: str = "godfield_agent"
    wandb: bool = False
    wandb_project: str = "godfield-rl"
    wandb_name: str | None = None

    def __post_init__(self) -> None:
        if self.use_transformer and self.d_model % self.nhead != 0:
            raise ValueError(
                f"d_model({self.d_model}) は nhead({self.nhead}) で割り切れる必要があります"
            )
        if self.batch_size > self.num_envs * self.n_steps:
            raise ValueError(
                f"batch_size({self.batch_size}) が1回のロールアウト"
                f"({self.num_envs * self.n_steps} サンプル)より大きいです"
            )
        if self.opponent not in OPPONENT_KINDS:
            raise ValueError(f"未知の相手方策です: {self.opponent!r}")


# 型ごとの argparse への渡し方。dataclass の定義を唯一の情報源にして、
# 引数定義を二重に書かないようにする。
_HELP = {
    "num_envs": "並列環境数。VRAMではなく主にシステムRAMに効く",
    "total_timesteps": "学習する総ステップ数",
    "seed": "乱数の種。リーグではワーカーごとに変えること",
    "lr": "学習率",
    "n_steps": "1ロールアウトあたりのステップ数（環境ごと）",
    "batch_size": "勾配計算のミニバッチ。VRAMを決めるのはこれ",
    "n_epochs": "1ロールアウトを何周するか",
    "ent_coef": "エントロピー係数。低すぎると方策が早期に潰れて戻れなくなる",
    "clip_range": "PPOのクリップ幅",
    "gamma": "割引率。報酬シェーピングにも同じ値が使われる",
    "shape_hp": "HP差のポテンシャル重み（0で無効）",
    "shape_mp": "MP差のポテンシャル重み。大きくすると温存を覚えるので小さく",
    "shape_money": "所持金差のポテンシャル重み。同上",
    "use_transformer": "Transformerを使う（切るとMLP）",
    "d_model": "Transformerの埋め込み次元（nheadで割り切れること）",
    "nhead": "Transformerのヘッド数",
    "num_layers": "Transformerの層数",
    "dim_feedforward": "Transformerの中間層の幅",
    "features_dim": "方策へ渡す特徴量の次元",
    # ArgumentDefaultsHelpFormatter がヘルプ文字列を % 展開するため、
    # リテラルの % は %% と書く必要がある。
    "amp": "bfloat16の自動混合精度で学習する（VRAM約35%%減・約1.9倍速）",
    "opponent": "環境内部で相手の手番を指す方策",
    "self_play": "自己対戦リーグを有効にする",
    "self_play_save_freq": "何ステップごとにモデルをプールへ保存するか",
    "pool_dir": "リーグのモデルを置く共有ディレクトリ",
    "worker_id": "リーグのワーカー番号",
    "start_opponent_model": "初期対戦相手にする学習済みモデル（.zip）",
    "tensorboard_log": "TensorBoardのログ出力先",
    "save_path": "学習後のモデルの保存先（拡張子なし）",
    "wandb": "Weights & Biases に記録する",
    "wandb_project": "WandBのプロジェクト名",
    "wandb_name": "WandBの実行名",
}


def add_arguments(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """TrainingConfig の各項目を argparse の引数として登録します。"""
    defaults = TrainingConfig()
    for f in fields(TrainingConfig):
        flag = "--" + f.name.replace("_", "-")
        default = getattr(defaults, f.name)
        help_text = _HELP.get(f.name, "")
        if f.type == "bool":
            # 既定が True のものは --no-xxx で切れるようにする
            if default:
                parser.add_argument(
                    "--no-" + f.name.replace("_", "-"), dest=f.name,
                    action="store_false", help=f"{help_text}（既定で有効）",
                )
            else:
                parser.add_argument(flag, dest=f.name, action="store_true", help=help_text)
            parser.set_defaults(**{f.name: default})
        elif f.name == "opponent":
            parser.add_argument(flag, choices=list(OPPONENT_KINDS), default=default, help=help_text)
        else:
            kind = {"int": int, "float": float}.get(f.type, str)
            parser.add_argument(flag, type=kind, default=default, help=help_text)
    return parser


def from_args(args: argparse.Namespace) -> TrainingConfig:
    names = {f.name for f in fields(TrainingConfig)}
    return TrainingConfig(**{k: v for k, v in vars(args).items() if k in names})
