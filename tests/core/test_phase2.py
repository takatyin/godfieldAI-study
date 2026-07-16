import godfield_core
from godfield_core import ActionType

from .test_utils import SimulationRunner, find_card_by_name, get_all_cards


def test_physical_attack_opp():
    """
    検証内容: 無属性（物理）通常攻撃と、それに対する防具を使用した通常防御フローのテスト。
    - P0が「パンチ (攻撃力3)」を選択し、相手 (P1) を対象に攻撃を実行すること。
    - 攻撃実行後、ゲーム状態が防御フェーズ (PHASE_DEFENSE) に移行し、被攻撃者 (P1) に攻守交代すること。
    - P1が「革の服 (防御力2)」を選択して防御を確定させること。
    - ダメージ計算が行われ、ターンがP1のメインフェーズに移行すること。
    """
    runner = SimulationRunner()

    weapon_id = find_card_by_name("パンチ")  # 攻撃力 3
    shield_id = find_card_by_name("革の服")  # 防御力 2

    runner.state.set_true_hand(player_id=0, hand_idx=0, card_id=weapon_id)
    runner.state.set_true_hand(player_id=1, hand_idx=0, card_id=shield_id)
    runner.set_status(player=1, hp=40)

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0

    # --- PHASE_MAIN (P0) ---
    assert runner.state.current_actor_id == 0
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_MAIN

    runner.step(action=ActionType.ACTION_SELECT_HAND_0)
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_ATTACK_PLUS
    assert runner.state.attacker_id == 0

    runner.step(action=ActionType.ACTION_TARGET_OPP)
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
    assert runner.state.defender_id == 1
    assert runner.state.current_actor_id == 1
    assert runner.state.pending_attack_power == 3

    # --- PHASE_DEFENSE (P1) ---
    runner.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner.step(action=ActionType.ACTION_CONFIRM)

    # ターンが移行し、P1のメインフェイズになっているはず
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_MAIN
    assert runner.state.current_actor_id == 1
    assert runner.state.get_hp(player_id=1) == 40 - (3 - 2)


def test_attack_self():
    """
    検証内容: 自分に対する攻撃（自傷攻撃）と、それに対する無防御選択フローのテスト。
    - プレイヤーが武器を選択し、自分を対象に攻撃を実行できることを確認。
    - 防御選択フェーズがなしに、相手にターンが移行することを確認。
    """
    runner = SimulationRunner()
    weapon_id = find_card_by_name("パンチ")
    runner.state.set_true_hand(0, 0, weapon_id)
    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0

    runner.step(action=ActionType.ACTION_SELECT_HAND_0)
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_ATTACK_PLUS
    assert runner.state.get_hp(0) == 40

    runner.step(action=ActionType.ACTION_TARGET_SELF)

    assert runner.state.get_hp(0) < 40
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_MAIN
    assert runner.state.current_actor_id == 1


def test_attack_plus_combination():
    """
    検証内容: ATTACK_PLUSフェーズにおける、複数のプラス属性・無属性武器の組み合わせによるダメージ蓄積テスト。
    - P0がメイン武器（通常の攻撃カード）を選択してプレイ。
    - PHASE_ATTACK_PLUSに移行後、さらに手札から複数の「プラス攻撃（+付き）」カードを追加でプレイ。
    - 最終的に相手を対象にして攻撃を実行した際、攻撃力（pending_attack_power）が
      「メイン武器の攻撃力 + 追加したプラス武器の攻撃力の合計」と一致していることを確認する。
    """
    runner = SimulationRunner()

    main_weapon_name = "パンチ"  # ATK3
    plus_weapon_name_1 = "ブーメラン"  # +ATK3
    plus_weapon_name_2 = "バトルボール"  # +ATK4

    main_weapon_id = find_card_by_name(main_weapon_name)
    plus_weapon_id_1 = find_card_by_name(plus_weapon_name_1)
    plus_weapon_id_2 = find_card_by_name(plus_weapon_name_2)

    # P0の手札にセット
    runner.set_hand(0, [main_weapon_id, plus_weapon_id_1, plus_weapon_id_2])

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0

    # 1. メイン武器を選択
    runner.step(action=ActionType.ACTION_SELECT_HAND_0)
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_ATTACK_PLUS

    # 2. プラス武器1枚目を追加選択
    # 合法手であるか確認
    legal_actions = godfield_core.get_legal_actions(runner.state)
    assert legal_actions[ActionType.ACTION_SELECT_HAND_1]
    assert legal_actions[ActionType.ACTION_SELECT_HAND_2]
    runner.step(action=ActionType.ACTION_SELECT_HAND_1)
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_ATTACK_PLUS

    # 3. プラス武器2枚目を追加選択
    runner.step(action=ActionType.ACTION_SELECT_HAND_2)
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_ATTACK_PLUS

    # 4. 相手を対象に攻撃を確定
    legal_actions = godfield_core.get_legal_actions(runner.state)
    assert legal_actions[ActionType.ACTION_TARGET_OPP]
    runner.step(action=ActionType.ACTION_TARGET_OPP)

    # 5. 合計攻撃力の検証
    cards_data = {c["id"]: c for c in get_all_cards()}
    expected_power = (
        cards_data[main_weapon_id].get("attack_power", 0)
        + cards_data[plus_weapon_id_1].get("attack_power", 0)
        + cards_data[plus_weapon_id_2].get("attack_power", 0)
    )

    assert runner.state.pending_attack_power == expected_power
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
    assert runner.state.defender_id == 1
