import godfield_core
from godfield_core import ActionType
from tests.core.test_utils import SimulationRunner, find_card_by_name, find_card_by_type


def test_element_mixing_light_light():
    """
    検証内容: 光属性と光属性の混成テスト。
    - 光属性（ベース: 聖剣）に光属性（プラス: 輝きのカケラ）を重ねた場合、最終属性が光属性（ELEM_LIGHT）になることを確認します。
    """
    runner = SimulationRunner()
    light_base = find_card_by_name("聖剣")
    light_plus = find_card_by_name("輝きのカケラ")

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_num_staged_cards(0, 0)
    runner.state.set_true_hand(0, 0, light_base)
    runner.state.set_true_hand(0, 1, light_plus)

    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_SELECT_HAND_1)
    runner.step(ActionType.ACTION_TARGET_OPP)

    assert runner.state.pending_attack_element == godfield_core.Element.ELEM_LIGHT


def test_element_mixing_light_fire():
    """
    検証内容: 光属性（ベース）に火属性（プラス）を混ぜた混成テスト。
    - 光属性は「ニュートラル」として振る舞うため、他の属性が存在する場合はその属性に変化します。
    - 光属性（ベース: 聖剣）に火属性（プラス: ファイヤークロスボウ）を重ねた場合、最終属性が火属性（ELEM_FIRE）になることを確認します。
    """
    runner = SimulationRunner()
    light_base = find_card_by_name("聖剣")
    fire_plus = find_card_by_name("ファイヤークロスボウ")

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_num_staged_cards(0, 0)
    runner.state.set_true_hand(0, 0, light_base)
    runner.state.set_true_hand(0, 1, fire_plus)

    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_SELECT_HAND_1)
    runner.step(ActionType.ACTION_TARGET_OPP)

    assert runner.state.pending_attack_element == godfield_core.Element.ELEM_FIRE


def test_element_mixing_fire_light():
    """
    検証内容: 火属性（ベース）に光属性（プラス）を混ぜた混成テスト。
    - 火属性（ベース: ブレイズブレイド）に光属性（プラス: 輝きのカケラ）を重ねた場合、光属性のニュートラル性により、最終属性が火属性（ELEM_FIRE）に維持されることを確認します。
    """
    runner = SimulationRunner()
    fire_base = find_card_by_name("ブレイズブレイド")
    light_plus = find_card_by_name("輝きのカケラ")

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_num_staged_cards(0, 0)
    runner.state.set_true_hand(0, 0, fire_base)
    runner.state.set_true_hand(0, 1, light_plus)

    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_SELECT_HAND_1)
    runner.step(ActionType.ACTION_TARGET_OPP)

    assert runner.state.pending_attack_element == godfield_core.Element.ELEM_FIRE


def test_element_mixing_fire_earth():
    """
    検証内容: 異なる通常属性同士（火＋土）を混ぜた混成テスト（無属性化）。
    - 異なる属性（火ベース: ブレイズブレイド、土プラス: 新石器トマホーク）を混成した場合、互いの属性が打ち消し合い、無属性（ELEM_NONE）になることを確認します。
    """
    runner = SimulationRunner()
    fire_base = find_card_by_name("ブレイズブレイド")
    stone_plus = find_card_by_name("新石器トマホーク")

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_num_staged_cards(0, 0)
    runner.state.set_true_hand(0, 0, fire_base)
    runner.state.set_true_hand(0, 1, stone_plus)

    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_SELECT_HAND_1)
    runner.step(ActionType.ACTION_TARGET_OPP)

    assert runner.state.pending_attack_element == godfield_core.Element.ELEM_NONE


def test_element_mixing_fire_none():
    """
    検証内容: 有属性（火）に無属性（プラス）を混ぜた混成テスト（無属性化）。
    - 火ベース（ブレイズブレイド）に無属性プラス（ブーメラン）を重ねた場合、無属性が混ざるため最終属性が無属性（ELEM_NONE）になることを確認します。
    """
    runner = SimulationRunner()
    fire_base = find_card_by_name("ブレイズブレイド")
    none_plus = find_card_by_name("ブーメラン")

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_num_staged_cards(0, 0)
    runner.state.set_true_hand(0, 0, fire_base)
    runner.state.set_true_hand(0, 1, none_plus)

    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_SELECT_HAND_1)
    runner.step(ActionType.ACTION_TARGET_OPP)

    assert runner.state.pending_attack_element == godfield_core.Element.ELEM_NONE


def test_element_mixing_none_fire():
    """
    検証内容: 無属性に有属性（火プラス）を混ぜた混成テスト（無属性化）。
    - 無属性ベース（ブーメラン）に火プラス（ファイヤークロスボウ）を重ねた場合、最終属性が無属性（ELEM_NONE）になることを確認します。
    """
    runner = SimulationRunner()
    none_base = find_card_by_name("ブーメラン")
    fire_plus = find_card_by_name("ファイヤークロスボウ")

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_num_staged_cards(0, 0)
    runner.state.set_true_hand(0, 0, none_base)
    runner.state.set_true_hand(0, 1, fire_plus)

    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_SELECT_HAND_1)
    runner.step(ActionType.ACTION_TARGET_OPP)

    assert runner.state.pending_attack_element == godfield_core.Element.ELEM_NONE


def test_element_mixing_none_light():
    """
    検証内容: 無属性に光属性を混ぜた混成テスト（無属性化）。
    - 無属性ベース（ブーメラン）に光プラス（輝きのカケラ）を重ねた場合、最終属性が無属性（ELEM_NONE）になることを確認します。
    """
    runner = SimulationRunner()
    none_base = find_card_by_name("ブーメラン")
    light_plus = find_card_by_name("輝きのカケラ")

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_num_staged_cards(0, 0)
    runner.state.set_true_hand(0, 0, none_base)
    runner.state.set_true_hand(0, 1, light_plus)

    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_SELECT_HAND_1)
    runner.step(ActionType.ACTION_TARGET_OPP)

    assert runner.state.pending_attack_element == godfield_core.Element.ELEM_NONE


def test_element_defense_masking_matching_rules():
    """
    検証内容: 属性防御時の防具マスク制限ルール。
    - 火属性の攻撃を受けた際、無効な属性防具（火属性のフレイムブーツ）は非合法手（False）としてマスクされることを確認します。
    - 有効な属性防具（水属性のアイスブーツ）および全属性防護（虹のカーテン）のみが合法手（True）として選択可能であることを確認します。
    """
    runner = SimulationRunner()
    fire_sword = find_card_by_name("ブレイズブレイド")
    fire_shield = find_card_by_name("フレイムブーツ")
    water_shield = find_card_by_name("アイスブーツ")
    rainbow = find_card_by_name("虹のカーテン") or find_card_by_name("armor/rainbow-curtain")

    runner.state.set_true_hand(0, 0, fire_sword)
    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0

    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_TARGET_OPP)

    runner.state.set_true_hand(1, 0, fire_shield)
    runner.state.set_true_hand(1, 1, water_shield)
    runner.state.set_true_hand(1, 2, rainbow)

    legal_actions = godfield_core.get_legal_actions(runner.state)

    # 相手は火属性の攻撃に対してフレイムブーツ(火)は非合法、アイスブーツ(水)とカーテンは合法
    assert legal_actions[ActionType.ACTION_SELECT_HAND_0] == False
    assert legal_actions[ActionType.ACTION_SELECT_HAND_1] == True
    assert legal_actions[ActionType.ACTION_SELECT_HAND_2] == True


def test_element_defense_curtain_unmasks_all_shields():
    """
    検証内容: 虹のカーテン（全属性防護）使用後の防具重ねがけ制限緩和。
    - 火属性の攻撃に対し、1枚目に「虹のカーテン」を使用した場合、2枚目の防具にはあらゆる属性・無属性防具（本来マスクされていた火属性のフレイムブーツを含む）が合法手として重ねられるようになることを確認します。
    """
    runner = SimulationRunner()
    fire_sword = find_card_by_name("ブレイズブレイド")
    fire_shield = find_card_by_name("フレイムブーツ")
    water_shield = find_card_by_name("アイスブーツ")
    rainbow = find_card_by_name("虹のカーテン") or find_card_by_name("armor/rainbow-curtain")

    runner.state.set_true_hand(0, 0, fire_sword)
    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0

    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_TARGET_OPP)

    runner.state.set_true_hand(1, 0, fire_shield)
    runner.state.set_true_hand(1, 1, water_shield)
    runner.state.set_true_hand(1, 2, rainbow)

    # 1枚目に虹のカーテンを使用
    runner.step(ActionType.ACTION_SELECT_HAND_2)

    # 2枚目には本来非合法だったフレイムブーツ(火: スロット0)が選択可能になる
    legal_actions = godfield_core.get_legal_actions(runner.state)
    assert legal_actions[ActionType.ACTION_SELECT_HAND_0] == True
    assert legal_actions[ActionType.ACTION_SELECT_HAND_1] == True


def test_element_light_defense_rules():
    """
    検証内容: 光属性攻撃に対する防御制限ルール。
    - 光属性の攻撃（聖剣）を受けた際、通常の属性・無属性防具（スロット0~4）はすべて非合法となり、全属性防護（虹のカーテン: スロット5）のみが合法となることを確認します。
    - 虹のカーテンを1枚目に置いた後は、無属性防具が追加で選択可能になることを確認します。
    """
    runner = SimulationRunner()
    light_sword = find_card_by_name("聖剣")
    rainbow = find_card_by_name("虹のカーテン") or find_card_by_name("armor/rainbow-curtain")

    normal_shield = find_card_by_type(type="defense", element="")
    fire_shield = find_card_by_type(type="defense", element="火")
    water_shield = find_card_by_type(type="defense", element="水")
    wood_shield = find_card_by_type(type="defense", element="木")
    stone_shield = find_card_by_type(type="defense", element="土")

    runner.state.set_true_hand(0, 0, light_sword)
    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0

    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_TARGET_OPP)

    runner.set_hand(1, [normal_shield, fire_shield, water_shield, wood_shield, stone_shield, rainbow])

    legal_actions = godfield_core.get_legal_actions(runner.state)

    # 光属性の攻撃に対して、0~4の通常防具は非合法、5のカーテンのみ合法
    assert legal_actions[ActionType.ACTION_SELECT_HAND_0] == False
    assert legal_actions[ActionType.ACTION_SELECT_HAND_1] == False
    assert legal_actions[ActionType.ACTION_SELECT_HAND_2] == False
    assert legal_actions[ActionType.ACTION_SELECT_HAND_3] == False
    assert legal_actions[ActionType.ACTION_SELECT_HAND_4] == False
    assert legal_actions[ActionType.ACTION_SELECT_HAND_5] == True

    # カーテンを選択
    runner.step(ActionType.ACTION_SELECT_HAND_5)

    # カーテン選択後は、無属性防具（スロット0）が選択可能になる
    legal_actions_after = godfield_core.get_legal_actions(runner.state)
    assert legal_actions_after[ActionType.ACTION_SELECT_HAND_0] == True


def test_darkness_attack_insta_death():
    """
    検証内容: 闇属性攻撃の無防御即死効果。
    - プレイヤーが闇属性攻撃（pending_attack_element = ELEM_DARKNESS）を防御なし（ACTION_CONFIRMのみ）で受けた際、ダメージに関わらずHPが即座に0（即死）になり、ゲーム終了（is_done = True）となることを確認します。
    """
    runner = SimulationRunner()
    runner.state.current_phase = godfield_core.GamePhase.PHASE_DEFENSE
    runner.state.current_actor_id = 0
    runner.state.pending_attack_element = godfield_core.Element.ELEM_DARKNESS
    runner.state.pending_attack_power = 10
    runner.state.set_hp(0, 40)

    # 防御をせず確定（即死）
    runner.step(ActionType.ACTION_CONFIRM)

    # HPが 0 で即死判定、ゲーム終了
    assert runner.state.get_hp(0) == 0
    assert runner.state.is_done == True


def test_darkness_attack_rainbow_defense():
    """
    検証内容: 闇属性攻撃に対する虹のカーテンの無効化（ダメージ化）処理。
    - 闇属性攻撃に対し、「虹のカーテン」を使用した場合、即死効果が中和され、攻撃力（pending_attack_power = 10）に応じた通常の被弾ダメージのみ（40 - 10 = 30）が適用されて生存（ゲームが続行）することを確認します。
    """
    runner = SimulationRunner()
    rainbow = find_card_by_name("虹のカーテン") or find_card_by_name("armor/rainbow-curtain")

    runner.state.current_phase = godfield_core.GamePhase.PHASE_DEFENSE
    runner.state.current_actor_id = 0
    runner.state.pending_attack_element = godfield_core.Element.ELEM_DARKNESS
    runner.state.pending_attack_power = 10
    runner.state.set_hp(0, 40)
    runner.state.set_true_hand(0, 0, rainbow)

    # 虹のカーテンで防御
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_CONFIRM)

    # 即死せず、攻撃力分のみ被弾 (40 - 10 = 30)
    assert runner.state.get_hp(0) == 30
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_MAIN


def test_element_mixing_darkness_light():
    """
    検証内容: 闇属性と光属性の混成テスト（無属性化）。
    - 闇属性（ベース: 死神のカマ）に光属性（プラス: 輝きのカケラ）を重ねた場合、光属性が闇属性の代わりになれないため、最終属性が無属性（ELEM_NONE）になることを確認します。
    """
    runner = SimulationRunner()
    dark_base = find_card_by_name("死神のカマ")
    light_plus = find_card_by_name("輝きのカケラ")

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_num_staged_cards(0, 0)
    runner.state.set_true_hand(0, 0, dark_base)
    runner.state.set_true_hand(0, 1, light_plus)

    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_SELECT_HAND_1)
    runner.step(ActionType.ACTION_TARGET_OPP)

    # 無属性（ELEM_NONE）になっていることをアサート
    assert runner.state.pending_attack_element == godfield_core.Element.ELEM_NONE
    assert runner.state.pending_attack_power == 11  # 10 + 1 = 11


def test_element_mixing_darkness_darkness():
    """
    検証内容: 闇属性と闇属性の混成テスト。
    - 闇属性（ベース: 死神のカマ）に闇属性（プラス: 冥矢）を重ねた場合、同一属性のため、最終属性が闇属性（ELEM_DARKNESS）に維持されることを確認します。
    """
    runner = SimulationRunner()
    dark_base = find_card_by_name("死神のカマ")
    dark_plus = find_card_by_name("冥矢")

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_num_staged_cards(0, 0)
    runner.state.set_true_hand(0, 0, dark_base)
    runner.state.set_true_hand(0, 1, dark_plus)

    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_SELECT_HAND_1)
    runner.step(ActionType.ACTION_TARGET_OPP)

    # 闇属性（ELEM_DARKNESS）のままであることをアサート
    assert runner.state.pending_attack_element == godfield_core.Element.ELEM_DARKNESS
    assert runner.state.pending_attack_power == 15  # 10 + 5 = 15


def test_element_mixing_light_darkness():
    """
    検証内容: 光属性と闇属性の混成テスト（無属性化、逆順）。
    - 光属性（ベース: 聖剣）に闇属性（プラス: 冥矢）を重ねた場合、光属性が闇属性の代わりになれないため、最終属性が無属性（ELEM_NONE）になることを確認します。
    """
    runner = SimulationRunner()
    light_base = find_card_by_name("聖剣")
    dark_plus = find_card_by_name("冥矢")

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_num_staged_cards(0, 0)
    runner.state.set_true_hand(0, 0, light_base)
    runner.state.set_true_hand(0, 1, dark_plus)

    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_SELECT_HAND_1)
    runner.step(ActionType.ACTION_TARGET_OPP)

    # 無属性（ELEM_NONE）になっていることをアサート
    assert runner.state.pending_attack_element == godfield_core.Element.ELEM_NONE
    assert runner.state.pending_attack_power == 14  # 9 + 5 = 14


def test_chikurincho_and_wand_of_mystic_water():
    """
    検証内容: ちくりんちょ（闇属性）に魔水のワンド（属性変更: 水）を重ねた場合、最終属性が水属性（ELEM_WATER）になることを確認します。
    """
    runner = SimulationRunner()
    chikurincho = find_card_by_name("ちくりんちょ")
    wand = find_card_by_name("魔水のワンド")

    runner.set_status(player=0, hp=99, mp=50, money=50)
    runner.set_status(player=1, hp=50, mp=50, money=50)

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_num_staged_cards(0, 0)
    runner.state.set_true_hand(0, 0, chikurincho)
    runner.state.set_true_hand(0, 1, wand)

    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_SELECT_HAND_1)
    print(f"DEBUG: Before target opp: phase={runner.state.current_phase}")
    runner.step(ActionType.ACTION_TARGET_OPP)
    print(f"DEBUG: After target opp: pending_elem={runner.state.pending_attack_element}, power={runner.state.pending_attack_power}, phase={runner.state.current_phase}")

    runner.step(ActionType.ACTION_CONFIRM)
    print(f"DEBUG: After confirm: hp1={runner.state.get_hp(1)}, phase={runner.state.current_phase}")
    obs = godfield_core.get_observation(runner.state, 0)
    for ev in obs.get_history():
        print(f"EV: actor={ev.actor}, type={ev.event_type}, card={ev.card_id}, target={ev.target_id}, val={ev.value}")
    assert runner.state.get_hp(1) == 44
