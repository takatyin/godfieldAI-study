import torch
from stable_baselines3 import PPO

from godfield_rl.env_wrapper import GodFieldVectorEnv


def main():
    num_envs = 1000  # High throughput for GPU!
    print(f"Initializing {num_envs} GodField parallel environments in C++...")

    vec_env = GodFieldVectorEnv(num_envs)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Setting up PPO model on {device}...")

    model = PPO("MlpPolicy", vec_env, verbose=1, device=device)

    print("Ready to start training! Run model.learn() to train.")
    # model.learn(total_timesteps=1_000_000)


if __name__ == "__main__":
    main()
