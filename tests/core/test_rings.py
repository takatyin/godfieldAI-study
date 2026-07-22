# -*- coding: utf-8 -*-
import pytest
import godfield_core
from godfield_core import GamePhase, ActionType, EventType
from tests.core.test_utils import SimulationRunner, find_card_by_name
from visualize_server import format_event_log

def test_saturn_ring_counter_attack_event():
    runner = SimulationRunner()
    sword_id = find_card_by_name('weapons/gale-sword')
    saturn_id = find_card_by_name('armor/saturn-ring')
    
    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    
    runner.set_hand(0, [sword_id])
    runner.set_hand(1, [saturn_id])
    
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_TARGET_OPP)
    
    assert runner.state.current_phase == GamePhase.PHASE_DEFENSE
    assert runner.state.current_actor_id == 1
    
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_CONFIRM)
    
    obs = godfield_core.get_observation(runner.state, 1)
    ring_events = [ev for ev in obs.get_history() if ev.event_type == int(EventType.RING_EFFECT)]
    
    assert len(ring_events) > 0
    last_ring_event = ring_events[-1]
    assert last_ring_event.card_id == saturn_id
    
    fmt = format_event_log(last_ring_event, 1)
    assert '反撃が発動！' in fmt['text']

def test_neptune_ring_mp_increase_event():
    runner = SimulationRunner()
    # 疾風剣 (10ダメ) で攻撃。海王の指輪(防御1)で防御すると貫通ダメ9発生 -> 自分のMPが 9*2 = 18増加
    sword_id = find_card_by_name('weapons/gale-sword')
    neptune_id = find_card_by_name('armor/neptune-ring')
    
    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_mp(1, 10)
    
    runner.set_hand(0, [sword_id])
    runner.set_hand(1, [neptune_id])
    
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_TARGET_OPP)
    
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_CONFIRM)
    
    # 貫通ダメージ9の2倍(=18)のMPが自分のMPに加算され、10 -> 28 になる
    assert runner.state.get_mp(1) == 28
