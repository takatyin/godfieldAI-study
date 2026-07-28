"""進行不能（合法手が1つも無い状態）が発生しないことのソークテスト。

step_game は制御をプレイヤーに返す時点で合法手が0件だった場合、状態ダンプ付きの
例外を投げます。黙って返すと、呼び出し側は「何を送っても進まない」環境を回し続ける
ことになり、学習側はそれを異常と認識できないためです。

このファイルは、ランダムな対戦を大量に回してその例外が飛ばないことを実測します。
個々の局面を狙い撃つテストと違い、想定していない組み合わせを踏むのが目的なので、
乱数は固定せず実際の分布のまま回します（シードは固定するので再現はします）。

【このテストの守備範囲】
ランダム対戦が踏むのは、あくまで確率的に出やすい経路です。実測したところ、
800局回しても「地球神があぶないキネを引く」経路には到達しませんでした
（この検出を入れたときに実際に見つかった進行不能はこの経路のもので、
気付けたのは tests/core/test_guardians.py の名指しのテストのおかげです）。

つまりここは「よくある進行で詰まないこと」の保証であって、稀な分岐の保証では
ありません。稀な分岐は引き続き名指しのテストで踏む必要があります。
"""

import numpy as np
import pytest

import godfield_core


def _play_games(seed: int, num_games: int, max_steps: int = 20000) -> int:
    """ランダム方策で指定局数を戦い、消費したステップ数を返します。

    EnvPool は決着すると自動でリセットするため、局の終わりは state.is_done ではなく
    get_dones() で数えます（is_done を見ても常に False に見えます）。
    """
    pool = godfield_core.EnvPool(1)
    pool.reset(seed)
    rng = np.random.default_rng(seed)

    finished = 0
    for step in range(max_steps):
        state = pool.get_state(0)
        legal = np.flatnonzero(np.array(godfield_core.get_legal_actions(state), dtype=bool))
        # 合法手0件なら step_game 側で例外になるはずなので、ここに来た時点で異常
        assert legal.size > 0, (
            f"seed={seed} step={step}: 合法手が0件です\n{godfield_core.describe_state(state)}"
        )
        pool.step_subset([0], [int(rng.choice(legal))])

        if pool.get_dones()[0]:
            finished += 1
            if finished >= num_games:
                return step + 1

    pytest.fail(f"seed={seed}: {max_steps} ステップで {num_games} 局を消化できませんでした（{finished} 局）")


@pytest.mark.parametrize("seed", range(8))
def test_random_games_never_reach_a_dead_end(seed):
    """ランダム対戦を大量に回し、進行不能にならないことを検証します。

    step_game が詰みを検出すると RuntimeError を投げるので、この関数は
    「例外なく決着し続けること」を確認していることになります。
    """
    steps = _play_games(seed, num_games=100)
    assert steps > 0, f"seed={seed}: 1ステップも進みませんでした"


def test_the_dead_end_detector_actually_fires():
    """詰み検出そのものが機能していることを、人工的な行き詰まり状態で検証します。

    これが無いと、上のソークテストは「検出が壊れていて何も見ていない」場合でも
    通ってしまいます。PHASE_GUARDIAN は合法手の定義もフェイズハンドラも持たない
    ため、実ゲームでは決して設定されませんが、進行不能そのものの再現には使えます。
    """
    state = godfield_core.InternalState()
    godfield_core.clear_state(state)
    state.current_phase = godfield_core.GamePhase.PHASE_GUARDIAN
    state.current_actor_id = 0
    state.is_done = False
    state.set_hp(0, 40)
    state.set_hp(1, 40)

    with pytest.raises(RuntimeError, match="合法手が1つもありません"):
        godfield_core.step_game(state, godfield_core.ActionType.ACTION_CONFIRM)


def test_the_crash_report_contains_enough_to_reproduce():
    """クラッシュレポートに、局面を再現できるだけの情報が含まれることを検証します。

    「詰みました」だけでは何も分からないので、フェイズ・手番・両者の状態・
    手札・仮置きが載っている必要があります。
    """
    pool = godfield_core.EnvPool(1)
    pool.reset(0)
    report = godfield_core.describe_state(pool.get_state(0))

    for key in ("phase=", "actor=", "attacker=", "initiator=", "pending:", "P0:", "P1:", "hand:", "staged("):
        assert key in report, f"クラッシュレポートに {key!r} がありません:\n{report}"
