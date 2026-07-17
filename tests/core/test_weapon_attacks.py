import godfield_core
from godfield_core import ActionType, GamePhase
from tests.core.test_utils import SimulationRunner, find_card_by_name, get_all_cards


def test_physical_attack_phase_transition():
    """
    検証内容: 無属性（物理）通常攻撃選択時のフェイズ遷移テスト。
    - 攻撃者がメインフェイズにおいて「パンチ」を選択すると、フェイズが PHASE_ATTACK_PLUS に遷移することを確認します。
    - 相手を対象（TARGET_OPP）に決定すると、防御側の防御フェイズ（PHASE_DEFENSE）に遷移することを確認します。
    """
    runner = SimulationRunner()
    weapon_id = find_card_by_name("パンチ")

    runner.state.set_true_hand(0, 0, weapon_id)
    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0

    # パンチを選択
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_ATTACK_PLUS
    assert runner.state.attacker_id == 0

    # 相手を対象に確定
    runner.step(ActionType.ACTION_TARGET_OPP)
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
    assert runner.state.defender_id == 1
    assert runner.state.current_actor_id == 1


def test_physical_attack_pending_atk_power():
    """
    検証内容: 武器選択時の保留攻撃力（pending_attack_power）の設定テスト。
    - 攻撃者が「パンチ (攻撃力3)」を選択し、相手をターゲットした時点で、保留攻撃力が正確に 3 に設定されることを確認します。
    """
    runner = SimulationRunner()
    weapon_id = find_card_by_name("パンチ")

    runner.state.set_true_hand(0, 0, weapon_id)
    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0

    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_TARGET_OPP)

    # 保留攻撃力が 3 であること
    assert runner.state.pending_attack_power == 3


def test_physical_defense_resolves_damage_and_turns():
    """
    検証内容: 防具を使用した防御解決におけるダメージ量とターン終了テスト。
    - 攻撃力 3 の攻撃に対し、防御側が「革の服 (防御力2)」を使用して防御を確定した際、受けるダメージが 3 - 2 = 1 となり、HPが 40 から 39 に減少することを確認します。
    - 防御解決後、手番（current_actor_id）が相手（プレイヤー1）のメインフェイズに正常に移行することを確認します。
    """
    runner = SimulationRunner()
    weapon_id = find_card_by_name("パンチ")
    shield_id = find_card_by_name("革の服")

    runner.state.set_true_hand(0, 0, weapon_id)
    runner.state.set_true_hand(1, 0, shield_id)
    runner.set_status(1, hp=40)

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0

    # 攻撃確定
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_TARGET_OPP)

    # 防御確定
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_CONFIRM)

    # HPが減少していること (40 - 1 = 39)
    assert runner.state.get_hp(1) == 39
    # 手番が防御側(1)のメインフェイズになっていること
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_MAIN
    assert runner.state.current_actor_id == 1


def test_physical_self_attack_resolves_instantly():
    """
    検証内容: 自傷物理攻撃時の即時解決とアクター遷移テスト。
    - プレイヤーが自分を対象（TARGET_SELF）に物理攻撃を実行した際、防御フェイズを経由せず即座にHPが減少することを確認します。
    - 自傷解決後、ターンが自動的に終了し、相手（プレイヤー1）のメインフェイズに手番が移行することを確認します。
    """
    runner = SimulationRunner()
    weapon_id = find_card_by_name("パンチ")

    runner.state.set_true_hand(0, 0, weapon_id)
    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.set_status(0, hp=40)

    # 自分を選択して攻撃
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_TARGET_SELF)

    # 防御を挟まず即座にダメージ適用（パンチのATKは3）
    assert runner.state.get_hp(0) < 40
    # 手番が相手(1)のメインフェイズに遷移していること
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_MAIN
    assert runner.state.current_actor_id == 1


def test_attack_plus_combination_addition():
    """
    検証内容: 複数プラス武器の重ねがけによる攻撃力合計テスト。
    - 通常武器（パンチ）をメインに選択した後、プラス武器（ブーメラン: +3、バトルボール: +4）を追加で重ねた場合、保留攻撃力がそれぞれの合計値（3 + 3 + 4 = 10）になることを確認します。
    """
    runner = SimulationRunner()
    main_weapon_id = find_card_by_name("パンチ")       # ATK 3
    plus_weapon_id_1 = find_card_by_name("ブーメラン")  # +ATK 3
    plus_weapon_id_2 = find_card_by_name("バトルボール") # +ATK 4

    runner.set_hand(0, [main_weapon_id, plus_weapon_id_1, plus_weapon_id_2])
    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0

    # 1. メイン武器を選択
    runner.step(ActionType.ACTION_SELECT_HAND_0)

    # 2. プラス武器1枚目を追加選択
    runner.step(ActionType.ACTION_SELECT_HAND_1)

    # 3. プラス武器2枚目を追加選択
    runner.step(ActionType.ACTION_SELECT_HAND_2)

    # 4. 相手を対象に攻撃を確定
    runner.step(ActionType.ACTION_TARGET_OPP)

    # 合計攻撃力の検証
    cards_data = {c["id"]: c for c in get_all_cards()}
    expected_power = (
        cards_data[main_weapon_id].get("attack_power", 0)
        + cards_data[plus_weapon_id_1].get("attack_power", 0)
        + cards_data[plus_weapon_id_2].get("attack_power", 0)
    )

    assert runner.state.pending_attack_power == expected_power
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE


def test_attack_plus_combination_non_plus_masked():
    """
    検証内容: 重ねがけフェイズにおける非プラス武器の選択制限テスト。
    - PHASE_ATTACK_PLUS において、手札にある別の非プラス武器（「パンチ」など）は追加選択できない（非合法手となる）ことを確認します。
    """
    runner = SimulationRunner()
    main_weapon_id = find_card_by_name("パンチ")
    other_non_plus_weapon_id = find_card_by_name("銅のこん棒")  # 非プラス武器

    runner.set_hand(0, [main_weapon_id, other_non_plus_weapon_id])
    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0

    # メイン武器を選択
    runner.step(ActionType.ACTION_SELECT_HAND_0)

    # 重ねがけフェイズにおいて、非プラス武器であるスロット1は選択できないことを確認
    legal_actions = godfield_core.get_legal_actions(runner.state)
    assert legal_actions[ActionType.ACTION_SELECT_HAND_1] is False


def test_weapon_and_multiple_miracles_with_dolls_stacking():
    """
    検証内容: 単体武器 ＋ 火の玉 ＋ ぬいぐるみ ＋ 火の玉 ＋ ぬいぐるみ の合法手およびMP消費相殺の検証。
    - メインに物理武器「パンチ」を使用し、そこに奇跡「＜火の玉＞」を追加。
    - 「精霊のぬいぐるみ」でMPを相殺し、さらに2枚目の「＜火の玉＞」を追加。
    - この4枚（武器 ＋ 火の玉 ＋ ぬいぐるみ ＋ 火の玉）の状態で攻撃を確定すると、最後の火の玉の消費MP 2がそのまま消費され（合計MP 2消費）、MP 8になることを確認します。
    - 5枚（武器 ＋ 火の玉 ＋ ぬいぐるみ ＋ 火の玉 ＋ ぬいぐるみ）の状態で確定すると、すべてのMP消費が相殺され（合計MP 0消費）、MP 10のままであることを確認します。
    """
    # 1. 4枚構成でのMP消費テスト（MP 2消費）
    runner_4 = SimulationRunner()
    punch_id = find_card_by_name("パンチ")
    fireball_id = find_card_by_name("＜火の玉＞")
    doll_id = find_card_by_name("精霊のぬいぐるみ")

    runner_4.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner_4.state.current_actor_id = 0
    runner_4.state.set_mp(0, 10)
    runner_4.state.set_true_hand(0, 0, punch_id)
    runner_4.state.set_true_hand(0, 1, fireball_id)
    runner_4.state.set_true_hand(0, 2, doll_id)
    runner_4.state.set_true_hand(0, 3, fireball_id)

    # 重ねがけ
    runner_4.step(ActionType.ACTION_SELECT_HAND_0)  # パンチ
    runner_4.step(ActionType.ACTION_SELECT_HAND_1)  # 火の玉
    runner_4.step(ActionType.ACTION_SELECT_HAND_2)  # ぬいぐるみ
    runner_4.step(ActionType.ACTION_SELECT_HAND_3)  # 火の玉（2枚目）

    # 相手をターゲットにして攻撃確定
    runner_4.step(ActionType.ACTION_TARGET_OPP)

    # 最後の火の玉の分のMP 2が消費されて、MP 8になっていること
    assert runner_4.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
    assert runner_4.state.get_mp(0) == 8

    # 2. 5枚構成でのMP消費テスト（MP 0消費）
    runner_5 = SimulationRunner()
    runner_5.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner_5.state.current_actor_id = 0
    runner_5.state.set_mp(0, 10)
    runner_5.state.set_true_hand(0, 0, punch_id)
    runner_5.state.set_true_hand(0, 1, fireball_id)
    runner_5.state.set_true_hand(0, 2, doll_id)
    runner_5.state.set_true_hand(0, 3, fireball_id)
    runner_5.state.set_true_hand(0, 4, doll_id)

    # 重ねがけ
    runner_5.step(ActionType.ACTION_SELECT_HAND_0)  # パンチ
    runner_5.step(ActionType.ACTION_SELECT_HAND_1)  # 火の玉
    runner_5.step(ActionType.ACTION_SELECT_HAND_2)  # ぬいぐるみ
    runner_5.step(ActionType.ACTION_SELECT_HAND_3)  # 火の玉（2枚目）
    runner_5.step(ActionType.ACTION_SELECT_HAND_4)  # ぬいぐるみ（2枚目）

    # 相手をターゲットにして攻撃確定
    runner_5.step(ActionType.ACTION_TARGET_OPP)

    # MP 0消費で、MP 10が維持されていること
    assert runner_5.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
    assert runner_5.state.get_mp(0) == 10
