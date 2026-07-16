import godfield_core
from tests.core.test_utils import SimulationRunner


def test_basic_attack_state_transition():
    """
    検証内容: 非合法手（違法なアクション）を選択した際に、ゲーム状態が遷移せずに無視されることをテストする。
    具体的には、守護神フェーズ (PHASE_GUARDIAN) において、手札決定アクション (ACTION_TARGET_OPP) は非合法であるため、
    ステップを実行してもフェーズやアクティブプレイヤーなどの状態が一切変化しないことを確認する。
    """
    sim = SimulationRunner()

    sim.set_status(player=0, hp=40)
    sim.set_status(player=1, hp=40)

    # 初期状態のアクティブプレイヤーが 0 であることを確認
    assert sim.state.current_actor_id == 0
    sim.state.current_phase = godfield_core.GamePhase.PHASE_GUARDIAN
    assert sim.state.current_phase == godfield_core.GamePhase.PHASE_GUARDIAN

    # 守護神フェーズにおいて無効なアクション 18 (ACTION_TARGET_OPP) を実行
    sim.step(godfield_core.ActionType.ACTION_TARGET_OPP)

    # アクションは無視され、状態が変わっていないことをアサート
    assert sim.state.current_phase == godfield_core.GamePhase.PHASE_GUARDIAN
    assert sim.state.current_actor_id == 0
