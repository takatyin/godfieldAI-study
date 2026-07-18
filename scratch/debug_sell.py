import sys

sys.path.append(".")
from godfield_core import ActionType, GamePhase
from tests.core.test_utils import SimulationRunner, find_card_by_name

runner = SimulationRunner()
sell_id = find_card_by_name("売る")
pot_id = find_card_by_name("守護封印のつぼ")

runner.state.current_phase = GamePhase.PHASE_MAIN
runner.state.current_actor_id = 0
runner.state.set_money(0, 5)
runner.state.set_mp(0, 8)
runner.state.set_hp(0, 50)

runner.state.set_true_hand(0, 0, sell_id)
runner.state.set_true_hand(0, 1, pot_id)

runner.step(action=ActionType.ACTION_SELECT_HAND_0)
print(
    f"After select0 (ID_SELL): phase={runner.state.current_phase}, actor={runner.state.current_actor_id}, staged={runner.state.get_staged_cards(0, 0)}, num={runner.state.get_num_staged_cards(0)}"
)
runner.step(action=ActionType.ACTION_TARGET_SELF)
print(
    f"After target self: phase={runner.state.current_phase}, actor={runner.state.current_actor_id}, attacker={runner.state.attacker_id}, defender={runner.state.defender_id}"
)
runner.step(action=ActionType.ACTION_SELECT_HAND_1)
print(
    f"After select1 (pot): phase={runner.state.current_phase}, actor={runner.state.current_actor_id}, staged1={runner.state.get_staged_cards(0, 1)}, num={runner.state.get_num_staged_cards(0)}"
)
runner.step(action=ActionType.ACTION_CONFIRM)
print(f"After confirm: phase={runner.state.current_phase}, money0={runner.state.get_money(0)}")
