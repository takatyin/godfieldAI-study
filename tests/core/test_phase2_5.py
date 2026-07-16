import godfield_core
from godfield_core import ActionType

from .test_utils import SimulationRunner, find_card_by_name, find_card_by_type


def test_element_mixing_attack():
    """
    検証内容: 複数属性の攻撃を重ね合わせた際の属性混成ルールのテスト。
    - 異なる属性同士を混ぜ合わせると無属性（None）になる。
    - 光属性は混成において「ニュートラル」として振る舞う（他の属性を上書きせず、他の属性が存在すればその属性になる）。

    具体的には以下の5パターンを検証する：
    1. 光属性（ベース） + 光属性（プラス） = 光属性
    2. 光属性（ベース） + 火属性（プラス） = 火属性
    3. 火属性（ベース） + 光属性（プラス） = 火属性
    4. 火属性（ベース） + 土属性（プラス） = 無属性
    5. 火属性（ベース） + 無属性（プラス） = 無属性
    """
    runner = SimulationRunner()

    light_base = find_card_by_name("聖剣")  # 光ATK9
    light_plus = find_card_by_name("輝きのカケラ")  # 光+ATK1
    fire_base = find_card_by_name("ブレイズブレイド")  # 火ATK5
    fire_plus = find_card_by_name("ファイヤークロスボウ")  # 火+ATK4
    stone_plus = find_card_by_name("新石器トマホーク")  # 土+ATK7
    none_plus = find_card_by_name("ブーメラン")  # +ATK3

    # 1. 光属性（ベース） + 光属性（プラス） = 光属性
    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_num_staged_cards(0, 0)
    runner.state.set_true_hand(0, 0, light_base)
    runner.state.set_true_hand(0, 1, light_plus)
    runner.step(ActionType.ACTION_SELECT_HAND_0)  # light base (transitions to PHASE_ATTACK_PLUS)
    runner.step(ActionType.ACTION_SELECT_HAND_1)  # light plus
    runner.step(ActionType.ACTION_TARGET_OPP)  # EXECUTE_OPP
    assert runner.state.pending_attack_element == godfield_core.Element.ELEM_LIGHT

    # 2. 光属性（ベース） + 火属性（プラス） = 火属性
    runner.reset_state()
    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_num_staged_cards(0, 0)
    runner.state.set_true_hand(0, 0, light_base)
    runner.state.set_true_hand(0, 1, fire_plus)
    runner.step(ActionType.ACTION_SELECT_HAND_0)  # light base (transitions to PHASE_ATTACK_PLUS)
    runner.step(ActionType.ACTION_SELECT_HAND_1)  # fire plus
    runner.step(ActionType.ACTION_TARGET_OPP)  # EXECUTE_OPP
    assert runner.state.pending_attack_element == godfield_core.Element.ELEM_FIRE

    # 3. 火属性（ベース） + 光属性（プラス） = 火属性
    runner.reset_state()
    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_num_staged_cards(0, 0)
    runner.state.set_true_hand(0, 0, fire_base)
    runner.state.set_true_hand(0, 1, light_plus)
    runner.step(ActionType.ACTION_SELECT_HAND_0)  # fire base (transitions to PHASE_ATTACK_PLUS)
    runner.step(ActionType.ACTION_SELECT_HAND_1)  # light plus
    runner.step(ActionType.ACTION_TARGET_OPP)  # EXECUTE_OPP
    assert runner.state.pending_attack_element == godfield_core.Element.ELEM_FIRE

    # 4. 火属性（ベース） + 土属性（プラス） = 無属性
    runner.reset_state()
    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_num_staged_cards(0, 0)
    runner.state.set_true_hand(0, 0, fire_base)
    runner.state.set_true_hand(0, 1, stone_plus)
    runner.step(ActionType.ACTION_SELECT_HAND_0)  # fire base (transitions to PHASE_ATTACK_PLUS)
    runner.step(ActionType.ACTION_SELECT_HAND_1)  # earth plus
    runner.step(ActionType.ACTION_TARGET_OPP)  # EXECUTE_OPP
    assert runner.state.pending_attack_element == godfield_core.Element.ELEM_NONE

    # 5. 火属性（ベース） + 無属性（プラス） = 無属性
    runner.reset_state()
    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_num_staged_cards(0, 0)
    runner.state.set_true_hand(0, 0, fire_base)
    runner.state.set_true_hand(0, 1, none_plus)
    runner.step(ActionType.ACTION_SELECT_HAND_0)  # fire base (transitions to PHASE_ATTACK_PLUS)
    runner.step(ActionType.ACTION_SELECT_HAND_1)  # none plus
    runner.step(ActionType.ACTION_TARGET_OPP)  # EXECUTE_OPP
    assert runner.state.pending_attack_element == godfield_core.Element.ELEM_NONE


def test_element_defense_masking():
    """
    検証内容: 属性攻撃に対する防具の防御合法手（マッチング制限ルール）のテスト。
    - 火属性の攻撃を受けた際、手札にある防具のうち有効な属性防具（水属性）や全属性ガード（虹のカーテン）のみが使用可能となり、
      無効な属性防具（火属性など）が非合法としてマスクされることを確認。
    - 虹のカーテン（全属性ガード）を使用した後は、後続の防具としてあらゆる防具が追加使用可能になることを確認。
    """
    runner = SimulationRunner()

    fire_sword = find_card_by_name("ブレイズブレイド")
    fire_shield = find_card_by_name("フレイムブーツ")
    water_shield = find_card_by_name("アイスブーツ")
    rainbow = find_card_by_name("虹のカーテン")

    runner.state.set_true_hand(0, 0, fire_sword)
    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0

    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_TARGET_OPP)  # EXECUTE_OPP

    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE

    runner.state.set_true_hand(1, 0, fire_shield)
    runner.state.set_true_hand(1, 1, water_shield)
    runner.state.set_true_hand(1, 2, rainbow)

    legal_actions = godfield_core.get_legal_actions(runner.state)

    # 相手は火属性の攻撃に対して、
    # 0: fire_shield (非合法)
    # 1: water_shield (合法)
    # 2: rainbow (合法)
    assert legal_actions[ActionType.ACTION_SELECT_HAND_0] == False
    assert legal_actions[ActionType.ACTION_SELECT_HAND_1] == True
    assert legal_actions[ActionType.ACTION_SELECT_HAND_2] == True

    runner.step(ActionType.ACTION_SELECT_HAND_2)  # 虹のカーテン

    legal_actions = godfield_core.get_legal_actions(runner.state)
    assert legal_actions[ActionType.ACTION_SELECT_HAND_0] == True
    assert legal_actions[ActionType.ACTION_SELECT_HAND_1] == True

    runner.step(ActionType.ACTION_SELECT_HAND_0)  # 火属性防具 (虹のカーテン後はOK)

    legal_actions = godfield_core.get_legal_actions(runner.state)
    assert legal_actions[ActionType.ACTION_CONFIRM] == True

    runner.step(ActionType.ACTION_CONFIRM)
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_MAIN
    assert runner.state.current_actor_id == 1


def test_element_light_masking():
    """
    検証内容: 光属性攻撃に対する防具の防御合法手（マッチング制限ルール）のテスト。
    - プレイヤーが光属性の攻撃を受けた際、全属性ガード（虹のカーテン）以外の通常の属性・無属性防具では
      防御できないことを確認。
    - 虹のカーテンを使用した後は、後続の防具としてあらゆる防具が追加使用可能になることを確認。
    """
    runner = SimulationRunner()

    light_sword = find_card_by_name("聖剣")
    rainbow = find_card_by_name("虹のカーテン")

    normal_shield = find_card_by_type(type="defense", element="")
    fire_shield = find_card_by_type(type="defense", element="火")
    water_shield = find_card_by_type(type="defense", element="水")
    wood_shield = find_card_by_type(type="defense", element="木")
    stone_shield = find_card_by_type(type="defense", element="土")

    runner.state.set_true_hand(0, 0, light_sword)
    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0

    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_TARGET_OPP)  # EXECUTE_OPP

    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE

    runner.set_hand(
        1, [normal_shield, fire_shield, water_shield, wood_shield, stone_shield, rainbow]
    )

    legal_actions = godfield_core.get_legal_actions(runner.state)

    # 相手は光属性の攻撃に対して、
    # 0~4: 通常の防具はすべて非合法
    # 5: 虹のカーテンのみ合法
    assert legal_actions[ActionType.ACTION_SELECT_HAND_0] == False
    assert legal_actions[ActionType.ACTION_SELECT_HAND_1] == False
    assert legal_actions[ActionType.ACTION_SELECT_HAND_2] == False
    assert legal_actions[ActionType.ACTION_SELECT_HAND_3] == False
    assert legal_actions[ActionType.ACTION_SELECT_HAND_4] == False
    assert legal_actions[ActionType.ACTION_SELECT_HAND_5] == True

    runner.step(ActionType.ACTION_SELECT_HAND_5)  # 虹のカーテン

    legal_actions = godfield_core.get_legal_actions(runner.state)
    assert legal_actions[ActionType.ACTION_SELECT_HAND_0] == True
    assert legal_actions[ActionType.ACTION_SELECT_HAND_1] == True
    assert legal_actions[ActionType.ACTION_SELECT_HAND_2] == True
    assert legal_actions[ActionType.ACTION_SELECT_HAND_3] == True
    assert legal_actions[ActionType.ACTION_SELECT_HAND_4] == True

    runner.step(ActionType.ACTION_SELECT_HAND_0)  # 無属性防具 (虹のカーテン後はOK)

    legal_actions = godfield_core.get_legal_actions(runner.state)
    assert legal_actions[ActionType.ACTION_CONFIRM] == True

    runner.step(ActionType.ACTION_CONFIRM)
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_MAIN
    assert runner.state.current_actor_id == 1


def test_darkness_attack_insta_death():
    """
    検証内容: 闇属性攻撃による即死効果のテスト。
    - 闇属性の攻撃を防具なし（あるいは虹のカーテン以外の防具）で受けた際、ダメージ量に関わらずHPが0（即死）になることを確認。
    """
    runner = SimulationRunner()

    runner.state.current_phase = godfield_core.GamePhase.PHASE_DEFENSE
    runner.state.current_actor_id = 0
    runner.state.pending_attack_element = godfield_core.Element.ELEM_DARKNESS
    runner.state.pending_attack_power = 10
    runner.state.set_hp(0, 40)

    # 防御をせず確定（即死）
    runner.step(ActionType.ACTION_CONFIRM)

    # 闇属性のダメージ -> 即死
    assert runner.state.get_hp(0) == 0
    assert runner.state.is_done == True


def test_darkness_attack_rainbow_defense():
    """
    検証内容: 闇属性攻撃に対する虹のカーテン（全属性ガード）の無効化処理のテスト。
    - 闇属性 of 攻撃に対して虹のカーテンで防御した際、即死効果が中和され、攻撃力に応じた通常のダメージ計算のみが適用されることを確認。
    """
    runner = SimulationRunner()

    rainbow = find_card_by_name("虹のカーテン")

    runner.state.current_phase = godfield_core.GamePhase.PHASE_DEFENSE
    runner.state.current_actor_id = 0
    runner.state.pending_attack_element = godfield_core.Element.ELEM_DARKNESS
    runner.state.pending_attack_power = 10
    runner.state.set_hp(0, 40)

    runner.state.set_true_hand(0, 0, rainbow)

    # 虹のカーテンで防御
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_CONFIRM)

    # 虹のカーテンは即死を防ぎ、攻撃力分のダメージのみを適用する
    # (期待値: 40 - 10 = 30)
    assert runner.state.get_hp(0) == 30
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_MAIN
