import godfield_core
from godfield_core import ActionType, CurseType, GamePhase
from tests.core.test_utils import SimulationRunner, find_card_by_name


def test_flash_prevents_unaffordable_wall():
    """
    検証内容: 閃光（CurseType.CURSE_FLASH）状態における防具制限とMP制限。
    - 閃光状態のプレイヤーがMP 0の時、手札に「＜壁＞」（消費MP6）と「精霊のぬいぐるみ」（MP相殺）があっても、
      閃光状態のため1枚しか防具カードを置けず、MPが足りない「＜壁＞」を置くことは非合法（False）であること。
    - 精霊のぬいぐるみ単体は防具カードではないため、最初には選択できない（False）。
    - 木の盾（無消費）は合法手（True）であること。
    """
    runner = SimulationRunner()

    wall = find_card_by_name("＜壁＞")
    plushie = find_card_by_name("精霊のぬいぐるみ")
    wooden_shield = find_card_by_name("木の盾")

    # 攻撃情報をセット
    runner.state.current_phase = GamePhase.PHASE_DEFENSE
    runner.state.current_actor_id = 0
    runner.state.pending_attack_element = godfield_core.Element.ELEM_NONE
    runner.state.pending_attack_power = 10
    runner.state.set_hp(0, 40)
    runner.state.set_mp(0, 0)  # MP = 0

    # プレイヤー0を手札と閃光状態にセット
    runner.state.set_num_staged_cards(0, 0)
    runner.state.set_true_hand(0, 0, wall)
    runner.state.set_true_hand(0, 1, plushie)
    runner.state.set_true_hand(0, 2, wooden_shield)
    runner.state.set_curses(0, CurseType.CURSE_FLASH, True)  # 閃光状態

    # 合法手を取得
    legal_actions = godfield_core.get_legal_actions(runner.state)

    # 閃光かつMP 0なので：
    # - 「＜壁＞」は消費6 MPで、精霊のぬいぐるみを重ねられないため非合法 (False)
    assert legal_actions[ActionType.ACTION_SELECT_HAND_0] == False

    # - 「精霊のぬいぐるみ」は単体では防御を開始できないため非合法 (False)
    assert legal_actions[ActionType.ACTION_SELECT_HAND_1] == False

    # - 「木の盾」はMP消費0なので合法 (True)
    assert legal_actions[ActionType.ACTION_SELECT_HAND_2] == True

    # 実際に木の盾で受ける
    runner.step(ActionType.ACTION_SELECT_HAND_2)

    # 閃光状態のため、1枚置いた時点でACTION_CONFIRM以外の選択（他の手札選択）が非合法になることを検証
    legal_actions_after = godfield_core.get_legal_actions(runner.state)
    assert legal_actions_after[ActionType.ACTION_CONFIRM] == True
    assert legal_actions_after[ActionType.ACTION_SELECT_HAND_0] == False
    assert legal_actions_after[ActionType.ACTION_SELECT_HAND_1] == False

    # 防御を確定して完了
    runner.step(ActionType.ACTION_CONFIRM)

    # 木の盾（防御力2）で10ダメージを減算し、40 - (10 - 2) = 32 HPになること
    assert runner.state.get_hp(0) == 32
