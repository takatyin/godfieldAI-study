import gymnasium as gym
import numpy as np
from gymnasium.spaces import Box, MultiDiscrete

try:
    import godfield_core
except ImportError:
    raise ImportError("godfield_core is not built. Please run 'pip install -e .'")


class GodFieldVectorEnv(gym.vector.VectorEnv):
    def __init__(self, num_envs: int):
        # 30 floats: 5 stats + 5 miracles + 10 hand + 5 opp stats + 5 opp miracles
        observation_space = Box(low=0, high=9999, shape=(30,), dtype=np.float32)
        # Action: 4 indices (e.g., up to 4 cards combined, 0=None). Up to 500 cards.
        action_space = MultiDiscrete([500, 500, 500, 500])
        super().__init__(num_envs, observation_space, action_space)

        self.core_env = godfield_core.VectorEnv(num_envs)

        # Zero-copy buffers
        self._obs_p0 = np.zeros((num_envs, 30), dtype=np.float32)
        self._obs_p1 = np.zeros((num_envs, 30), dtype=np.float32)
        self._rewards_p0 = np.zeros((num_envs,), dtype=np.float32)
        self._rewards_p1 = np.zeros((num_envs,), dtype=np.float32)
        self._dones = np.zeros((num_envs,), dtype=bool)

    def reset(self, *, seed=None, options=None):
        self.core_env.reset(self._obs_p0, self._obs_p1)
        # We return a view/copy of player 0's observation
        return self._obs_p0.copy(), {}

    def step(self, actions):
        """
        actions: numpy array of shape (num_envs, 4)
        """
        # Placeholder for opponent actions (random actions for now)
        actions_p1 = np.random.randint(0, 500, size=(self.num_envs, 4), dtype=np.int32)
        actions_p0 = np.array(actions, dtype=np.int32)

        # C++ extension call (fills the zero-copy buffers)
        self.core_env.step(
            actions_p0,
            actions_p1,
            self._obs_p0,
            self._obs_p1,
            self._rewards_p0,
            self._rewards_p1,
            self._dones,
        )

        info = {}
        # In stable-baselines3, vectorized envs don't need manual resets,
        # but our C++ implementation automatically resets done environments anyway!

        return (
            self._obs_p0.copy(),
            self._rewards_p0.copy(),
            self._dones.copy(),
            np.zeros_like(self._dones),
            info,
        )
