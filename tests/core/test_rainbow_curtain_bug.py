# -*- coding: utf-8 -*-
import pytest
import godfield_core
from tests.core.test_utils import SimulationRunner, find_card_by_name


def test_rainbow_curtain_followed_by_elemental_armors_miracle():
    """
    検証内容: 相手の火属性奇跡攻撃(＜炎＞)に対し、防御側が1枚目に「虹のカーテン」を出した直後、
    手札にある各属性の防具(水属性、木属性、土属性、無属性等)がすべて合法手として選択可能かを検証。
    """
    runner = SimulationRunner()

    fire_miracle_id = find_card_by_name("miracles/flame") # 火属性奇跡
    rainbow_curtain_id = find_card_by_name("armor/rainbow-curtain") # 虹のカーテン
    ice_boots_id = find_card_by_name("armor/ice-boots") # 水属性防具
    grove_shield_id = find_card_by_name("armor/grove-shield") # 木属性防具
    iron_shield_id = find_card_by_name("armor/iron-shield") # 無属性防具

    runner.set_status(0, hp=40, mp=20)
    runner.set_status(1, hp=40, mp=20)

    runner.state.set_true_hand(0, 0, fire_miracle_id)
    runner.state.set_true_hand(1, 0, rainbow_curtain_id)
    runner.state.set_true_hand(1, 1, ice_boots_id)
    runner.state.set_true_hand(1, 2, grove_shield_id)
    runner.state.set_true_hand(1, 3, iron_shield_id)

    # P0が＜炎＞でP1に奇跡攻撃
    runner.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
    runner.step(godfield_core.ActionType.ACTION_TARGET_OPP)

    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_MIRACLE_DEFENSE

    # P1が1枚目に「虹のカーテン」(スロット0)を選択・仮置き
    runner.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)

    # 虹のカーテン仮置き後のP1の合法手を取得
    actions = godfield_core.get_legal_actions(runner.state)

    print("スロット1 (水属性 アイスブーツ):", actions[godfield_core.ActionType.ACTION_SELECT_HAND_1])
    print("スロット2 (木属性 林の盾):", actions[godfield_core.ActionType.ACTION_SELECT_HAND_2])
    print("スロット3 (無属性 アイアンシールド):", actions[godfield_core.ActionType.ACTION_SELECT_HAND_3])

    assert actions[godfield_core.ActionType.ACTION_SELECT_HAND_1] is True, "水属性防具が選択可能であること"
    assert actions[godfield_core.ActionType.ACTION_SELECT_HAND_2] is True, "木属性防具が選択可能であること"
    assert actions[godfield_core.ActionType.ACTION_SELECT_HAND_3] is True, "無属性防具が選択可能であること"


def test_rainbow_curtain_followed_by_elemental_armors_weapon():
    """
    検証内容: 相手の火属性武器攻撃(フレアアクス)に対し、防御側が1枚目に「虹のカーテン」を出した直後、
    手札にある各属性の防具(水属性、木属性、土属性、無属性等)がすべて合法手として選択可能かを検証。
    """
    runner = SimulationRunner()

    flare_axe_id = find_card_by_name("weapons/flare-axe") # 火属性武器
    rainbow_curtain_id = find_card_by_name("armor/rainbow-curtain") # 虹のカーテン
    ice_boots_id = find_card_by_name("armor/ice-boots") # 水属性防具
    grove_shield_id = find_card_by_name("armor/grove-shield") # 木属性防具
    iron_shield_id = find_card_by_name("armor/iron-shield") # 無属性防具

    runner.set_status(0, hp=40, mp=20)
    runner.set_status(1, hp=40, mp=20)

    runner.state.set_true_hand(0, 0, flare_axe_id)
    runner.state.set_true_hand(1, 0, rainbow_curtain_id)
    runner.state.set_true_hand(1, 1, ice_boots_id)
    runner.state.set_true_hand(1, 2, grove_shield_id)
    runner.state.set_true_hand(1, 3, iron_shield_id)

    # P0がフレアアクスでP1に物理属性攻撃
    runner.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
    runner.step(godfield_core.ActionType.ACTION_TARGET_OPP)

    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE

    # P1が1枚目に「虹のカーテン」(スロット0)を選択・仮置き
    runner.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)

    # 虹のカーテン仮置き後のP1の合法手を取得
    actions = godfield_core.get_legal_actions(runner.state)

    print("スロット1 (水属性 アイスブーツ):", actions[godfield_core.ActionType.ACTION_SELECT_HAND_1])
    print("スロット2 (木属性 林の盾):", actions[godfield_core.ActionType.ACTION_SELECT_HAND_2])
    print("スロット3 (無属性 アイアンシールド):", actions[godfield_core.ActionType.ACTION_SELECT_HAND_3])

    assert actions[godfield_core.ActionType.ACTION_SELECT_HAND_1] is True, "水属性防具が選択可能であること"
    assert actions[godfield_core.ActionType.ACTION_SELECT_HAND_2] is True, "木属性防具が選択可能であること"
    assert actions[godfield_core.ActionType.ACTION_SELECT_HAND_3] is True, "無属性防具が選択可能であること"


def test_rainbow_curtain_all_element_armors_available():
    """
    検証内容: 虹のカーテンを1枚目に出した後は、攻撃属性が無属性化されるため、
    手札の火・水・木・土・光・無属性の全防具が合法手として正しく選択できることを網羅検証。
    """
    runner = SimulationRunner()

    fire_miracle_id = find_card_by_name("miracles/flame") # 火属性攻撃
    rainbow_curtain_id = find_card_by_name("armor/rainbow-curtain") # 虹のカーテン
    sparkle_glove_id = find_card_by_name("armor/sparkle-glove") # 火属性
    aqua_shoes_id = find_card_by_name("armor/aqua-shoes") # 水属性
    wood_shield_id = find_card_by_name("armor/wood-shield") # 木属性
    bedrock_id = find_card_by_name("armor/bedrock") # 土属性
    leather_cap_id = find_card_by_name("armor/leather-cap") # 無属性

    runner.set_status(0, hp=40, mp=20)
    runner.set_status(1, hp=40, mp=20)

    runner.state.set_true_hand(0, 0, fire_miracle_id)
    runner.state.set_true_hand(1, 0, rainbow_curtain_id)
    runner.state.set_true_hand(1, 1, sparkle_glove_id)
    runner.state.set_true_hand(1, 2, aqua_shoes_id)
    runner.state.set_true_hand(1, 3, wood_shield_id)
    runner.state.set_true_hand(1, 4, bedrock_id)
    runner.state.set_true_hand(1, 5, leather_cap_id)

    # 奇跡攻撃
    runner.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
    runner.step(godfield_core.ActionType.ACTION_TARGET_OPP)

    # 1枚目に虹のカーテンを仮置き
    runner.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)

    actions = godfield_core.get_legal_actions(runner.state)

    # 2枚目として全属性の防具が合法手になっていることを確認
    assert actions[godfield_core.ActionType.ACTION_SELECT_HAND_1] is True, "火属性防具が選択可能"
    assert actions[godfield_core.ActionType.ACTION_SELECT_HAND_2] is True, "水属性防具特防具が選択可能"
    assert actions[godfield_core.ActionType.ACTION_SELECT_HAND_3] is True, "木属性防具が選択可能"
    assert actions[godfield_core.ActionType.ACTION_SELECT_HAND_4] is True, "土属性防具が選択可能"
    assert actions[godfield_core.ActionType.ACTION_SELECT_HAND_5] is True, "無属性防具が選択可能"


def test_rainbow_curtain_plus_sky_armor_against_meteor():
    """
    検証内容: 相手から＜流星＞(光属性奇跡 ATK 10) を撃たれ、
    防御側が1枚目に「虹のカーテン」を出した後、2枚目としてリアクション防具である「スカイアーマー」(Def 9)
    が正しく合法手として選択でき、防御力9が計算に加算されることをテスト。
    """
    runner = SimulationRunner()

    meteor_id = find_card_by_name("miracles/meteor") # ＜流星＞ (光属性奇跡 ATK 10)
    rainbow_curtain_id = find_card_by_name("armor/rainbow-curtain") # 虹のカーテン
    sky_armor_id = find_card_by_name("armor/sky-armor") # ススカイアーマー (reaction: bounce, def: 9)

    runner.set_status(0, hp=40, mp=20)
    runner.set_status(1, hp=40, mp=20)

    runner.state.set_true_hand(0, 0, meteor_id)
    runner.state.set_true_hand(1, 0, rainbow_curtain_id)
    runner.state.set_true_hand(1, 1, sky_armor_id)

    # P0が＜流星＞でP1に光属性奇跡攻撃
    runner.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
    runner.step(godfield_core.ActionType.ACTION_TARGET_OPP)

    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_MIRACLE_DEFENSE

    # P1が1枚目に「虹のカーテン」(スロット0)を選択・仮置き
    runner.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)

    # 虹のカーテン仮置き後、手札スロット1の「スカイアーマー」が合法手になっていることをアサート！
    actions = godfield_core.get_legal_actions(runner.state)
    assert actions[godfield_core.ActionType.ACTION_SELECT_HAND_1] is True, "虹のカーテンの後にスカイアーマーが選択可能であること"

    # P1がスカイアーマー(スロット1)を選択して確定
    runner.step(godfield_core.ActionType.ACTION_SELECT_HAND_1)
    runner.step(godfield_core.ActionType.ACTION_CONFIRM)

    # ＜流星＞(ATK 10) に対して スカイアーマー(Def 9) で防御したため、ダメージは 10 - 9 = 1 ダメージ
    # P1のHPは 40 - 1 = 39 になること！
    assert runner.state.get_hp(1) == 39
