import gymnasium as gym
import numpy as np
import torch

# 以前ここで init_game_logic([{"id": 0, ...}]) を呼んでダミー1枚の登録簿に
# 差し替えていた。init_game_logic はプロセス全体のグローバルを書き換えるので、
# import された時点で他のテストのカードマスタまで壊れる（実際、テストを
# ディレクトリに分けて実行順が変わった途端に 486 件が落ちた）。
# 登録簿の初期化は conftest の autouse フィクスチャが済ませている。
from godfield_rl.feature_config import TOTAL_OBSERVATION_FEATURE_SIZE_NO_MASK
from godfield_rl.feature_extractor import GodFieldTransformerExtractor


def test_transformer_forward():
    # Create dummy observation space
    obs_dim = TOTAL_OBSERVATION_FEATURE_SIZE_NO_MASK
    observation_space = gym.spaces.Box(
        low=-np.inf, high=np.inf, shape=(obs_dim,), dtype=np.float32
    )

    extractor = GodFieldTransformerExtractor(
        observation_space,
        d_model=64,
        nhead=2,
        num_layers=1,
        features_dim=128
    )

    batch_size = 4
    # Dummy observations (zeros)
    obs = torch.zeros((batch_size, obs_dim), dtype=torch.float32)

    # Forward pass
    features = extractor(obs)

    assert features.shape == (batch_size, 128)
    print("Transformer forward pass successful! Output shape:", features.shape)

if __name__ == "__main__":
    test_transformer_forward()
