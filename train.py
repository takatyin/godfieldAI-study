import argparse
import os

import torch
from sb3_contrib import MaskablePPO

from sb3_contrib.common.maskable.callbacks import MaskableEvalCallback

from godfield_rl.env_wrapper import GodFieldVectorEnv
from godfield_rl.feature_extractor import GodFieldFeatureExtractor
from godfield_rl.opponents import make_opponent, PoolOpponent
from godfield_rl.callbacks import WinRateCallback, SelfPlayCallback


def main():
    # Limit PyTorch CPU threads to avoid resource contention with C++ OpenMP threads
    torch.set_num_threads(2)

    parser = argparse.ArgumentParser(description="Train GodField RL Agent")
    parser.add_argument("--num-envs", type=int, default=1000, help="Number of parallel environments")
    parser.add_argument("--total-timesteps", type=int, default=5_000_000, help="Total training timesteps")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--lr", type=float, default=5.845e-05, help="Learning rate (Optuna Best)")
    
    # PPO Hyperparameters optimized for high-throughput vectorized environments
    parser.add_argument("--n-steps", type=int, default=256, help="PPO n_steps (per env)")
    parser.add_argument("--batch-size", type=int, default=16384, help="PPO batch size for gradient updates")
    parser.add_argument("--n-epochs", type=int, default=10, help="PPO n_epochs")
    parser.add_argument("--ent-coef", type=float, default=0.00258, help="Entropy coefficient")
    parser.add_argument("--clip-range", type=float, default=0.3, help="PPO clip range")
    parser.add_argument("--gamma", type=float, default=0.995, help="Discount factor")

    parser.add_argument("--self-play", action="store_true", help="Enable Self-Play league training")
    parser.add_argument("--self-play-save-freq", type=int, default=1_000_000, help="Steps between self-play model snapshots")
    parser.add_argument("--worker-id", type=int, default=0, help="Worker ID for distributed league training")

    parser.add_argument(
        "--opponent",
        choices=["heuristic", "random"],
        default="heuristic",
        help="環境内部で相手の手番を指す方策。学習者の勝率がそのまま強さの指標になる",
    )
    # Logging options
    parser.add_argument("--tensorboard-log", type=str, default="logs/tb", help="TensorBoard log directory")
    parser.add_argument("--wandb", action="store_true", help="Enable Weights & Biases logging")
    parser.add_argument("--wandb-project", type=str, default="godfield-rl", help="WandB project name")
    parser.add_argument("--wandb-name", type=str, default=None, help="WandB run name")
    
    args = parser.parse_args()

    run = None
    if args.wandb:
        import wandb
        from wandb.integration.sb3 import WandbCallback
        run_name = args.wandb_name or f"ppo_{args.opponent}_{args.seed}"
        run = wandb.init(
            project=args.wandb_project,
            name=run_name,
            config=vars(args),
            sync_tensorboard=True,
            monitor_gym=True,
            save_code=True,
        )

    print(f"Initializing {args.num_envs} GodField parallel environments in C++...")
    if args.self_play:
        print("Opponent policy: Self-Play Pool (Starting with Heuristic)")
        initial_opponent = make_opponent("heuristic", seed=args.seed)
        pool_opponent = PoolOpponent(opponents=[initial_opponent], seed=args.seed)
        vec_env = GodFieldVectorEnv(args.num_envs, opponent=pool_opponent)
        
        # 評価用の環境 (Heuristic相手の絶対的な強さを測るため)
        eval_env = GodFieldVectorEnv(100, opponent=make_opponent("heuristic", seed=args.seed + 1))
        eval_env.seed(args.seed + 1)
    else:
        print(f"Opponent policy: {args.opponent}")
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
        n_steps=args.n_steps,
        batch_size=args.batch_size,
        n_epochs=args.n_epochs,
        ent_coef=args.ent_coef,
        clip_range=args.clip_range,
        gamma=args.gamma,
        verbose=1,
        device=device,
        seed=args.seed,
        tensorboard_log=args.tensorboard_log,
    )

    callbacks = [WinRateCallback()]
    
    if args.self_play:
        # Self-Playのプール更新コールバック
        selfplay_cb = SelfPlayCallback(
            pool=pool_opponent,
            save_freq=max(1, args.self_play_save_freq // args.num_envs),
            save_path="models/league_pool",  # 全ワーカーで共有するディレクトリ
            worker_id=args.worker_id,
            verbose=1
        )
        callbacks.append(selfplay_cb)
        
        # ベースライン（Heuristic）に対する絶対評価コールバック
        eval_freq = max(1000, 500_000 // args.num_envs)  # 環境数で割ってステップ数に換算
        eval_cb = MaskableEvalCallback(
            eval_env,
            best_model_save_path=f"models/{run_name}/best_model" if args.wandb_name else "models/best_model",
            log_path="logs/eval",
            eval_freq=eval_freq,
            n_eval_episodes=50,
            deterministic=True,
            render=False,
            verbose=1
        )
        callbacks.append(eval_cb)

    if args.wandb:
        callbacks.append(WandbCallback(model_save_path=f"models/{run.id}", verbose=2))

    print(f"Starting training for {args.total_timesteps} timesteps...")
    model.learn(total_timesteps=args.total_timesteps, callback=callbacks)
    
    model.save("godfield_agent")
    print("Training complete! Model saved to godfield_agent.zip")
    
    if args.wandb:
        run.finish()


if __name__ == "__main__":
    main()
