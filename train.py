import argparse

import torch
from sb3_contrib import MaskablePPO

from godfield_rl.env_wrapper import GodFieldVectorEnv
from godfield_rl.feature_extractor import GodFieldFeatureExtractor
from godfield_rl.opponents import make_opponent


def main():
    # Limit PyTorch CPU threads to avoid resource contention with C++ OpenMP threads
    torch.set_num_threads(2)

    parser = argparse.ArgumentParser(description="Train GodField RL Agent")
    parser.add_argument("--num-envs", type=int, default=1000, help="Number of parallel environments")
    parser.add_argument("--total-timesteps", type=int, default=1_000_000, help="Total training timesteps")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--lr", type=float, default=3e-4, help="Learning rate")
    parser.add_argument(
        "--opponent",
        choices=["heuristic", "random"],
        default="heuristic",
        help="環境内部で相手の手番を指す方策。学習者の勝率がそのまま強さの指標になる",
    )
    args = parser.parse_args()

    print(f"Initializing {args.num_envs} GodField parallel environments in C++...")
    print(f"Opponent policy: {args.opponent}")
    # 相手の手番は環境の内部で消化され、SB3 には学習者の意思決定点だけが見える。
    # これにより PPO のロールアウトが単一エージェントのものになる（GAE の符号問題を回避）。
    vec_env = GodFieldVectorEnv(args.num_envs, opponent=make_opponent(args.opponent, seed=args.seed))
    vec_env.seed(args.seed)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Setting up MaskablePPO model on {device}...")

    policy_kwargs = dict(
        features_extractor_class=GodFieldFeatureExtractor,
        features_extractor_kwargs=dict(
            card_embed_dim=16,
            features_dim=256,
        ),
    )

    model = MaskablePPO(
        "MlpPolicy",
        vec_env,
        policy_kwargs=policy_kwargs,
        learning_rate=args.lr,
        verbose=1,
        device=device,
        seed=args.seed,
    )

    print(f"Starting training for {args.total_timesteps} timesteps...")
    model.learn(total_timesteps=args.total_timesteps)
    model.save("godfield_agent")
    print("Training complete! Model saved to godfield_agent.zip")


if __name__ == "__main__":
    main()
