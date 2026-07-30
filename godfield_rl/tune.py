import argparse

import optuna
import torch
from sb3_contrib import MaskablePPO
from stable_baselines3.common.callbacks import BaseCallback

from godfield_rl.env_wrapper import GodFieldVectorEnv
from godfield_rl.feature_extractor import GodFieldFeatureExtractor
from godfield_rl.opponents import make_opponent


class OptunaPruningCallback(BaseCallback):
    def __init__(self, trial: optuna.Trial, eval_freq: int, verbose: int = 0):
        super().__init__(verbose)
        self.trial = trial
        self.eval_idx = 0
        self.is_pruned = False
        self.eval_freq = eval_freq
        self.wins = 0
        self.episodes = 0

    def _on_step(self) -> bool:
        if "dones" in self.locals and "rewards" in self.locals:
            dones = self.locals["dones"]
            rewards = self.locals["rewards"]
            for i in range(len(dones)):
                if dones[i]:
                    self.episodes += 1
                    if rewards[i] == 1.0:
                        self.wins += 1

        if self.num_timesteps > 0 and self.num_timesteps % self.eval_freq == 0:
            if self.episodes > 0:
                win_rate = self.wins / self.episodes
                self.trial.report(win_rate, self.eval_idx)
                if self.trial.should_prune():
                    self.is_pruned = True
                    return False
                self.eval_idx += 1
                # 次の期間のためにリセット
                self.wins = 0
                self.episodes = 0
        return True

def objective(trial: optuna.Trial, num_envs: int, total_timesteps: int, seed: int):
    # 探索空間 (Search Space)
    batch_size = trial.suggest_categorical("batch_size", [8192, 16384, 32768, 65536])
    n_steps = trial.suggest_categorical("n_steps", [256, 512, 1024, 2048])
    n_epochs = trial.suggest_categorical("n_epochs", [2, 4, 8, 10])
    learning_rate = trial.suggest_float("learning_rate", 1e-5, 1e-3, log=True)
    ent_coef = trial.suggest_float("ent_coef", 1e-4, 5e-2, log=True)
    clip_range = trial.suggest_categorical("clip_range", [0.1, 0.2, 0.3])
    gamma = trial.suggest_categorical("gamma", [0.99, 0.995, 0.999])

    vec_env = GodFieldVectorEnv(num_envs, opponent=make_opponent("heuristic", seed=seed))
    vec_env.seed(seed)

    policy_kwargs = dict(
        features_extractor_class=GodFieldFeatureExtractor,
        features_extractor_kwargs=dict(card_embed_dim=16, features_dim=256),
    )

    model = MaskablePPO(
        "MlpPolicy",
        vec_env,
        policy_kwargs=policy_kwargs,
        learning_rate=learning_rate,
        n_steps=n_steps,
        batch_size=batch_size,
        n_epochs=n_epochs,
        ent_coef=ent_coef,
        clip_range=clip_range,
        gamma=gamma,
        verbose=0,
        device="cuda" if torch.cuda.is_available() else "cpu",
        seed=seed,
    )

    # 4回の評価期間を設ける（途中経過で勝率が低ければ枝刈り）
    eval_freq = max(total_timesteps // 4, 1)
    callback = OptunaPruningCallback(trial, eval_freq)

    try:
        model.learn(total_timesteps=total_timesteps, callback=callback)
    except AssertionError:
        # 不正なパラメータで発散した場合などはPrune
        raise optuna.exceptions.TrialPruned()

    if callback.is_pruned:
        raise optuna.exceptions.TrialPruned()

    # 最終的な勝率（直近の四半期の勝率）を返す
    win_rate = callback.wins / max(callback.episodes, 1)
    return win_rate

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=20, help="Number of trials per worker")
    parser.add_argument("--num-envs", type=int, default=1000, help="Parallel environments")
    parser.add_argument("--total-timesteps", type=int, default=1_500_000, help="Timesteps per trial")
    parser.add_argument("--seed", type=int, default=42, help="Seed")
    parser.add_argument("--storage", type=str, default="sqlite:///godfield_optuna.db", help="Optuna DB URL")
    parser.add_argument("--study-name", type=str, default="ppo-tuning", help="Optuna Study Name")
    args = parser.parse_args()

    print(f"Starting Optuna Study '{args.study_name}' for {args.trials} trials, {args.total_timesteps} steps each...")
    print(f"Using DB: {args.storage}")

    study = optuna.create_study(
        study_name=args.study_name,
        storage=args.storage,
        load_if_exists=True,
        direction="maximize",
        pruner=optuna.pruners.MedianPruner(n_warmup_steps=1)
    )

    try:
        study.optimize(lambda trial: objective(trial, args.num_envs, args.total_timesteps, args.seed), n_trials=args.trials)
    except KeyboardInterrupt:
        print("Optimization interrupted by user.")

    print("\n===============================")
    print("Number of finished trials: ", len(study.trials))
    try:
        trial = study.best_trial
        print("Best trial:")
        print("  Value (Win Rate): ", trial.value)
        print("  Params: ")
        for key, value in trial.params.items():
            print(f"    {key}: {value}")
    except ValueError:
        print("No trials are completed yet.")
    print("===============================\n")

if __name__ == "__main__":
    main()
