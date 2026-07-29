import torch
import gymnasium as gym
import numpy as np

try:
    import godfield_core
    # Mock registry so tests can run
    godfield_core.init_game_logic([{"id": 0, "name": "dummy", "drop_rate": 1}])
except ImportError:
    pass

from godfield_rl.feature_extractor import GodFieldTransformerExtractor
from godfield_rl.feature_config import TOTAL_OBSERVATION_FEATURE_SIZE_NO_MASK

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
