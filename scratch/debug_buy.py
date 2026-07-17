import sys
sys.path.append('.')
import godfield_core
from godfield_core import GamePhase, ActionType
from tests.core.test_utils import SimulationRunner, find_card_by_name

runner2 = SimulationRunner()
buy_id = find_card_by_name("買う")
shield_id = find_card_by_name("木の盾")
pot_id = find_card_by_name("守護封印のつぼ")

runner2.state.current_phase = GamePhase.PHASE_MAIN
runner2.state.current_actor_id = 0
runner2.state.set_money(0, 20)
runner2.state.set_money(1, 0)

runner2.state.set_true_hand(0, 0, buy_id)
for i in range(1, 18):
    runner2.state.set_true_hand(0, i, shield_id)

runner2.state.set_true_hand(1, 0, pot_id)

runner2.step(action=ActionType.ACTION_SELECT_HAND_0)
print(f"After select: {runner2.state.current_phase}, staged: {runner2.state.get_staged_cards(0,0)}")
runner2.step(action=ActionType.ACTION_TARGET_OPP)
print(f"After target: {runner2.state.current_phase}, actor: {runner2.state.current_actor_id}")
runner2.step(action=ActionType.ACTION_CONFIRM)
print(f"After confirm: {runner2.state.current_phase}, actor: {runner2.state.current_actor_id}, staged1: {runner2.state.get_staged_cards(1,0)}")
runner2.step(action=ActionType.ACTION_DEAL_YES)
print(f"After deal: {runner2.state.current_phase}")
print(f"Money0: {runner2.state.get_money(0)}, Money1: {runner2.state.get_money(1)}")

pot_count = 0
for i in range(1, 18):
    card = runner2.state.get_true_hand(0, i)
    if card == pot_id:
        pot_count += 1
print(f"Pot count: {pot_count}")
