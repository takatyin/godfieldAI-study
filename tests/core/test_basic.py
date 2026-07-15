from tests.core.test_utils import SimulationRunner
import godfield_core

def test_basic_attack_state_transition():
    sim = SimulationRunner()
    
    # 状況セットアップ: P0は木の剣(id_str="wood_sword"が未定義なら適当なIDにするが、今回はダミーロジックテストなので手札は問わない)
    # ダミーとして適当にセット
    sim.set_status(player=0, hp=40)
    sim.set_status(player=1, hp=40)
    
    # current_actor_id is 0 by default
    assert sim.state.current_actor_id == 0
    assert sim.state.current_phase == godfield_core.GamePhase.STATE_0_GUARDIAN
    
    # Action 18 is dummy for "attack execution" in our game_logic.cpp test
    sim.step(action=18)
    
    # Assert state moved to defense phase and actor switched
    assert sim.state.current_phase == godfield_core.GamePhase.STATE_4_ATK_DEF
    assert sim.state.attacker_id == 0
    assert sim.state.defender_id == 1
    assert sim.state.current_actor_id == 1
    assert sim.state.pending_attack_power == 1
