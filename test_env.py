import godfield_core
import numpy as np

def main():
    print("Initializing EnvPool...")
    env = godfield_core.EnvPool(10)
    
    print("Resetting envs...")
    env.reset(42)
    
    ready_ids = env.get_ready_env_ids()
    print("Ready IDs:", ready_ids)
    
    obs = env.get_observations()
    print("Observations shape (flat):", obs.shape)
    
    # Each Observation has a fixed size.
    obs_2d = obs.reshape(10, -1)
    print("Observations shape (reshaped):", obs_2d.shape)
    
    actions = np.zeros(len(ready_ids), dtype=np.int32)
    print("Taking step with all zero actions...")
    env.step_all(actions)
    
    obs_after = env.get_observations()
    obs_after_2d = obs_after.reshape(10, -1)
    
    print("Success. Script completed without crashes.")

if __name__ == "__main__":
    main()
