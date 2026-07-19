import copy
import pytest
import numpy as np
import godfield_core
from tests.core.test_utils import SimulationRunner

def test_observation_basic():
    # 1. Setup game logic registry and runner
    sim = SimulationRunner()
    
    # 2. Set statuses
    sim.set_status(player=0, hp=40, mp=10, money=20)
    sim.set_status(player=1, hp=35, mp=15, money=25)
    
    # Let's set some cards
    # Use actual card IDs (e.g. 0, 1, 2)
    sim.state.set_true_hand(0, 0, 0) # weapons/bronze-club
    sim.state.set_true_hand(0, 1, 1) # weapons/silver-club
    sim.state.set_apparent_hand(0, 0, 0)
    sim.state.set_apparent_hand(0, 1, 1)
    
    # 3. Get observation for player 0
    obs_p0 = godfield_core.get_observation(sim.state, 0)
    
    assert obs_p0.hp_me == pytest.approx(0.4)
    assert obs_p0.hp_opp == pytest.approx(0.35)
    assert obs_p0.mp_me == pytest.approx(0.1)
    assert obs_p0.mp_opp == pytest.approx(0.15)
    assert obs_p0.money_me == pytest.approx(0.2)
    assert obs_p0.money_opp == pytest.approx(0.25)
    
    # Hand cards check
    hand = obs_p0.get_hand_cards()
    assert hand[0] == 0
    assert hand[1] == 1
    assert hand[2] == -1 # Empty
    
    # 4. Check copyability
    obs_copy = copy.copy(obs_p0)
    assert obs_copy.hp_me == pytest.approx(0.4)
    
    # 5. Check numpy conversion
    arr = obs_p0.to_numpy()
    assert isinstance(arr, np.ndarray)
    assert arr.dtype == np.float32
    assert len(arr.shape) == 1
    # Check that array size matches
    assert arr[0] == pytest.approx(0.4) # hp_me
    assert arr[1] == pytest.approx(0.35) # hp_opp

def test_observation_fog_masking():
    sim = SimulationRunner()
    sim.set_status(player=0, hp=40, mp=10, money=20)
    sim.set_status(player=1, hp=35, mp=15, money=25)
    
    # Put player 0 under Fog curse (Fog is CurseType index 0)
    sim.state.set_curses(0, godfield_core.CurseType.CURSE_FOG, True)
    
    # Get observation for player 0 (who has fog)
    obs_p0 = godfield_core.get_observation(sim.state, 0)
    assert obs_p0.hp_me == pytest.approx(0.4)
    assert obs_p0.hp_opp == pytest.approx(0.0)  # Fogged!
    assert obs_p0.mp_opp == pytest.approx(0.0)  # Fogged!
    assert obs_p0.money_opp == pytest.approx(0.0)  # Fogged!
    
    # Get observation for player 1 (who does NOT have fog)
    obs_p1 = godfield_core.get_observation(sim.state, 1)
    assert obs_p1.hp_me == pytest.approx(0.35)
    assert obs_p1.hp_opp == pytest.approx(0.4)  # Not fogged for player 1!
