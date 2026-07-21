import godfield_core
from godfield_core import ActionType, GamePhase
from tests.core.test_utils import SimulationRunner, find_card_by_name


def test_group_attack_mirage_transition():
    """
    検証内容: 単体物理武器攻撃に対する「＜蜃気楼＞」による全体化とフェイズ遷移。
    - 単体武器（銅のこん棒）を選択後、「＜蜃気楼＞」を追加することで、フェイズが全体武器攻撃フェイズ（PHASE_GROUP_WEAPON）に遷移することを確認します。
    - 全体化された後は、他の物理武器（吹き矢）の重ねがけや、自傷攻撃（TARGET_SELF）が非合法手となることを確認します。
    - 精霊のぬいぐるみを追加して、MP消費 0 のまま相手全体をターゲットし、物理防御フェイズ（PHASE_DEFENSE）に遷移できることを確認します。
    """
    runner = SimulationRunner()
    runner.state.seed_rng(0)
    sword_id = find_card_by_name("銅のこん棒")
    mirage_id = find_card_by_name("＜蜃気楼＞")
    doll_id = find_card_by_name("精霊のぬいぐるみ")
    blowpipe_id = find_card_by_name("吹き矢")

    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_mp(0, 10)

    runner.state.set_true_hand(0, 0, sword_id)
    runner.state.set_true_hand(0, 1, mirage_id)
    runner.state.set_true_hand(0, 2, doll_id)
    runner.state.set_true_hand(0, 3, blowpipe_id)

    # 武器選択
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    assert runner.state.current_phase == GamePhase.PHASE_ATTACK_PLUS

    # 蜃気楼を追加 -> 全体化
    runner.step(ActionType.ACTION_SELECT_HAND_1)
    assert runner.state.current_phase == GamePhase.PHASE_GROUP_WEAPON

    # 合法手判定: 吹き矢(スロット3)と自傷は非合法、ぬいぐるみ(スロット2)は合法
    legal_actions = godfield_core.get_legal_actions(runner.state)
    assert legal_actions[ActionType.ACTION_SELECT_HAND_3] is False
    assert legal_actions[ActionType.ACTION_TARGET_SELF] is False
    assert legal_actions[ActionType.ACTION_SELECT_HAND_2] is True

    # ぬいぐるみを追加して相手をターゲット
    runner.step(ActionType.ACTION_SELECT_HAND_2)
    runner.step(ActionType.ACTION_TARGET_OPP)

    # 防御フェイズへ遷移し、MPが減っていないこと
    assert runner.state.current_phase == GamePhase.PHASE_DEFENSE
    assert runner.state.get_mp(0) == 10


def test_group_attack_original_group_weapon():
    """
    検証内容: 生来の全体物理武器攻撃時のフェイズ遷移とターゲット制限。
    - 全体物理武器である「火の粉袋」を選択した際、直接全体武器攻撃フェイズ（PHASE_GROUP_WEAPON）に遷移することを確認します。
    - このフェイズでは、他の武器などの重ねがけが一切非合法になり、相手をターゲット（TARGET_OPP）することのみが合法手となることを確認します。
    """
    runner = SimulationRunner()
    runner.state.seed_rng(0)
    saw_id = find_card_by_name("火の粉袋")
    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_true_hand(0, 0, saw_id)

    # 全体攻撃武器を選択
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    assert runner.state.current_phase == GamePhase.PHASE_GROUP_WEAPON

    # 重ねがけは一切禁止されていることを確認
    legal_actions = godfield_core.get_legal_actions(runner.state)
    for idx in range(18):
        assert legal_actions[ActionType.ACTION_SELECT_HAND_0.value + idx] is False

    assert legal_actions[ActionType.ACTION_TARGET_OPP] is True
    assert legal_actions[ActionType.ACTION_TARGET_SELF] is False

    # ターゲットして確定
    runner.step(ActionType.ACTION_TARGET_OPP)
    assert runner.state.current_phase == GamePhase.PHASE_DEFENSE


def test_group_attack_original_group_miracle():
    """
    検証内容: 生来の全体奇跡攻撃時のフェイズ遷移とターゲット制限。
    - 全体奇跡である「＜煙＞」を選択した際、直接全体奇跡攻撃フェイズ（PHASE_GROUP_MIRACLE_PLUS）に遷移することを確認します。
    - このフェイズでは、自傷（TARGET_SELF）が非合法手であり、相手全体をターゲット（TARGET_OPP）することが合法手であることを確認します。
    """
    runner = SimulationRunner()
    runner.state.seed_rng(0)
    storm_id = find_card_by_name("＜煙＞")
    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_mp(0, 20)
    runner.state.set_true_hand(0, 0, storm_id)

    # 全体奇跡を選択
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    assert runner.state.current_phase == GamePhase.PHASE_GROUP_MIRACLE_PLUS

    # 自傷は不可、相手攻撃は可
    legal_actions = godfield_core.get_legal_actions(runner.state)
    assert legal_actions[ActionType.ACTION_TARGET_OPP] is True
    assert legal_actions[ActionType.ACTION_TARGET_SELF] is False

    # 攻撃確定
    runner.step(ActionType.ACTION_TARGET_OPP)
    assert runner.state.current_phase == GamePhase.PHASE_MIRACLE_DEFENSE


def test_group_attack_miracle_stacking_group_weapon():
    """
    検証内容: 物理攻撃への奇跡プラス・全体化と複合MP解決。
    - 物理武器「パンチ」を使用し、そこに奇跡「＜火の玉＞」を重ねて属性物理攻撃とする。
    - そこにさらに「＜蜃気楼＞」を追加することで、全体化されて PHASE_GROUP_WEAPON に遷移することを確認します。
    - 「精霊のぬいぐるみ」を追加して、MP消費が 2（火の玉のコスト）のままで攻撃が解決されることを確認します。
    """
    runner = SimulationRunner()
    runner.state.seed_rng(0)
    punch_id = find_card_by_name("パンチ")
    fireball_id = find_card_by_name("＜火の玉＞")
    mirage_id = find_card_by_name("＜蜃気楼＞")
    doll_id = find_card_by_name("精霊のぬいぐるみ")

    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_mp(0, 20)
    runner.state.set_true_hand(0, 0, punch_id)
    runner.state.set_true_hand(0, 1, fireball_id)
    runner.state.set_true_hand(0, 2, mirage_id)
    runner.state.set_true_hand(0, 3, doll_id)

    runner.step(ActionType.ACTION_SELECT_HAND_0)  # パンチ (ATTACK_PLUSへ)
    assert runner.state.current_phase == GamePhase.PHASE_ATTACK_PLUS

    runner.step(ActionType.ACTION_SELECT_HAND_1)  # 火の玉 (ATTACK_PLUSのまま)
    assert runner.state.current_phase == GamePhase.PHASE_ATTACK_PLUS

    runner.step(ActionType.ACTION_SELECT_HAND_2)  # 蜃気楼 (GROUP_WEAPONへ)
    assert runner.state.current_phase == GamePhase.PHASE_GROUP_WEAPON

    # ぬいぐるみを追加して相手をターゲット
    runner.step(ActionType.ACTION_SELECT_HAND_3)
    runner.step(ActionType.ACTION_TARGET_OPP)

    # 最終的に防御フェイズへ移行し、MPは 20 - 2 = 18 となっていること
    assert runner.state.current_phase == GamePhase.PHASE_DEFENSE
    assert runner.state.get_mp(0) == 18


def test_mirage_group_attack_flag_prevents_self_target():
    """
    検証内容: 蜃気楼による全体攻撃フラグ変更と自傷ターゲットの不許可。
    - 通常の単体武器「パンチ」を選択した段階では、自傷（TARGET_SELF）が合法であることを確認します。
    - 「＜蜃気楼＞」をプラスした時点で、全体攻撃フラグ（pending_is_group_attack）が True になり、自傷（TARGET_SELF）が非合法手になることを確認します。
    """
    runner = SimulationRunner()
    punch_id = find_card_by_name("パンチ")
    mirage_id = find_card_by_name("＜蜃気楼＞")

    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.set_status(0, hp=40, mp=10)

    runner.state.set_true_hand(0, 0, punch_id)
    runner.state.set_true_hand(0, 1, mirage_id)

    # パンチを選択
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    assert runner.state.current_phase == GamePhase.PHASE_ATTACK_PLUS

    # 最初は自傷可能であること
    actions_before = godfield_core.get_legal_actions(runner.state)
    assert actions_before[ActionType.ACTION_TARGET_SELF] is True

    # 蜃気楼を追加
    runner.step(ActionType.ACTION_SELECT_HAND_1)

    # 全体攻撃フラグがONになり、自傷が不可になっていること
    assert runner.state.pending_is_group_attack is True
    actions_after = godfield_core.get_legal_actions(runner.state)
    assert actions_after[ActionType.ACTION_TARGET_SELF] is False


def test_multiple_mirage_stacking_punch():
    """
    検証内容: パンチ -> 蜃気楼 -> 蜃気楼 -> 精霊 -> 蜃気楼 の重ねがけテスト。
    - 3枚の蜃気楼と1枚の精霊を物理攻撃に重ねがけした際、MP消費が合計 10 となり、
      攻撃回数（remaining_attacks）が 3 回の全体物理攻撃になることを確認します。
    """
    runner = SimulationRunner()
    runner.state.seed_rng(0)
    punch_id = find_card_by_name("パンチ")
    mirage_id = find_card_by_name("＜蜃気楼＞")
    doll_id = find_card_by_name("精霊のぬいぐるみ")

    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_mp(0, 30)

    # 手札設定
    runner.state.set_true_hand(0, 0, punch_id)
    runner.state.set_true_hand(0, 1, mirage_id)
    runner.state.set_true_hand(0, 2, mirage_id)
    runner.state.set_true_hand(0, 3, doll_id)
    runner.state.set_true_hand(0, 4, mirage_id)

    runner.step(ActionType.ACTION_SELECT_HAND_0)  # パンチ (PHASE_ATTACK_PLUSへ)
    assert runner.state.current_phase == GamePhase.PHASE_ATTACK_PLUS

    runner.step(ActionType.ACTION_SELECT_HAND_1)  # 蜃気楼 1 (PHASE_GROUP_WEAPONへ)
    assert runner.state.current_phase == GamePhase.PHASE_GROUP_WEAPON

    runner.step(ActionType.ACTION_SELECT_HAND_2)  # 蜃気楼 2 (PHASE_GROUP_WEAPON継続)
    assert runner.state.current_phase == GamePhase.PHASE_GROUP_WEAPON

    runner.step(ActionType.ACTION_SELECT_HAND_3)  # 精霊 (PHASE_GROUP_WEAPON継続)
    assert runner.state.current_phase == GamePhase.PHASE_GROUP_WEAPON

    runner.step(ActionType.ACTION_SELECT_HAND_4)  # 蜃気楼 3 (PHASE_GROUP_WEAPON継続)
    assert runner.state.current_phase == GamePhase.PHASE_GROUP_WEAPON

    # 攻撃確定
    runner.step(ActionType.ACTION_TARGET_OPP)

    # 防御フェイズへ遷移し、MP消費が 10 (蜃気楼1=5, 蜃気楼2=0, 精霊=0, 蜃気楼3=5) となり、
    # 攻撃回数が 3回 に設定されていることを確認
    assert runner.state.current_phase == GamePhase.PHASE_DEFENSE
    assert runner.state.get_mp(0) == 20  # 30 - 10 = 20
    assert runner.state.remaining_attacks == 3


def test_original_group_weapon_cannot_stack_mirage():
    """
    検証内容: 生来の全体攻撃武器「火の粉袋」に対して追加カード（蜃気楼や精霊など）を重ねられないことを確認するテスト。
    """
    runner = SimulationRunner()
    runner.state.seed_rng(0)
    bag_id = find_card_by_name("火の粉袋")
    mirage_id = find_card_by_name("＜蜃気楼＞")

    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_true_hand(0, 0, bag_id)
    runner.state.set_true_hand(0, 1, mirage_id)

    # 火の粉袋を選択
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    assert runner.state.current_phase == GamePhase.PHASE_GROUP_WEAPON

    # 蜃気楼のあるスロット1の選択が非合法であることを確認
    legal_actions = godfield_core.get_legal_actions(runner.state)
    assert legal_actions[ActionType.ACTION_SELECT_HAND_1] is False

