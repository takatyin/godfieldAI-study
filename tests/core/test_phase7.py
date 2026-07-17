import godfield_core
from godfield_core import ActionType, GamePhase
from .test_utils import SimulationRunner, find_card_by_name


def test_weapon_and_miracle_stacking():
    """
    検証内容: 武器 + 奇跡の重ねがけは「武器攻撃」として扱われ、PHASE_DEFENSEへ遷移する。
    """
    runner = SimulationRunner()
    punch_id = find_card_by_name("パンチ")
    fireball_id = find_card_by_name("＜火の玉＞")

    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.set_status(0, hp=40, mp=10) # 十分なMPを付与

    runner.state.set_true_hand(0, 0, punch_id)
    runner.state.set_true_hand(0, 1, fireball_id)

    # 1. 武器 (パンチ) を出す -> PHASE_ATTACK_PLUSへ
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    assert runner.state.current_phase == GamePhase.PHASE_ATTACK_PLUS

    # 2. 火の玉を追加で出す (TIMING_ATK_PLUS)
    runner.step(ActionType.ACTION_SELECT_HAND_1)

    # 3. 相手を対象に攻撃決定 -> PHASE_DEFENSE (武器攻撃の守り) へ遷移するはず
    runner.step(ActionType.ACTION_TARGET_OPP)
    assert runner.state.current_phase == GamePhase.PHASE_DEFENSE


def test_miracle_and_miracle_stacking():
    """
    検証内容: 奇跡 + 奇跡の重ねがけは「武器攻撃」として扱われ、PHASE_DEFENSEへ遷移する。
    """
    runner = SimulationRunner()
    fireball_id = find_card_by_name("＜火の玉＞")

    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.set_status(0, hp=40, mp=10) # 十分なMPを付与

    runner.state.set_true_hand(0, 0, fireball_id)
    runner.state.set_true_hand(0, 1, fireball_id)

    # 1. 火の玉を出す -> PHASE_MIRACLE_PLUSへ
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    assert runner.state.current_phase == GamePhase.PHASE_MIRACLE_PLUS

    # 2. 火の玉を追加で出す (TIMING_ATK_PLUS)
    runner.step(ActionType.ACTION_SELECT_HAND_1)

    # 3. 相手を対象に攻撃決定 -> PHASE_DEFENSE (武器攻撃の守り) へ遷移するはず
    runner.step(ActionType.ACTION_TARGET_OPP)
    assert runner.state.current_phase == GamePhase.PHASE_DEFENSE


def test_miracle_and_spiritual_card_stacking():
    """
    検証内容: 奇跡 + 精霊の足袋 (Spiritual socks) の重ねがけは、
    奇跡攻撃 (PHASE_MIRACLE_DEFENSE) のまま遷移し、消費MPが0になる。
    """
    runner = SimulationRunner()
    fireball_id = find_card_by_name("＜火の玉＞") # MP 2
    spiritual_socks_id = find_card_by_name("精霊の足袋")

    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.set_status(0, hp=40, mp=10) # MP=10で開始

    runner.state.set_true_hand(0, 0, fireball_id)
    runner.state.set_true_hand(0, 1, spiritual_socks_id)

    # 1. 火の玉を出す -> PHASE_MIRACLE_PLUSへ
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    assert runner.state.current_phase == GamePhase.PHASE_MIRACLE_PLUS

    # 2. 精霊の足袋を追加で出す (TIMING_MIRACLE_PLUS)
    runner.step(ActionType.ACTION_SELECT_HAND_1)

    # 3. 相手を対象に攻撃決定 -> PHASE_MIRACLE_DEFENSE (奇跡攻撃の守り) へ遷移するはず
    runner.step(ActionType.ACTION_TARGET_OPP)
    assert runner.state.current_phase == GamePhase.PHASE_MIRACLE_DEFENSE

    # 4. 消費MPが0であることを確認 (MPは10のままのはず)
    assert runner.state.get_mp(0) == 10


def test_mirage_group_attack_flag():
    """
    検証内容: 攻撃に 蜃気楼 (Mirage) を重ねると、全体攻撃フラグ (pending_is_group_attack) が True になり、
    自分自身をターゲットにできなくなる (ACTION_TARGET_SELF が不可になる)。
    """
    runner = SimulationRunner()
    punch_id = find_card_by_name("パンチ")
    mirage_id = find_card_by_name("＜蜃気楼＞")

    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.set_status(0, hp=40, mp=10) # 十分なMPを付与

    runner.state.set_true_hand(0, 0, punch_id)
    runner.state.set_true_hand(0, 1, mirage_id)

    # 1. 武器 (パンチ) を出す -> PHASE_ATTACK_PLUSへ
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    assert runner.state.current_phase == GamePhase.PHASE_ATTACK_PLUS

    # 最初は単体攻撃なので自分もターゲット可能
    actions_before = godfield_core.get_legal_actions(runner.state)
    assert actions_before[ActionType.ACTION_TARGET_SELF] is True

    # 2. 蜃気楼を追加で出す (TIMING_ATK_PLUS)
    runner.step(ActionType.ACTION_SELECT_HAND_1)

    # 全体攻撃フラグがONになっているか確認
    assert runner.state.pending_is_group_attack is True

    # 自分へのターゲットが不可になっているか確認
    actions_after = godfield_core.get_legal_actions(runner.state)
    assert actions_after[ActionType.ACTION_TARGET_SELF] is False
