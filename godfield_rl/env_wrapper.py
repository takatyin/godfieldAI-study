import gymnasium as gym
import numpy as np
from gymnasium.spaces import Box, Discrete

try:
    import godfield_core
except ImportError:
    raise ImportError("godfield_core is not built. Please run 'pip install -e .'")


class GodFieldVectorEnv(gym.vector.VectorEnv):
    """
    GodField game environment implementing Gymnasium VectorEnv interface.
    This wrapper leverages C++ EnvPool for massively parallel game simulation
    and self-play state transition handling.
    """
    def __init__(self, num_envs: int):
        # Observation is a flat vector of OBSERVATION_FEATURE_SIZE floats, excluding padding
        observation_space = Box(
            low=-np.inf, 
            high=np.inf, 
            shape=(godfield_core.OBSERVATION_FEATURE_SIZE,), 
            dtype=np.float32
        )
        # Action space has 122 discrete choices (ActionType enum options)
        action_space = Discrete(122)
        
        # Manually initialize attributes to support newer Gymnasium VectorEnv specifications
        self.num_envs = num_envs
        self.observation_space = observation_space
        self.action_space = action_space
        self.single_observation_space = Box(
            low=-np.inf,
            high=np.inf,
            shape=(godfield_core.OBSERVATION_FEATURE_SIZE,),
            dtype=np.float32
        )
        self.single_action_space = Discrete(122)
        
        super().__init__()

        self.core_env = godfield_core.EnvPool(num_envs)
        self.seed_val = 42

    def reset(self, *, seed=None, options=None):
        """
        Resets all parallel environments in the pool.
        """
        super().reset(seed=seed)
        if seed is not None:
            self.seed_val = seed
            
        self.core_env.reset(self.seed_val)
        
        # Fetch the flat zero-copy observations and reshape to batch format
        obs_flat = self.core_env.get_observations()
        obs_raw = obs_flat.reshape(self.num_envs, godfield_core.OBSERVATION_SIZE)
        obs = obs_raw[:, :godfield_core.OBSERVATION_FEATURE_SIZE].copy()
        
        self._last_obs = obs.copy()
        return obs, {}

    def step(self, actions):
        """
        Steps all environments simultaneously with the provided actions.
        actions: a numpy array of shape (num_envs,) with integer action indices.
        """
        # Cache the observation prior to stepping (used for final_observation)
        last_obs = self._last_obs.copy()

        # Call C++ parallel stepping
        self.core_env.step_all(np.array(actions, dtype=np.int32))
        
        # Retrieve batch data from zero-copy arrays
        obs_flat = self.core_env.get_observations()
        obs_raw = obs_flat.reshape(self.num_envs, godfield_core.OBSERVATION_SIZE)
        obs = obs_raw[:, :godfield_core.OBSERVATION_FEATURE_SIZE].copy()
        self._last_obs = obs.copy()
        
        rewards = self.core_env.get_rewards().copy()
        terminated = self.core_env.get_dones().astype(bool).copy()
        
        truncated = np.zeros(self.num_envs, dtype=bool)
        
        # info must contain placeholder dictionaries for each environment
        info = {
            "_terminated": terminated,
            "_truncated": truncated,
        }

        # Populate final_observation for terminated environments
        if np.any(terminated):
            info["final_observation"] = np.empty(self.num_envs, dtype=object)
            info["final_info"] = np.empty(self.num_envs, dtype=object)
            for i, done in enumerate(terminated):
                if done:
                    info["final_observation"][i] = last_obs[i]
                    info["final_info"][i] = {}
        
        return obs, rewards, terminated, truncated, info
