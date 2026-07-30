"""学習の実行入口。

設定は `godfield_rl/config.py`、組み立てと実行は `godfield_rl/training.py` に
あります。このファイルはコマンドラインを読んで渡すだけです。

以前はこのファイルの main() が引数定義・環境構築・モデル構築・コールバック設定を
すべて抱えて200行を超えており、設定を1つ足すたびに伸びていました。

例::

    uv run python train.py --total-timesteps 5000000
    uv run python train.py --self-play --worker-id 0 --seed 42 --pool-dir models/league_v2
    uv run python train.py --no-use-transformer --no-amp    # MLP・fp32 で回す
"""

import argparse

import torch

from godfield_rl.config import add_arguments, from_args
from godfield_rl.training import run


def main() -> None:
    # C++ 側の OpenMP と CPU を取り合わないよう、torch のスレッドを絞る
    torch.set_num_threads(2)

    parser = argparse.ArgumentParser(
        description="GodField の強化学習エージェントを学習する",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    add_arguments(parser)
    run(from_args(parser.parse_args()))


if __name__ == "__main__":
    main()
