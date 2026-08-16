"""設定から学習を組み立てて走らせる。

`train.py` は引数を読んでここを呼ぶだけにしてあります。組み立てを関数に分けて
あるので、ノートブックやテストからも「環境だけ作る」「モデルだけ作る」が
できます。
"""

from __future__ import annotations

import torch
from sb3_contrib import MaskablePPO
from sb3_contrib.common.maskable.callbacks import MaskableEvalCallback
from stable_baselines3.common.callbacks import BaseCallback

import godfield_core
from godfield_rl.amp import policy_class
from godfield_rl.callbacks import SelfPlayCallback, WinRateCallback
from godfield_rl.cards import all_cards
from godfield_rl.config import TrainingConfig
from godfield_rl.env_wrapper import GodFieldVectorEnv
from godfield_rl.feature_extractor import (
    GodFieldFeatureExtractor,
    GodFieldTransformerExtractor,
)
from godfield_rl.opponents import (
    OPPONENT_KINDS,
    FrozenOpponent,
    PoolOpponent,
    make_opponent,
)
from godfield_rl.privileged.policy import privileged_policy_class
from godfield_rl.privileged.ppo import PrivilegedMaskablePPO
from godfield_rl.shaping import make_shaper

EVAL_NUM_ENVS = 100
EVAL_EPISODES = 50
EVAL_EVERY_STEPS = 500_000


def pick_device() -> str:
    return "cuda" if torch.cuda.is_available() else "cpu"


def build_policy_kwargs(cfg: TrainingConfig) -> dict:
    """特徴抽出器の設定。"""
    if not cfg.use_transformer:
        return dict(
            features_extractor_class=GodFieldFeatureExtractor,
            features_extractor_kwargs=dict(
                card_embed_dim=16, features_dim=cfg.features_dim
            ),
        )
    return dict(
        features_extractor_class=GodFieldTransformerExtractor,
        features_extractor_kwargs=dict(
            d_model=cfg.d_model,
            nhead=cfg.nhead,
            num_layers=cfg.num_layers,
            dim_feedforward=cfg.dim_feedforward,
            features_dim=cfg.features_dim,
            grad_checkpointing=cfg.grad_checkpointing,
        ),
    )


def build_opponent(cfg: TrainingConfig, device: str):
    """相手方策を作ります。自己対戦ならプールを、そうでなければ単体を返します。"""
    if not cfg.self_play:
        return make_opponent(cfg.opponent, seed=cfg.seed)

    # 錨は学習を通じて固定の相手。自己対戦だけだと自分の過去としか戦わず、
    # 自分と同じ弱点が一度も罰されない（PoolOpponent の説明を参照）。
    #
    # 弱い順に並べる。初期化直後のネットは人手の戦略に 3.3% しか勝てないため、
    # 最初から最強の相手だけだと勝敗がほぼ定数になり、行動の良し悪しが差として
    # 出ない。進み具合に応じて配分が強い方へ移る。
    anchors = [make_opponent(kind, seed=cfg.seed + i)
               for i, kind in enumerate(anchor_kinds(cfg))]
    if cfg.start_opponent_model:
        # 相手の推論はロールアウト時間の大半を占めるので、学習者と同じデバイスに載せる
        model = MaskablePPO.load(cfg.start_opponent_model, device=device)
        anchors.append(FrozenOpponent(model))
    return PoolOpponent(
        anchors=anchors,
        seed=cfg.seed,
        anchor_ratio=cfg.anchor_ratio,
        curriculum_end=cfg.anchor_curriculum_end,
    )


def anchor_kinds(cfg: TrainingConfig) -> list[str]:
    """錨に使う方策の名前を弱い順に返します。

    `--anchor-kinds` はカンマ区切り。最後（＝最強）は `--opponent` と一致させます。
    評価用の環境が `--opponent` を使うため、ここがずれると「学習の最終目標」と
    「eval が測っているもの」が食い違います。
    """
    kinds = [k.strip() for k in cfg.anchor_kinds.split(",") if k.strip()]
    for kind in kinds:
        if kind not in OPPONENT_KINDS:
            raise ValueError(
                f"--anchor-kinds に未知の方策があります: {kind!r}"
                f"（{' / '.join(OPPONENT_KINDS)} のいずれか）"
            )
    if not kinds:
        return [cfg.opponent]
    if kinds[-1] != cfg.opponent:
        raise ValueError(
            f"--anchor-kinds の最後は --opponent と同じにしてください"
            f"（今は {kinds[-1]!r} と {cfg.opponent!r}）。"
            f" 評価用の環境は --opponent を使うため、ずれると学習の最終目標と"
            f" 評価が食い違います。"
        )
    return kinds


def build_envs(
    cfg: TrainingConfig,
    opponent,
    device: str = "cpu",
) -> tuple[GodFieldVectorEnv, GodFieldVectorEnv | None]:
    """学習用と評価用の環境を作ります。

    評価用にはシェーピングを入れません。見たいのは「勝てるか」だけで、
    シェーピングぶんが混ざると勝率以外の量を見ることになります。
    """
    shaper = make_shaper(
        hp=cfg.shape_hp,
        mp=cfg.shape_mp,
        money=cfg.shape_money,
        gamma=cfg.gamma,
        hand=cfg.shape_hand,
        hand_value_model_dir=cfg.hand_value_model_dir,
        hand_device=device,
        hand_clip_value=cfg.hand_value_clip_value,
    )
    train_env = GodFieldVectorEnv(
        cfg.num_envs, opponent=opponent, shaper=shaper
    )
    train_env.seed(cfg.seed)

    if not cfg.self_play:
        return train_env, None

    eval_env = GodFieldVectorEnv(
        EVAL_NUM_ENVS, opponent=make_opponent(cfg.opponent, seed=cfg.seed + 1)
    )
    eval_env.seed(cfg.seed + 1)
    return train_env, eval_env


def build_model(cfg: TrainingConfig, env: GodFieldVectorEnv, device: str) -> MaskablePPO:
    """設定に応じて通常 PPO または Privileged Critic 版を組み立てる。"""

    if cfg.privileged_critic:
        # rollout buffer と value 計算の両方が privileged 情報に対応した組を使う。
        model_class = PrivilegedMaskablePPO
        policy = privileged_policy_class(cfg.amp)
    else:
        # 比較対象の baseline は従来の MaskablePPO / policy をそのまま使う。
        model_class = MaskablePPO
        policy = policy_class(cfg.amp)
    return model_class(
        policy,
        env,
        policy_kwargs=build_policy_kwargs(cfg),
        learning_rate=cfg.lr,
        n_steps=cfg.n_steps,
        batch_size=cfg.batch_size,
        n_epochs=cfg.n_epochs,
        target_kl=cfg.target_kl if cfg.target_kl > 0 else None,
        ent_coef=cfg.ent_coef,
        clip_range=cfg.clip_range,
        gamma=cfg.gamma,
        verbose=1,
        device=device,
        seed=cfg.seed,
        tensorboard_log=cfg.tensorboard_log,
    )


def build_callbacks(
    cfg: TrainingConfig, opponent, eval_env: GodFieldVectorEnv | None
) -> list[BaseCallback]:
    callbacks: list[BaseCallback] = [WinRateCallback()]
    if not cfg.self_play:
        return callbacks

    callbacks.append(
        SelfPlayCallback(
            pool=opponent,
            save_freq=max(1, cfg.self_play_save_freq // cfg.num_envs),
            save_path=cfg.pool_dir,
            worker_id=cfg.worker_id,
            seed=cfg.seed,
            total_timesteps=cfg.total_timesteps,
            verbose=1,
        )
    )
    if eval_env is not None:
        callbacks.append(
            MaskableEvalCallback(
                eval_env,
                best_model_save_path=f"{cfg.pool_dir}/best_worker_{cfg.worker_id}",
                log_path="logs/eval",
                eval_freq=max(1000, EVAL_EVERY_STEPS // cfg.num_envs),
                n_eval_episodes=EVAL_EPISODES,
                deterministic=True,
                render=False,
                verbose=1,
            )
        )
    return callbacks


def describe(cfg: TrainingConfig, device: str) -> str:
    """実行前に効いている設定を1箇所にまとめて出します。

    ログの先頭を見ればその実行の条件が分かるようにしておかないと、
    何十時間も回したあとで「どの設定だったか」を追えなくなります。
    """
    seq_len = 1 + godfield_core.MAX_HAND_SIZE * 4 + godfield_core.HISTORY_LENGTH
    net = (
        f"Transformer d{cfg.d_model} h{cfg.nhead} L{cfg.num_layers} "
        f"ff{cfg.dim_feedforward} 系列長{seq_len}"
        if cfg.use_transformer else "MLP"
    )
    shaping = (
        f"hp={cfg.shape_hp} mp={cfg.shape_mp} money={cfg.shape_money}"
        if (cfg.shape_hp or cfg.shape_mp or cfg.shape_money) else "なし"
    )
    return "\n".join([
        "=" * 68,
        f"  device      : {device}{' + bf16(AMP)' if cfg.amp else ''}",
        f"  network     : {net}",
        f"  envs        : {cfg.num_envs} / n_steps={cfg.n_steps}"
        f" / rollout={cfg.num_envs * cfg.n_steps:,} サンプル",
        f"  ppo         : batch={cfg.batch_size} epochs={cfg.n_epochs}"
        f" lr={cfg.lr} ent={cfg.ent_coef} gamma={cfg.gamma}",
        f"  shaping     : {shaping}",
        f"  opponent    : {cfg.opponent}"
        + (f" + self-play(worker {cfg.worker_id}, pool={cfg.pool_dir})" if cfg.self_play else ""),
        f"  seed        : {cfg.seed}",
        f"  timesteps   : {cfg.total_timesteps:,}",
        "=" * 68,
    ])


def run(cfg: TrainingConfig) -> MaskablePPO:
    """設定どおりに学習を実行し、学習後のモデルを返します。"""
    all_cards()   # カードマスタと C++ 登録簿の初期化
    device = pick_device()
    print(describe(cfg, device))

    wandb_run = None
    if cfg.wandb:
        import wandb
        from wandb.integration.sb3 import WandbCallback

        wandb_run = wandb.init(
            project=cfg.wandb_project,
            name=cfg.wandb_name or f"ppo_{cfg.opponent}_{cfg.seed}",
            config=cfg.__dict__,
            sync_tensorboard=True,
            save_code=True,
        )

    opponent = build_opponent(cfg, device)
    train_env, eval_env = build_envs(cfg, opponent, device)
    model = build_model(cfg, train_env, device)
    callbacks = build_callbacks(cfg, opponent, eval_env)

    if cfg.wandb:
        from wandb.integration.sb3 import WandbCallback

        callbacks.append(WandbCallback(model_save_path=f"models/{wandb_run.id}", verbose=2))

    model.learn(total_timesteps=cfg.total_timesteps, callback=callbacks)
    model.save(cfg.save_path)
    print(f"Training complete! Model saved to {cfg.save_path}.zip")

    if wandb_run is not None:
        wandb_run.finish()
    return model
