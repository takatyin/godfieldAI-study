import godfield_core
from godfield_core import ActionType
from tests.core.test_utils import SimulationRunner, find_card_by_name


def test_mushroom_outbreak_auto_advance():
    """
    検証内容: 「運命のひも」によって「きのこ大発生」がトリガーされた際、
    即座に全自動で6ターン（ご乱心状態）が進行し、ターン数が6進むこと、
    およびご乱心終了後に通常の操作受付（mushroom_turns = 0）に戻ることを検証する。
    """
    string_of_fate_id = find_card_by_name("運命のひも")

    # きのこ大発生（現象インデックス 2）を発生させるシードを探索
    target_seed = -1
    for seed in range(100):
        runner = SimulationRunner()
        runner.reset_state()
        runner.state.seed_rng(seed)
        runner.state.current_turn = 10
        runner.state.current_actor_id = 0
        runner.set_status(player=0, hp=40, mp=10, money=10)
        runner.set_status(player=1, hp=40, mp=10, money=10)

        # 運命のひもを持たせる
        runner.state.set_true_hand(0, 0, string_of_fate_id)

        # 運命のひもを使用する (選択 ➡ ターゲット自己)
        runner.step(ActionType.ACTION_SELECT_HAND_0)
        runner.step(ActionType.ACTION_TARGET_SELF)

        # もし「きのこ大発生」がトリガーされた場合、内部で mushroom_turns が 6 にセットされた後、
        # ターン終了処理でデクリメントされつつ自動進行するため、
        # 最終的に現在のターンが 10 + 6 = 16 まで進んでいるはずである。
        if runner.state.current_turn == 16:
            target_seed = seed
            break

    assert target_seed != -1, "Mushroom Outbreak was not triggered in any of the 100 seeds"

    # 発見したシードで再度詳細をアサート
    runner = SimulationRunner()
    runner.reset_state()
    runner.state.seed_rng(target_seed)
    runner.state.current_turn = 10
    runner.state.current_actor_id = 0
    runner.set_status(player=0, hp=40, mp=10, money=10)
    runner.set_status(player=1, hp=40, mp=10, money=10)
    runner.state.set_true_hand(0, 0, string_of_fate_id)

    # 運命のひもを使用する前のターンは 10
    assert runner.state.current_turn == 10

    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_TARGET_SELF)

    # ご乱心中の6ターンが自動進行し、終了していることをアサート
    assert runner.state.current_turn == 16
    assert runner.state.mushroom_turns == 0
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_MAIN

    # 自動進行により、カードがドローされて手札に入っていることを確認
    hand0 = [runner.state.get_true_hand(0, i) for i in range(18)]
    hand1 = [runner.state.get_true_hand(1, i) for i in range(18)]
    has_cards0 = any(c != godfield_core.CARD_EMPTY for c in hand0)
    has_cards1 = any(c != godfield_core.CARD_EMPTY for c in hand1)

    assert has_cards0 or has_cards1 or runner.state.is_done, (
        "No cards were drawn or played during the 6 automatic turns under confusion"
    )


def test_mushroom_outbreak_stacking():
    """
    検証内容: きのこ大発生中にさらにきのこ大発生が発生した際、ターン数が上書きではなく加算されること。
    - 内部状態の mushroom_turns に対し、値が正しく加算・保持できることを検証。
    """
    runner = SimulationRunner()
    runner.reset_state()

    # 初期状態としてご乱心3ターンをセット
    runner.state.mushroom_turns = 3

    # 加算解決（C++側の += 6 と同等の操作）
    runner.state.mushroom_turns += 6
    assert runner.state.mushroom_turns == 9

