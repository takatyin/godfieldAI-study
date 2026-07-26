"""強化学習パイプライン（VecEnv・観測レイアウト・特徴抽出器）のテスト。

`tests/core/` がゲームロジックを検証しているのに対し、こちらはC++コアとPython側の
境界を検証します。特に観測レイアウトはC++の `Observation` 構造体と
`feature_config.py` のオフセット表が一致していることが前提であり、
ズレても例外は起きず、学習だけが静かに壊れます。
"""

import numpy as np
import pytest
import torch
from gymnasium.spaces import Box

import godfield_core
from godfield_rl import feature_config as fc
from godfield_rl.env_wrapper import ACTION_SPACE_SIZE, GodFieldVectorEnv
from godfield_rl.feature_extractor import GodFieldFeatureExtractor
from godfield_rl.opponents import HeuristicOpponent, RandomOpponent, make_opponent

NUM_ENVS = 4


@pytest.fixture
def env():
    return GodFieldVectorEnv(NUM_ENVS)


def _first_legal_actions(env: GodFieldVectorEnv) -> np.ndarray:
    """各環境の最初の合法手を選びます。"""
    masks = env.action_masks()
    return np.array([int(np.flatnonzero(masks[i])[0]) for i in range(env.num_envs)], dtype=np.int32)


# ==========================================
# 定数・観測レイアウトの整合性
# ==========================================


def test_constants_come_from_the_core_module():
    """
    検証内容: 行動空間などの定数がC++側と一致していること。
    - これらを Python 側にコピーすると、C++での変更に追従できず観測の
      スライス位置が静かにズレます。
    """
    assert ACTION_SPACE_SIZE == godfield_core.ACTION_SPACE_SIZE
    assert fc.ACTION_SPACE_SIZE == godfield_core.ACTION_SPACE_SIZE
    assert fc.MAX_HAND_SIZE == godfield_core.MAX_HAND_SIZE
    assert fc.HISTORY_LENGTH == godfield_core.HISTORY_LENGTH


def test_feature_config_layout_matches_the_core_observation():
    """
    検証内容: feature_config のオフセット表がC++の Observation と整合すること。
    - マスクを除いた特徴量サイズが、C++が報告する値と一致する必要があります。
    - ここがズレると特徴抽出器が別のフィールドを読み始めます。
    """
    expected = godfield_core.OBSERVATION_FEATURE_SIZE - godfield_core.ACTION_SPACE_SIZE
    assert fc.TOTAL_OBSERVATION_FEATURE_SIZE_NO_MASK == expected

    # カードIDの領域は4ブロック（自分の手札・仮置き・相手の手札・相手の仮置き）が連続する
    assert fc.STAGED_CARDS_START == fc.HAND_CARDS_START + fc.MAX_HAND_SIZE
    assert fc.OPP_HAND_CARDS_START == fc.STAGED_CARDS_START + fc.MAX_HAND_SIZE
    assert fc.OPP_STAGED_CARDS_START == fc.OPP_HAND_CARDS_START + fc.MAX_HAND_SIZE
    assert fc.HISTORY_START == fc.OPP_STAGED_CARDS_START + fc.MAX_HAND_SIZE


# ==========================================
# VecEnv インターフェース
# ==========================================


def test_reset_returns_observations_without_the_action_mask(env):
    """
    検証内容: reset が返す観測の形状と型。
    - 観測には合法手マスクを含めず、マスクは action_masks() から取得します。
    """
    obs = env.reset()
    assert obs.shape == (NUM_ENVS, fc.TOTAL_OBSERVATION_FEATURE_SIZE_NO_MASK)
    assert obs.dtype == np.float32
    assert env.observation_space.shape == (fc.TOTAL_OBSERVATION_FEATURE_SIZE_NO_MASK,)


def test_action_masks_shape_and_at_least_one_legal_action(env):
    """
    検証内容: 合法手マスクの形状・型と、行動可能な状態であること。
    - MaskablePPO は bool 配列を要求します。
    - どの環境でも合法手が最低1つないと、エージェントが行動を選べません。
    """
    env.reset()
    masks = env.action_masks()

    assert masks.shape == (NUM_ENVS, ACTION_SPACE_SIZE)
    assert masks.dtype == np.bool_
    assert (masks.sum(axis=1) > 0).all()


def test_step_returns_the_vecenv_tuple(env):
    """
    検証内容: step が VecEnv の規約通り (obs, rewards, dones, infos) を返すこと。
    """
    env.reset()
    obs, rewards, dones, infos = env.step(_first_legal_actions(env))

    assert obs.shape == (NUM_ENVS, fc.TOTAL_OBSERVATION_FEATURE_SIZE_NO_MASK)
    assert rewards.shape == (NUM_ENVS,)
    assert dones.shape == (NUM_ENVS,)
    assert dones.dtype == np.bool_
    assert len(infos) == NUM_ENVS
    assert all(isinstance(info, dict) for info in infos)


def test_seed_controls_reset_and_is_reproducible(env):
    """
    検証内容: seed() が実際に環境の乱数を制御すること。
    - VecEnv の既定実装はサブ環境ごとに seed を配る前提で、C++側がシードを
      一括管理するこの構成では届きません。override が外れると seed が固定値に
      戻り、--seed を指定しても再現性が得られなくなります。
    """
    env.seed(999)
    first = env.reset()

    env.seed(1)
    other = env.reset()

    env.seed(999)
    again = env.reset()

    assert not np.array_equal(first, other), "シードを変えても初期状態が変わっていない"
    assert np.array_equal(first, again), "同じシードで初期状態が再現していない"


def test_terminal_observation_is_recorded_on_episode_end():
    """
    検証内容: エピソード終了時に終端観測が info へ記録されること。
    - EnvPool は完了した環境をそのステップ内で自動リセットするため、
      対策がないと「リセット後の初期状態」で価値をブートストラップしてしまいます。
    """
    env = GodFieldVectorEnv(16)
    env.seed(7)
    env.reset()
    rng = np.random.default_rng(0)

    for _ in range(400):
        masks = env.action_masks()
        actions = np.array(
            [rng.choice(np.flatnonzero(masks[i])) for i in range(env.num_envs)], dtype=np.int32
        )
        _, _, dones, infos = env.step(actions)
        if dones.any():
            idx = int(np.flatnonzero(dones)[0])
            terminal = infos[idx]["terminal_observation"]
            assert terminal.shape == (fc.TOTAL_OBSERVATION_FEATURE_SIZE_NO_MASK,)
            assert infos[idx]["TimeLimit.truncated"] is False
            return

    pytest.fail("400ステップ以内にエピソードが終了しませんでした")


def test_no_state_runs_out_of_legal_actions():
    """
    検証内容: 長時間のランダム対戦でも合法手が0件になる状態に陥らないこと。

    合法手が0件になると、送った行動が全て非合法なので状態が進まず、環境が永久に停止します。
    ターン数打ち切りも `current_turn` が進まないため救済になりません。MaskablePPO は
    空のマスクから確率分布を作れず NaN か例外になります。

    実例として、MPを借りて＜オーラ＞を仮置きした後に別のプラスカードを重ねると、
    返済手段である精霊系カードが永久に非合法化して詰んでいました。
    """
    num_envs = 64
    env = GodFieldVectorEnv(num_envs)
    env.seed(12345)
    env.reset()
    rng = np.random.default_rng(0)

    for step in range(400):
        masks = env.action_masks()
        stuck = np.flatnonzero(masks.sum(axis=1) == 0)
        assert stuck.size == 0, (
            f"step {step}: 環境 {stuck.tolist()} の合法手が0件です。"
            f"phase={env.core_env.get_state(int(stuck[0])).current_phase.name}"
        )
        actions = np.array(
            [rng.choice(np.flatnonzero(masks[i])) for i in range(num_envs)], dtype=np.int32
        )
        env.step(actions)


@pytest.mark.parametrize("seat", [0, 1])
def test_learner_only_ever_sees_its_own_turns(seat):
    """
    検証内容: SB3 に見えるロールアウトが単一エージェントのものになっていること。

    2人ゲームの手番をそのまま SB3 に渡すと、連続する遷移が別プレイヤーのものになり、
    GAE が相手視点の V(s') を符号反転せずにブートストラップしてしまいます。
    相手の手番は環境の内部で消化されるべきで、学習者の手番以外が観測されてはいけません。
    """
    env = GodFieldVectorEnv(16, opponent=HeuristicOpponent(seed=0), learner_seat=seat)
    env.seed(7)
    env.reset()
    rng = np.random.default_rng(0)

    for _ in range(120):
        actors = env.core_env.get_current_actors()
        assert (actors == seat).all(), f"学習者以外の手番が渡された: {np.unique(actors)}"
        masks = env.action_masks()
        actions = np.array(
            [rng.choice(np.flatnonzero(masks[i])) for i in range(env.num_envs)], dtype=np.int32
        )
        env.step(actions)


def test_rewards_use_the_learner_perspective():
    """
    検証内容: 報酬が学習者視点であること。

    相手の手番で決着した場合、行動者視点の報酬（get_rewards）は相手のものなので符号が逆に
    なります。学習者視点（get_rewards_for）を使う必要があります。
    勝敗はどちらも起こるため、勝ちと負けの両方が観測できることで符号の正しさを確認します。
    """
    env = GodFieldVectorEnv(32, opponent=HeuristicOpponent(seed=0), learner_seat=0)
    env.seed(7)
    env.reset()
    rng = np.random.default_rng(0)

    wins = losses = 0
    for _ in range(400):
        masks = env.action_masks()
        actions = np.array(
            [rng.choice(np.flatnonzero(masks[i])) for i in range(env.num_envs)], dtype=np.int32
        )
        _, rewards, dones, _ = env.step(actions)
        for i in np.flatnonzero(dones):
            assert -1.0 <= rewards[i] <= 1.0
            if rewards[i] > 0:
                wins += 1
            elif rewards[i] < 0:
                losses += 1

    assert wins > 0, "勝利が一度も観測されていない"
    assert losses > 0, "敗北が一度も観測されていない"
    # ランダム方策はヒューリスティックに勝てないはずで、符号が逆なら逆転する
    assert losses > wins, f"ランダム方策の勝敗が不自然（win={wins} lose={losses}）。報酬の符号を確認"


def test_parallel_stepping_is_deterministic():
    """
    検証内容: OpenMP 並列下でも同じシードなら同じ結果になること。
    - draw_card はスレッドローカルな確率分布から抽選するため、
      スレッド数や実行順に結果が依存してはいけません。
    """

    def rollout():
        env = GodFieldVectorEnv(32)
        env.seed(7)
        obs = env.reset()
        rng = np.random.default_rng(0)
        rewards_sum = 0.0
        for _ in range(30):
            masks = env.action_masks()
            actions = np.array(
                [rng.choice(np.flatnonzero(masks[i])) for i in range(env.num_envs)], dtype=np.int32
            )
            obs, rewards, _, _ = env.step(actions)
            rewards_sum += float(rewards.sum())
        return float(obs.sum()), rewards_sum

    assert rollout() == rollout()


# ==========================================
# 特徴抽出器
# ==========================================


def test_feature_extractor_consumes_real_observations(env):
    """
    検証内容: 特徴抽出器が実際の観測を処理できること。
    - 連続値・カードID埋め込み・イベント履歴の各ブロックを結合した次元が、
      入力層の in_features と一致している必要があります。
    """
    obs = env.reset()
    space = Box(low=-np.inf, high=np.inf, shape=(obs.shape[1],), dtype=np.float32)
    extractor = GodFieldFeatureExtractor(space, features_dim=256)

    out = extractor(torch.as_tensor(obs))

    assert out.shape == (NUM_ENVS, 256)
    assert torch.isfinite(out).all()


@pytest.mark.parametrize("kind", ["random", "heuristic"])
def test_opponents_only_choose_legal_actions(kind):
    """
    検証内容: 相手方策が必ず合法手を返すこと。
    - 非合法手を返すと状態が進まず、環境が停止します。
    """
    env = GodFieldVectorEnv(16, opponent=make_opponent(kind, seed=0))
    env.reset()
    obs, masks = env._get_obs_and_masks()
    opponent = make_opponent(kind, seed=0)

    actions = opponent.act(obs, masks.astype(bool))

    assert actions.shape == (env.num_envs,)
    assert actions.dtype == np.int32
    assert masks.astype(bool)[np.arange(env.num_envs), actions].all()


def test_heuristic_opponent_beats_random():
    """
    検証内容: ヒューリスティック相手が意味のあるベースラインであること。
    - 自己対戦だけでは勝率が50%付近に張り付いて強くなっているか分からないため、
      ヒューリスティックへの勝率を指標として使います。
      それが機能するには、ランダム方策より明確に強い必要があります。
    """
    env = GodFieldVectorEnv(32, opponent=HeuristicOpponent(seed=0), learner_seat=0)
    env.seed(7)
    env.reset()
    learner = RandomOpponent(seed=1)

    wins = losses = 0
    for _ in range(300):
        obs, masks = env._get_obs_and_masks()
        actions = learner.act(obs, masks.astype(bool))
        _, rewards, dones, _ = env.step(actions)
        for i in np.flatnonzero(dones):
            if rewards[i] > 0:
                wins += 1
            elif rewards[i] < 0:
                losses += 1

    total = wins + losses
    assert total > 50, f"決着したエピソードが少なすぎます ({total})"
    assert wins / total < 0.45, f"ランダム方策の勝率が高すぎます ({wins}/{total})"


def test_card_ids_stay_within_the_embedding_table(env):
    """
    検証内容: 観測に現れるカードIDが埋め込みテーブルの範囲に収まること。
    - 埋め込みは CARD_EMPTY(-1) を 0 に寄せるため +1 してから引きます。
      カードが追加されて NUM_CARD_TYPES を超えると、clamp によって
      別のカードとして扱われ、静かに精度が落ちます。
    """
    obs = env.reset()
    cards = obs[:, fc.HAND_CARDS_START : fc.OPP_STAGED_CARDS_START + fc.MAX_HAND_SIZE]

    assert cards.min() >= godfield_core.CARD_EMPTY
    assert cards.max() < fc.NUM_CARD_TYPES
    assert fc.NUM_CARD_TYPES >= godfield_core.get_registry_size()
