from godfield_rl.env_wrapper import GodFieldVectorEnv
from godfield_rl.privileged.policy import PrivilegedMaskableActorCriticPolicy
from godfield_rl.privileged.ppo import PrivilegedMaskablePPO


def test_privileged_ppo_short_learn():
    env = GodFieldVectorEnv(num_envs=2)

    model = PrivilegedMaskablePPO(
        policy=PrivilegedMaskableActorCriticPolicy,
        env=env,
        n_steps=4,
        batch_size=4,
        n_epochs=1,
        learning_rate=3e-4,
        verbose=0,
    )

    model.learn(total_timesteps=8)