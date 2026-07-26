import godfield_core
from godfield_core import ActionType, EventType, GamePhase
from tests.core.test_utils import SimulationRunner, find_card_by_name
from visualizer.event_formatter import format_event_log


def test_saturn_ring_counter_attack_event():
    runner = SimulationRunner()
    sword_id = find_card_by_name('weapons/gale-sword')
    saturn_id = find_card_by_name('armor/saturn-ring')

    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0

    runner.set_hand(0, [sword_id])
    runner.set_hand(1, [saturn_id])

    runner.perform_attack([0])

    assert runner.state.current_phase == GamePhase.PHASE_DEFENSE
    assert runner.state.current_actor_id == 1

    runner.perform_defense([0])

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

    runner.perform_attack([0])
    runner.perform_defense([0])

    # 貫通ダメージ9の2倍(=18)のMPが自分のMPに加算され、10 -> 28 になる
    assert runner.state.get_mp(1) == 28


def test_venus_ring_counter_defense_restrictions():
    runner = SimulationRunner()

    # プレイヤー0がプレイヤー1 of 金星の指輪による反撃を受けている状況を作る
    runner.state.current_phase = GamePhase.PHASE_SUNDRY_SELECT_MIRROR
    runner.state.current_actor_id = 0
    runner.state.attacker_id = 1
    runner.state.defender_id = 0
    runner.state.pending_attack_source_id = find_card_by_name('armor/venus-ring')
    runner.state.pending_attack_power = 10

    # プレイヤー0の手札: 木盾 と スーパーミラー
    wood_shield = find_card_by_name('armor/wood-shield')
    super_mirror = find_card_by_name('armor/super-mirror')
    runner.set_hand(0, [wood_shield, super_mirror])

    # 合法アクションを取得
    legal = godfield_core.get_legal_actions(runner.state)

    # 木盾(スロット0)は使用不可（通常防具のため）
    assert not legal[int(ActionType.ACTION_SELECT_HAND_0)]

    # スーパーミラー(スロット1)は使用可能
    assert legal[int(ActionType.ACTION_SELECT_HAND_1)]


def test_venus_ring_counter_phases():
    runner = SimulationRunner()
    sword_id = find_card_by_name('weapons/gale-sword')
    venus_id = find_card_by_name('armor/venus-ring')

    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0

    runner.set_hand(0, [sword_id])
    runner.set_hand(1, [venus_id])

    # プレイヤー0が攻撃
    runner.perform_attack([0])

    # プレイヤー1が金星の指輪で防御
    runner.perform_defense([0])

    # 金星の指輪による反撃がトリガーされる。
    # 特殊指輪なので、フェイズは PHASE_SUNDRY_SELECT_MIRROR になるはず！
    assert runner.state.current_phase == GamePhase.PHASE_SUNDRY_SELECT_MIRROR
    assert runner.state.current_actor_id == 0 # 攻撃した側のプレイヤー0が防御（反射）の選択に入る


def test_mars_ring_counter():
    punch_id = find_card_by_name("weapons/punch")
    mars_ring_id = find_card_by_name("armor/mars-ring")
    ice_shield_id = find_card_by_name("アイスシールド")

    runner = SimulationRunner()
    runner.state.seed_rng(42)  # ロール成功するシード値
    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.set_status(0, hp=40, mp=10)
    runner.set_status(1, hp=40, mp=10)

    runner.state.set_true_hand(0, 0, punch_id)
    runner.state.set_true_hand(0, 1, ice_shield_id)
    runner.state.set_true_hand(1, 0, mars_ring_id)

    runner.perform_attack([0])
    runner.perform_defense([0])

    assert runner.state.get_hp(1) == 37

    assert runner.state.current_phase == GamePhase.PHASE_DEFENSE
    assert runner.state.current_actor_id == 0
    assert runner.state.pending_attack_power == 3
    assert runner.state.pending_attack_element == godfield_core.Element.ELEM_FIRE

    runner.perform_defense([1])

    assert runner.state.get_hp(0) == 40
    assert runner.state.current_phase == GamePhase.PHASE_MAIN


def test_jupiter_ring_curse():
    punch_id = find_card_by_name("weapons/punch")
    jupiter_ring_id = find_card_by_name("armor/jupiter-ring")

    runner = SimulationRunner()
    runner.state.seed_rng(42)
    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.set_status(0, hp=40, mp=10)
    runner.set_status(1, hp=40, mp=10)

    runner.state.set_true_hand(0, 0, punch_id)
    runner.state.set_true_hand(1, 0, jupiter_ring_id)

    runner.perform_attack([0])
    runner.perform_defense([0])

    assert runner.state.current_phase == GamePhase.PHASE_SUNDRY_SELECT_MIRROR
    assert runner.state.current_actor_id == 0
    assert runner.state.pending_attack_power == 0
    assert runner.state.pending_attack_element == godfield_core.Element.ELEM_WOOD

    runner.perform_defense([], confirm=True)

    assert runner.state.get_hp(0) == 40
    assert runner.state.get_curses(0, godfield_core.CurseType.CURSE_DREAM) == True
    assert runner.state.current_phase == GamePhase.PHASE_MAIN


def test_neptune_venus_rings():
    punch_id = find_card_by_name("weapons/punch")
    neptune_ring_id = find_card_by_name("armor/neptune-ring")
    venus_ring_id = find_card_by_name("armor/venus-ring")

    runner = SimulationRunner()
    runner.state.seed_rng(42)
    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.set_status(0, hp=40, mp=10, money=20)
    runner.set_status(1, hp=40, mp=10, money=20)

    runner.state.set_true_hand(0, 0, punch_id)
    runner.state.set_true_hand(1, 0, neptune_ring_id)
    runner.state.set_true_hand(1, 1, venus_ring_id)

    runner.perform_attack([0])
    runner.perform_defense([0, 1])

    assert runner.state.get_mp(1) == 16
    assert runner.state.get_hp(1) == 37

    assert runner.state.current_phase == GamePhase.PHASE_SUNDRY_SELECT_MIRROR
    assert runner.state.current_actor_id == 0
    assert runner.state.pending_attack_power == 3

    runner.perform_defense([], confirm=True)

    assert runner.state.get_money(0) == 17
    assert runner.state.get_money(1) == 23


def test_ring_multiple_attacks_delay():
    saw_bunbun_id = find_card_by_name("weapons/saw-boom-boom")
    saturn_ring_id = find_card_by_name("armor/saturn-ring")
    leather_clothes_id = find_card_by_name("armor/leather-clothes")

    runner = SimulationRunner()
    runner.state.seed_rng(42)
    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.set_status(0, hp=40, mp=10)
    runner.set_status(1, hp=40, mp=10)

    runner.state.set_true_hand(0, 0, saw_bunbun_id)
    runner.state.set_true_hand(1, 0, saturn_ring_id)
    runner.state.set_true_hand(1, 1, leather_clothes_id)

    runner.perform_attack([0])
    runner.perform_defense([0])

    assert runner.state.current_phase == GamePhase.PHASE_DEFENSE
    assert runner.state.current_actor_id == 1
    assert runner.state.remaining_attacks == 1
    assert runner.state.get_hp(1) == 37

    runner.perform_defense([1])

    assert runner.state.current_phase == GamePhase.PHASE_DEFENSE
    assert runner.state.current_actor_id == 0
    assert runner.state.pending_attack_power == 6
    assert runner.state.pending_attack_element == godfield_core.Element.ELEM_STONE


def test_ring_counter_super_mirror_chain():
    punch_id = find_card_by_name("weapons/punch")
    venus_ring_id = find_card_by_name("armor/venus-ring")
    super_mirror_id = find_card_by_name("armor/super-mirror")

    runner = SimulationRunner()
    runner.state.seed_rng(42)
    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.set_status(0, hp=40, mp=10, money=20)
    runner.set_status(1, hp=40, mp=10, money=20)

    runner.state.set_true_hand(0, 0, punch_id)
    runner.state.set_true_hand(0, 1, super_mirror_id)
    runner.state.set_true_hand(1, 0, venus_ring_id)

    runner.perform_attack([0])
    runner.perform_defense([0])

    assert runner.state.current_phase == GamePhase.PHASE_SUNDRY_SELECT_MIRROR
    assert runner.state.current_actor_id == 0

    runner.perform_defense([1], confirm=False)

    assert runner.state.current_phase == GamePhase.PHASE_SUNDRY_SELECT_MIRROR
    assert runner.state.current_actor_id == 1
    assert runner.state.pending_attack_power == 3

    runner.perform_defense([], confirm=True)

    assert runner.state.get_money(1) == 17
    assert runner.state.get_money(0) == 23
    assert runner.state.get_hp(1) == 37


def test_venus_ring_insufficient_funds():
    punch_id = find_card_by_name("weapons/punch")
    venus_ring_id = find_card_by_name("armor/venus-ring")

    runner = SimulationRunner()
    runner.state.seed_rng(42)
    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.set_status(0, hp=40, mp=1, money=1)
    runner.set_status(1, hp=40, mp=10, money=20)

    runner.state.set_true_hand(0, 0, punch_id)
    runner.state.set_true_hand(1, 0, venus_ring_id)

    runner.perform_attack([0])
    runner.perform_defense([0])

    assert runner.state.current_phase == GamePhase.PHASE_SUNDRY_SELECT_MIRROR
    assert runner.state.current_actor_id == 0

    runner.perform_defense([], confirm=True)

    assert runner.state.get_money(0) == 0
    assert runner.state.get_mp(0) == 0
    assert runner.state.get_hp(0) == 39

    assert runner.state.get_money(1) == 23


def test_venus_ring_death_insufficient_funds():
    punch_id = find_card_by_name("weapons/punch")
    venus_ring_id = find_card_by_name("armor/venus-ring")

    runner = SimulationRunner()
    runner.state.seed_rng(42)
    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.set_status(0, hp=1, mp=0, money=0)
    runner.set_status(1, hp=40, mp=10, money=20)

    runner.state.set_true_hand(0, 0, punch_id)
    runner.state.set_true_hand(1, 0, venus_ring_id)

    runner.perform_attack([0])
    runner.perform_defense([0])

    runner.perform_defense([], confirm=True)

    assert runner.state.get_hp(0) == 0
    assert runner.state.get_money(1) == 23


def test_special_rings_defense_restrictions():
    jupiter_ring = find_card_by_name("armor/jupiter-ring")
    uranus_ring = find_card_by_name("armor/uranus-ring")
    pluto_ring = find_card_by_name("armor/pluto-ring")
    mercury_ring = find_card_by_name("armor/mercury-ring")

    wood_shield = find_card_by_name('armor/wood-shield')
    super_mirror = find_card_by_name('armor/super-mirror')

    rings = [jupiter_ring, uranus_ring, pluto_ring, mercury_ring]

    for ring_id in rings:
        runner = SimulationRunner()
        runner.state.current_phase = GamePhase.PHASE_SUNDRY_SELECT_MIRROR
        runner.state.current_actor_id = 0
        runner.state.attacker_id = 1
        runner.state.defender_id = 0
        runner.state.pending_attack_source_id = ring_id
        runner.state.pending_attack_power = 0

        runner.set_hand(0, [wood_shield, super_mirror])

        legal = godfield_core.get_legal_actions(runner.state)
        assert not legal[int(ActionType.ACTION_SELECT_HAND_0)]
        assert legal[int(ActionType.ACTION_SELECT_HAND_1)]


def test_ring_curse_effects():
    punch_id = find_card_by_name("weapons/punch")
    uranus_ring = find_card_by_name("armor/uranus-ring")
    pluto_ring = find_card_by_name("armor/pluto-ring")
    mercury_ring = find_card_by_name("armor/mercury-ring")

    # 1. 天王の指輪 -> 閃光 (CURSE_FLASH)
    runner = SimulationRunner()
    runner.state.seed_rng(42)
    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.set_status(0, hp=40, mp=10)
    runner.set_status(1, hp=40, mp=10)
    runner.state.set_true_hand(0, 0, punch_id)
    runner.state.set_true_hand(1, 0, uranus_ring)

    runner.perform_attack([0])
    runner.perform_defense([0])
    runner.perform_defense([], confirm=True)

    assert runner.state.get_curses(0, godfield_core.CurseType.CURSE_FLASH) == True

    # 2. 冥王の指輪 -> 暗雲 (CURSE_DARK_CLOUD)
    runner = SimulationRunner()
    runner.state.seed_rng(42)
    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.set_status(0, hp=40, mp=10)
    runner.set_status(1, hp=40, mp=10)
    runner.state.set_true_hand(0, 0, punch_id)
    runner.state.set_true_hand(1, 0, pluto_ring)

    runner.perform_attack([0])
    runner.perform_defense([0])
    runner.perform_defense([], confirm=True)

    assert runner.state.get_curses(0, godfield_core.CurseType.CURSE_DARK_CLOUD) == True

    # 3. 水星の指輪 -> 霧 (CURSE_FOG)
    runner = SimulationRunner()
    runner.state.seed_rng(42)
    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.set_status(0, hp=40, mp=10)
    runner.set_status(1, hp=40, mp=10)
    runner.state.set_true_hand(0, 0, punch_id)
    runner.state.set_true_hand(1, 0, mercury_ring)

    runner.perform_attack([0])
    runner.perform_defense([0])
    runner.perform_defense([], confirm=True)

    assert runner.state.get_curses(0, godfield_core.CurseType.CURSE_FOG) == True
