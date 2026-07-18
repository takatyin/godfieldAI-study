import godfield_core
from godfield_core import ActionType
from tests.core.test_utils import SimulationRunner, find_card_by_name


def test_spiritual_doll_mp_bypass_availability():
    """
    検証内容: 精霊のぬいぐるみによるMP消費踏み倒し時のカード選択権。
    - 手持ちのMPが2の状態で、消費MP 2 の奇跡「＜火の玉＞」を選択した際、重ねがけフェイズ（PHASE_MIRACLE_PLUS）に遷移することを確認します。
    - 重ねがけフェイズにおいて、手札にある「精霊のぬいぐるみ」が合法手（選択可能）であることを確認します。
    """
    runner = SimulationRunner()
    fireball_id = find_card_by_name("＜火の玉＞")
    doll_id = find_card_by_name("精霊のぬいぐるみ")

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_mp(0, 2)

    runner.state.set_true_hand(0, 0, fireball_id)
    runner.state.set_true_hand(0, 1, doll_id)

    # 火の玉を選択
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_MIRACLE_PLUS

    # 重ねがけで「精霊のぬいぐるみ」が選択可能なこと
    legal_actions = godfield_core.get_legal_actions(runner.state)
    assert legal_actions[ActionType.ACTION_SELECT_HAND_1] is True


def test_spiritual_doll_mp_bypass_executes_with_zero_mp_cost():
    """
    検証内容: 精霊のぬいぐるみ使用時のMP消費ゼロ解決。
    - 奇跡「＜火の玉＞」に「精霊 of ぬいぐるみ」を重ねて攻撃を実行した際、MPが 2 から減らずに維持された状態で奇跡防御フェイズ（PHASE_MIRACLE_DEFENSE）に移行することを確認します。
    """
    runner = SimulationRunner()
    fireball_id = find_card_by_name("＜火の玉＞")
    doll_id = find_card_by_name("精霊のぬいぐるみ")

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_mp(0, 2)

    runner.state.set_true_hand(0, 0, fireball_id)
    runner.state.set_true_hand(0, 1, doll_id)

    runner.step(ActionType.ACTION_SELECT_HAND_0)  # 火の玉
    runner.step(ActionType.ACTION_SELECT_HAND_1)  # ぬいぐるみ
    runner.step(ActionType.ACTION_TARGET_OPP)

    # MPが 2 のままであること
    assert runner.state.get_mp(0) == 2
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_MIRACLE_DEFENSE


def test_high_cost_miracle_initial_selection():
    """
    検証内容: MP不足時の高コスト奇跡の選択権（精霊存在ルール）。
    - 自身のMPが 2 の際、手札に消費MP 5 の奇跡「＜闇＞」と「精霊のぬいぐるみ」がある場合、メインフェイズにおいて「＜闇＞」が選択可能（合法手）になることを確認します。
    - 精霊が手札に無い場合は、MP不足のため「＜闇＞」が非合法手になることも併せて確認します。
    """
    runner_with_doll = SimulationRunner()
    darkness_id = find_card_by_name("＜闇＞")
    doll_id = find_card_by_name("精霊のぬいぐるみ")

    runner_with_doll.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner_with_doll.state.current_actor_id = 0
    runner_with_doll.state.set_mp(0, 2)

    runner_with_doll.state.set_true_hand(0, 0, darkness_id)
    runner_with_doll.state.set_true_hand(0, 1, doll_id)

    # 手札に精霊がある場合は、闇の選択が合法であること
    actions_with_doll = godfield_core.get_legal_actions(runner_with_doll.state)
    assert actions_with_doll[ActionType.ACTION_SELECT_HAND_0] is True

    # 手札に精霊が無い場合
    runner_no_doll = SimulationRunner()
    runner_no_doll.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner_no_doll.state.current_actor_id = 0
    runner_no_doll.state.set_mp(0, 2)
    runner_no_doll.state.set_true_hand(0, 0, darkness_id)

    actions_no_doll = godfield_core.get_legal_actions(runner_no_doll.state)
    assert actions_no_doll[ActionType.ACTION_SELECT_HAND_0] is False


def test_high_cost_miracle_cannot_target_without_doll():
    """
    検証内容: 精霊を追加する前のターゲット制限。
    - MP不足の状態で高コスト奇跡「＜闇＞」を選択して仮置き（PHASE_MIRACLE_PLUS）した際、追加で精霊を置くまでは、ターゲット決定（TARGET_OPP）が非合法手になることを確認します。
    """
    runner = SimulationRunner()
    darkness_id = find_card_by_name("＜闇＞")
    doll_id = find_card_by_name("精霊のぬいぐるみ")

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_mp(0, 2)

    runner.state.set_true_hand(0, 0, darkness_id)
    runner.state.set_true_hand(0, 1, doll_id)

    # 闇を選択した直後
    runner.step(ActionType.ACTION_SELECT_HAND_0)

    # まだコストが踏み倒されていない（不足状態）ため、ターゲット指定は非合法であること
    legal_actions = godfield_core.get_legal_actions(runner.state)
    assert legal_actions[ActionType.ACTION_TARGET_OPP] is False


def test_high_cost_miracle_can_target_after_doll():
    """
    検証内容: 精霊を追加した後のターゲット解除と解決。
    - 仮置きした高コスト奇跡に対し、さらに「精霊のぬいぐるみ」を追加した時点で、ターゲット決定（TARGET_OPP）が合法化されることを確認します。
    - 攻撃実行後、MPが 2 を維持した状態で奇跡防御フェイズに移行することを確認します。
    """
    runner = SimulationRunner()
    darkness_id = find_card_by_name("＜闇＞")
    doll_id = find_card_by_name("精霊のぬいぐるみ")

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_mp(0, 2)

    runner.state.set_true_hand(0, 0, darkness_id)
    runner.state.set_true_hand(0, 1, doll_id)

    runner.step(ActionType.ACTION_SELECT_HAND_0)  # 闇
    runner.step(ActionType.ACTION_SELECT_HAND_1)  # ぬいぐるみを追加

    # ターゲット指定が合法になること
    legal_actions = godfield_core.get_legal_actions(runner.state)
    assert legal_actions[ActionType.ACTION_TARGET_OPP] is True

    # ターゲットして確定
    runner.step(ActionType.ACTION_TARGET_OPP)
    assert runner.state.get_mp(0) == 2
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_MIRACLE_DEFENSE


def test_miracle_and_spiritual_socks_stacking():
    """
    検証内容: 奇跡 ＋ 精霊の足袋の重ねがけ処理。
    - 奇跡「＜火の玉＞」に「精霊の足袋」を重ねて攻撃を決定した際、武器攻撃フェイズ（PHASE_DEFENSE）ではなく、奇跡防御フェイズ（PHASE_MIRACLE_DEFENSE）へと遷移することを確認します。
    - 消費MPが 0 になり、MPが減少していないことを確認します。
    """
    runner = SimulationRunner()
    fireball_id = find_card_by_name("＜火の玉＞")
    socks_id = find_card_by_name("精霊の足袋")

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.set_status(0, hp=40, mp=10)

    runner.state.set_true_hand(0, 0, fireball_id)
    runner.state.set_true_hand(0, 1, socks_id)

    runner.step(ActionType.ACTION_SELECT_HAND_0)  # 火の玉
    runner.step(ActionType.ACTION_SELECT_HAND_1)  # 足袋
    runner.step(ActionType.ACTION_TARGET_OPP)

    # 奇跡防御フェイズへ移行していること
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_MIRACLE_DEFENSE
    # MPが消費されていないこと (10)
    assert runner.state.get_mp(0) == 10
