import optuna

def main():
    study = optuna.load_study(study_name='godfield-ppo', storage='sqlite:///optuna_study.db')
    trials = [t for t in study.trials if t.value is not None]
    trials.sort(key=lambda t: t.value, reverse=True)
    
    print("--- Top 10 Trials ---")
    for i, t in enumerate(trials[:10]):
        print(f"Rank {i+1} (Trial {t.number}): Win Rate {t.value:.4f}")
        for k, v in t.params.items():
            if isinstance(v, float):
                print(f"  {k}: {v:.6f}")
            else:
                print(f"  {k}: {v}")
        print()

if __name__ == "__main__":
    main()
