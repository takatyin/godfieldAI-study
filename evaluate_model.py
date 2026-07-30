import argparse

from sb3_contrib import MaskablePPO
from tqdm import tqdm

from godfield_rl.env_wrapper import GodFieldVectorEnv
from godfield_rl.feature_extractor import GodFieldFeatureExtractor, GodFieldTransformerExtractor
from godfield_rl.opponents import OPPONENT_KINDS, make_opponent


def main():
    parser = argparse.ArgumentParser(description="Evaluate GodField RL Agent")
    parser.add_argument("model_path", type=str, help="Path to the trained model (.zip)")
    parser.add_argument("--use-transformer", action="store_true", help="Set if the model is a Transformer")
    parser.add_argument("--opponent", choices=list(OPPONENT_KINDS), default="heuristic", help="Opponent to evaluate against")
    parser.add_argument("--episodes", type=int, default=1000, help="Number of episodes to evaluate")
    parser.add_argument("--num-envs", type=int, default=100, help="Number of parallel environments")
    args = parser.parse_args()

    print(f"Loading model from {args.model_path}...")

    if args.use_transformer:
        custom_objects = {
            "features_extractor_class": GodFieldTransformerExtractor,
        }
    else:
        custom_objects = {
            "features_extractor_class": GodFieldFeatureExtractor,
        }

    model = MaskablePPO.load(args.model_path, device="cuda", custom_objects=custom_objects)

    print(f"Initializing {args.num_envs} environments playing against {args.opponent}...")
    env = GodFieldVectorEnv(args.num_envs, opponent=make_opponent(args.opponent, seed=42))

    obs = env.reset()

    wins = 0
    losses = 0
    draws = 0
    episodes = 0

    pbar = tqdm(total=args.episodes, desc="Evaluating")

    while episodes < args.episodes:
        action_masks = env.action_masks()
        actions, _ = model.predict(obs, action_masks=action_masks, deterministic=True)
        obs, rewards, dones, infos = env.step(actions)

        for i in range(args.num_envs):
            if dones[i]:
                episodes += 1
                if rewards[i] == 1.0:
                    wins += 1
                elif rewards[i] == -1.0:
                    losses += 1
                else:
                    draws += 1
                pbar.update(1)

                if episodes >= args.episodes:
                    break

    pbar.close()

    win_rate = wins / args.episodes
    loss_rate = losses / args.episodes
    draw_rate = draws / args.episodes

    print("\n--- Evaluation Results ---")
    print(f"Opponent: {args.opponent}")
    print(f"Total Episodes: {args.episodes}")
    print(f"Wins:   {wins} ({win_rate*100:.1f}%)")
    print(f"Losses: {losses} ({loss_rate*100:.1f}%)")
    print(f"Draws:  {draws} ({draw_rate*100:.1f}%)")

if __name__ == "__main__":
    main()
