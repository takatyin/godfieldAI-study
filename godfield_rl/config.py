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

# リーグの共有プール。観測のレイアウトか特徴抽出器を変えたら過去のモデルは
# 読めなくなるので、そのたびに新しいディレクトリへ移すこと（古いプールに書き足すと、
# 読めないモデルが混ざったまま気付きにくい）。
#
# **run_league.sh の POOL_DIR と必ず揃えること。** 片方だけ更新すると、
# スクリプト経由と train.py 直叩きで別のプールを使うことになる。
# 各版で何が変わったかは docs/rl_history.md にある。
DEFAULT_POOL_DIR = "models/league_v5"


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
    # 1ロールアウトあたりの勾配更新回数は rollout/batch_size * n_epochs で決まる。
    # batch_size を VRAM だけで決めると、大きいモデルほど更新回数が跳ね上がる:
    #   batch 8192 -> 16 ミニバッチ x 10 =  160 更新（approx_kl 0.025）
    #   batch 2048 -> 63 ミニバッチ x 10 =  630 更新（approx_kl 0.42）
    #   batch 1024 -> 125 ミニバッチ x 10 = 1250 更新（approx_kl 0.35, clip率 0.47）
    # approx_kl が 0.4 では方策が信頼領域を大きく外れ、重要度比のクリップばかりが
    # 効いて学習が進まない。target_kl を超えた時点で epoch ループを打ち切ることで、
    # batch_size をいくつにしても更新量が揃う。0以下で無効。
    target_kl: float = 0.03
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
    # 逆伝播用に保持する層ごとの活性を捨て、必要になった時点で再計算する。
    # 逆伝播が約1.3倍になる代わりに、大きいモデルでも batch_size を上げられる。
    # batch_size を VRAM の都合で下げると更新回数が跳ね上がるため（target_kl の
    # コメント参照）、そちらを避けるための手段。
    grad_checkpointing: bool = False

    # --- 対戦相手 ----------------------------------------------------------
    opponent: str = "strategic"
    self_play: bool = False
    self_play_save_freq: int = 1_000_000
    pool_dir: str = DEFAULT_POOL_DIR
    worker_id: int = 0
    start_opponent_model: str | None = None

    # 自己対戦中、固定の相手（--opponent の方策）と当たる割合。
    #
    # 以前は「人手の戦略1体 + 自分の過去5体」を一様に選んでいたため約17%でした。
    # 自分の過去は自分と同じ弱点を持つので、その弱点が罰されません。実測では
    # 37M ステップ学習しても「買う」を選ぶ確率が所持金にほとんど反応せず、
    # gen4 から gen36 まで数値が動きませんでした。
    anchor_ratio: float = 0.5

    # 固定の相手を弱い順に並べたもの（カンマ区切り）。最後は opponent と揃えること。
    #
    # 初期化直後のネットの勝率は 対 random 49.4% / 対 heuristic 26.0% /
    # 対 strategic 3.3% で、最強の相手だけで始めると勝敗がほぼ定数になり、
    # 行動の良し悪しが差として出ません。しかも分身が現れるのは最初の保存
    # （self_play_save_freq）以降なので、それまでは錨が100%を占めます。
    anchor_kinds: str = "heuristic,strategic"

    # 学習の何割の時点で、錨が最強のものだけ（比率1）になるか。
    # 実測ではこの課題の学習は 10M ステップまでに大半が終わるので、
    # 50M なら 0.3（=15M）で移行を終える。
    anchor_curriculum_end: float = 0.3

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
        if not 0.0 <= self.anchor_ratio <= 1.0:
            raise ValueError(
                f"anchor_ratio は 0..1 で指定してください: {self.anchor_ratio}"
            )
        if not 0.0 <= self.anchor_curriculum_end <= 1.0:
            raise ValueError(
                "anchor_curriculum_end は 0..1 で指定してください: "
                f"{self.anchor_curriculum_end}"
            )


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
    "target_kl": "方策の変化がこれを超えたら更新を打ち切る（0以下で無効）",
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
    "grad_checkpointing": "活性を保持せず再計算してVRAMを削る（逆伝播が約1.3倍）",
    "opponent": "環境内部で相手の手番を指す方策",
    "self_play": "自己対戦リーグを有効にする",
    "self_play_save_freq": "何ステップごとにモデルをプールへ保存するか",
    "pool_dir": "リーグのモデルを置く共有ディレクトリ",
    "worker_id": "リーグのワーカー番号",
    "start_opponent_model": "初期対戦相手にする学習済みモデル（.zip）",
    "anchor_ratio": "自己対戦中に固定の相手と当たる割合",
    "anchor_kinds": "固定の相手を弱い順に並べたもの（カンマ区切り。最後は --opponent と同じに）",
    "anchor_curriculum_end": "学習の何割の時点で最強の固定相手だけになるか（0で最初から最強のみ）",
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
