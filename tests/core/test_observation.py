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
    sim.state.set_true_hand(0, 0, 0)  # weapons/bronze-club
    sim.state.set_true_hand(0, 1, 1)  # weapons/silver-club
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
    assert hand[2] == -1  # Empty

    # 4. Check copyability
    obs_copy = copy.copy(obs_p0)
    assert obs_copy.hp_me == pytest.approx(0.4)

    # 5. Check numpy conversion
    arr = obs_p0.to_numpy()
    assert isinstance(arr, np.ndarray)
    assert arr.dtype == np.float32
    assert len(arr.shape) == 1
    assert arr.shape[0] == godfield_core.OBSERVATION_SIZE
    # Check that array size matches
    assert arr[0] == pytest.approx(0.4)  # hp_me
    assert arr[1] == pytest.approx(0.35)  # hp_opp

    # Deleted attributes check
    assert not hasattr(obs_p0, "pending_card")
    assert not hasattr(obs_p0, "history_count")
    assert not hasattr(obs_p0, "player_id")


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


def test_observation_custom_features():
    sim = SimulationRunner()
    sim.set_status(player=0, hp=40, mp=10, money=10)
    sim.set_status(player=1, hp=40, mp=10, money=10)

    # Put Wood Shield (ID=118) in hand slot 0
    sim.state.set_true_hand(0, 0, 118)
    sim.state.set_apparent_hand(0, 0, 118)

    # Set phase to PHASE_DEFENSE
    sim.state.current_phase = godfield_core.GamePhase.PHASE_DEFENSE
    sim.state.defender_id = 0
    sim.state.attacker_id = 1
    sim.state.pending_attack_power = 30

    # Test before staging defense
    obs0 = godfield_core.get_observation(sim.state, 0)
    assert obs0.incoming_damage == pytest.approx(0.3)
    assert obs0.current_staged_defense == pytest.approx(0.0)

    # Phase one-hot size and value check
    phases = obs0.get_phase_one_hot()
    assert len(phases) == 18
    # PHASE_DEFENSE (index 7) should be 1.0
    assert phases[7] == pytest.approx(1.0)
    assert sum(phases) == pytest.approx(1.0)

    # Stage the Wood Shield
    sim.state.set_staged_card(0, 0, 0)
    sim.state.set_num_staged_cards(0, 1)

    # Test after staging defense
    obs1 = godfield_core.get_observation(sim.state, 0)
    assert obs1.incoming_damage == pytest.approx(0.3)
    # Wood Shield defense power is 2 (normalized to 0.02)
    assert obs1.current_staged_defense == pytest.approx(0.02)
