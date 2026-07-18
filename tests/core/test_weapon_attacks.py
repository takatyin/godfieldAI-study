import godfield_core
from godfield_core import ActionType
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
    main_weapon_id = find_card_by_name("パンチ")  # ATK 3
    plus_weapon_id_1 = find_card_by_name("ブーメラン")  # +ATK 3
    plus_weapon_id_2 = find_card_by_name("バトルボール")  # +ATK 4

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


def test_ghost_swords_absorption():
    """
    検証内容: ゴーストソードおよびリアルゴーストソードのHP吸収テスト。
    - ゴーストソード(ATK 7)で無防備の相手を攻撃した際、与えたダメージ7と同じ分だけ攻撃側のHPが回復(吸収)することを確認します。
    - リアルゴーストソード(ATK 12)で無防備の相手を攻撃した際、与えたダメージ12と同じ分だけ攻撃側のHPが回復することを確認します。
    """
    # 1. ゴーストソードの検証
    runner = SimulationRunner()
    ghost_sword_id = find_card_by_name("ゴーストソード")

    runner.set_status(0, hp=40, mp=0)
    runner.set_status(1, hp=40, mp=0)
    runner.state.set_true_hand(0, 0, ghost_sword_id)

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0

    # 攻撃
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_TARGET_OPP)

    # 防御側(1)は何もしないで確定
    runner.step(ActionType.ACTION_CONFIRM)

    # ダメージ適用とHP吸収の検証
    assert runner.state.get_hp(1) == 33  # 40 - 7
    assert runner.state.get_hp(0) == 47  # 40 + 7

    # 2. リアルゴーストソードの検証
    runner_real = SimulationRunner()
    real_ghost_sword_id = find_card_by_name("リアルゴーストソード")

    runner_real.set_status(0, hp=40, mp=0)
    runner_real.set_status(1, hp=40, mp=0)
    runner_real.state.set_true_hand(0, 0, real_ghost_sword_id)

    runner_real.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner_real.state.current_actor_id = 0

    # 攻撃
    runner_real.step(ActionType.ACTION_SELECT_HAND_0)
    runner_real.step(ActionType.ACTION_TARGET_OPP)

    # 防御側(1)は何もしないで確定
    runner_real.step(ActionType.ACTION_CONFIRM)

    # ダメージ適用とHP吸収の検証
    assert runner_real.state.get_hp(1) == 28  # 40 - 12
    assert runner_real.state.get_hp(0) == 52  # 40 + 12


def test_evil_broadsword_damage_flow():
    """
    検証内容: 邪神の大剣(ATK 14)の自傷ダメージ・反射ダメージテスト。
    - 相手を攻撃した場合: 与えたダメージ14と同等の自傷ダメージを攻撃者が受けることを確認。
    - 自分を対象に攻撃した場合: 自傷ダメージが二重に乗り、2倍のダメージ(28)を受けることを確認。
    - 弾き(Bounce)失敗時: 弾こうとした側が自傷ダメージを含めて2倍のダメージ(28)を受けることを確認。
    """
    # 1. 相手を攻撃した時の自傷
    runner = SimulationRunner()
    evil_id = find_card_by_name("邪神の大剣")

    runner.set_status(0, hp=40, mp=0)
    runner.set_status(1, hp=40, mp=0)
    runner.state.set_true_hand(0, 0, evil_id)

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0

    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_TARGET_OPP)
    runner.step(ActionType.ACTION_CONFIRM)  # 防御側は確定

    assert runner.state.get_hp(1) == 26  # 40 - 14
    assert runner.state.get_hp(0) == 26  # 40 - 14 (自傷)

    # 2. 自分をターゲットにした時の2倍自傷
    runner_self = SimulationRunner()
    runner_self.set_status(0, hp=40, mp=0)
    runner_self.state.set_true_hand(0, 0, evil_id)

    runner_self.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner_self.state.current_actor_id = 0

    runner_self.step(ActionType.ACTION_SELECT_HAND_0)
    runner_self.step(ActionType.ACTION_TARGET_SELF)  # 自分を攻撃して即時解決

    assert runner_self.state.get_hp(0) == 12  # 40 - 14 - 14 (2倍)

    # 3. 弾き失敗時の2倍被弾 (相手が弾こうとして失敗した場合)
    runner_bounce = SimulationRunner()
    bounce_weapon_id = find_card_by_name("乱弾武剣")  # 物理の弾く武器

    runner_bounce.set_status(0, hp=40, mp=0)
    runner_bounce.set_status(1, hp=40, mp=0)

    # 乱数シードを固定して、弾き失敗（Bounce success確率50%）をテストしたい。
    # シード0で検証。
    runner_bounce.state.seed_rng(0)  # シード0で失敗するように固定
    runner_bounce.state.set_true_hand(0, 0, evil_id)
    runner_bounce.state.set_true_hand(1, 0, bounce_weapon_id)

    runner_bounce.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner_bounce.state.current_actor_id = 0

    runner_bounce.step(ActionType.ACTION_SELECT_HAND_0)  # プレイヤー0が邪神の大剣を使用
    runner_bounce.step(ActionType.ACTION_TARGET_OPP)

    # プレイヤー1は乱弾武剣で防御
    runner_bounce.step(ActionType.ACTION_SELECT_HAND_0)
    runner_bounce.step(ActionType.ACTION_CONFIRM)

    # 弾きが失敗した場合、防御側であるプレイヤー1に攻撃が当たり、かつ自傷で2倍ダメージを受ける。
    # プレイヤー1のHPが12 (40 - 28) になっていること、プレイヤー0のHPは40のままであることを確認。
    assert runner_bounce.state.get_hp(1) == 12
    assert runner_bounce.state.get_hp(0) == 40


def test_wands_element_resolution():
    """
    検証内容: 発火のワンド、魔水のワンドによる属性上書きおよび順序依存の解決テスト。
    - パンチ(無) -> ファイヤークロスボウ(火) -> 魔水のワンド(水) ＝ 水属性
    - 聖剣(光) -> ファイヤークロスボウ(火) -> 魔水のワンド(水) ＝ 水属性
    - 聖剣(光) -> ファイヤークロスボウ(火) -> 魔水のワンド(水) -> ファイヤークロスボウ(火) ＝ 無属性
    - 聖剣(光) -> ファイヤークロスボウ(火) -> 魔水のワンド(水) -> 輝きのカケラ(光) ＝ 水属性
    - 魔水のワンド(水) -> 戦士の弓(無) ＝ 無属性
    """
    punch_id = find_card_by_name("パンチ")
    holy_sword_id = find_card_by_name("聖剣")
    fire_crossbow_id = find_card_by_name("ファイヤークロスボウ")
    piece_of_brightness_id = find_card_by_name("輝きのカケラ")
    warrior_bow_id = find_card_by_name("戦士の弓")
    mystic_water_wand_id = find_card_by_name("魔水のワンド")

    # 1. パンチ -> ファイヤークロスボウ -> 魔水のワンド = 水属性
    runner_1 = SimulationRunner()
    runner_1.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner_1.state.current_actor_id = 0
    runner_1.state.set_true_hand(0, 0, punch_id)
    runner_1.state.set_true_hand(0, 1, fire_crossbow_id)
    runner_1.state.set_true_hand(0, 2, mystic_water_wand_id)

    runner_1.step(ActionType.ACTION_SELECT_HAND_0)  # パンチ
    runner_1.step(ActionType.ACTION_SELECT_HAND_1)  # ファイヤークロスボウ
    runner_1.step(ActionType.ACTION_SELECT_HAND_2)  # 魔水のワンド
    runner_1.step(ActionType.ACTION_TARGET_OPP)
    assert runner_1.state.pending_attack_element == godfield_core.Element.ELEM_WATER

    # 2. 聖剣 -> ファイヤークロスボウ -> 魔水のワンド = 水属性
    runner_2 = SimulationRunner()
    runner_2.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner_2.state.current_actor_id = 0
    runner_2.state.set_true_hand(0, 0, holy_sword_id)
    runner_2.state.set_true_hand(0, 1, fire_crossbow_id)
    runner_2.state.set_true_hand(0, 2, mystic_water_wand_id)

    runner_2.step(ActionType.ACTION_SELECT_HAND_0)  # 聖剣
    runner_2.step(ActionType.ACTION_SELECT_HAND_1)  # ファイヤークロスボウ
    runner_2.step(ActionType.ACTION_SELECT_HAND_2)  # 魔水のワンド
    runner_2.step(ActionType.ACTION_TARGET_OPP)
    assert runner_2.state.pending_attack_element == godfield_core.Element.ELEM_WATER

    # 3. 聖剣 -> ファイヤークロスボウ -> 魔水のワンド -> ファイヤークロスボウ = 無属性
    runner_3 = SimulationRunner()
    runner_3.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner_3.state.current_actor_id = 0
    runner_3.state.set_true_hand(0, 0, holy_sword_id)
    runner_3.state.set_true_hand(0, 1, fire_crossbow_id)
    runner_3.state.set_true_hand(0, 2, mystic_water_wand_id)
    runner_3.state.set_true_hand(0, 3, fire_crossbow_id)

    runner_3.step(ActionType.ACTION_SELECT_HAND_0)  # 聖剣
    runner_3.step(ActionType.ACTION_SELECT_HAND_1)  # ファイヤークロスボウ
    runner_3.step(ActionType.ACTION_SELECT_HAND_2)  # 魔水のワンド
    runner_3.step(ActionType.ACTION_SELECT_HAND_3)  # ファイヤークロスボウ (重ねる)
    runner_3.step(ActionType.ACTION_TARGET_OPP)
    assert runner_3.state.pending_attack_element == godfield_core.Element.ELEM_NONE

    # 4. 聖剣 -> ファイヤークロスボウ -> 魔水のワンド -> 輝きのカケラ = 水属性
    runner_4 = SimulationRunner()
    runner_4.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner_4.state.current_actor_id = 0
    runner_4.state.set_true_hand(0, 0, holy_sword_id)
    runner_4.state.set_true_hand(0, 1, fire_crossbow_id)
    runner_4.state.set_true_hand(0, 2, mystic_water_wand_id)
    runner_4.state.set_true_hand(0, 3, piece_of_brightness_id)

    runner_4.step(ActionType.ACTION_SELECT_HAND_0)  # 聖剣
    runner_4.step(ActionType.ACTION_SELECT_HAND_1)  # ファイヤークロスボウ
    runner_4.step(ActionType.ACTION_SELECT_HAND_2)  # 魔水のワンド
    runner_4.step(ActionType.ACTION_SELECT_HAND_3)  # 輝きのカケラ
    runner_4.step(ActionType.ACTION_TARGET_OPP)
    assert runner_4.state.pending_attack_element == godfield_core.Element.ELEM_WATER

    # 5. 魔水のワンド -> 戦士の弓 = 無属性
    runner_5 = SimulationRunner()
    runner_5.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner_5.state.current_actor_id = 0
    runner_5.state.set_true_hand(0, 0, mystic_water_wand_id)
    runner_5.state.set_true_hand(0, 1, warrior_bow_id)

    runner_5.step(ActionType.ACTION_SELECT_HAND_0)  # 魔水のワンド
    runner_5.step(ActionType.ACTION_SELECT_HAND_1)  # 戦士の弓
    runner_5.step(ActionType.ACTION_TARGET_OPP)
    assert runner_5.state.pending_attack_element == godfield_core.Element.ELEM_NONE


def test_magical_stick_damage_flow():
    """
    検証内容: マジカルステッキのMP全消費および残MPベースの攻撃力計算テスト。
    1. マジカルステッキ単体 (所持MP 10) -> ATK 20, 消費 10
    2. マジカルステッキ ＋ 流星 (所持MP 10, 流星消費 7) -> ATK (3 * 2) + 10 = 16, 消費 10
    3. マジカルステッキ ＋ 流星 ＋ 精霊 (所持MP 10, 精霊効果で流星消費 0)
       - 手札に精霊がある段階で流星が合法手（can_afford = True）であることを検証
       - 重ねた後の ATK = 30, 消費 10
    4. MP不足時の重ねがけ不可 (所持MP 5, 流星消費 7) -> can_afford = False
    5. MP 0 での使用 (所持MP 0) -> ATK 0, 消費 0 で使用可能
    """
    magical_stick_id = find_card_by_name("weapons/magical-stick")
    meteor_id = find_card_by_name("miracles/meteor")
    doll_id = find_card_by_name("sundries/spiritual-doll")
    punch_id = find_card_by_name("weapons/punch")

    # 1. マジカルステッキ単体 (所持MP 10)
    runner_1 = SimulationRunner()
    runner_1.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner_1.state.current_actor_id = 0
    runner_1.state.set_mp(0, 10)
    runner_1.state.set_true_hand(0, 0, magical_stick_id)

    runner_1.step(ActionType.ACTION_SELECT_HAND_0)  # マジカルステッキを選択
    assert runner_1.state.current_phase == godfield_core.GamePhase.PHASE_ATTACK_PLUS

    runner_1.step(ActionType.ACTION_TARGET_OPP)  # ターゲット選択して攻撃確定
    assert runner_1.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
    assert runner_1.state.pending_attack_power == 20
    assert runner_1.state.pending_attack_element == godfield_core.Element.ELEM_NONE

    # 攻撃解決後のMP減少を確認するため、相手が何も防御せずに食らう
    runner_1.step(ActionType.ACTION_CONFIRM)  # 相手防御パス
    assert runner_1.state.get_mp(0) == 0  # MPが0になっていること

    # 2. マジカルステッキ ＋ 流星 (所持MP 10, 流星消費 7)
    runner_2 = SimulationRunner()
    runner_2.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner_2.state.current_actor_id = 0
    runner_2.state.set_mp(0, 10)
    runner_2.state.set_true_hand(0, 0, magical_stick_id)
    runner_2.state.set_true_hand(0, 1, meteor_id)

    runner_2.step(ActionType.ACTION_SELECT_HAND_0)  # マジカルステッキ
    runner_2.step(ActionType.ACTION_SELECT_HAND_1)  # 流星を重ねる
    runner_2.step(ActionType.ACTION_TARGET_OPP)  # ターゲット選択して確定

    # 攻撃力: マジカルステッキ(10-7)*2=6 + 流星10 = 16
    assert runner_2.state.pending_attack_power == 16
    assert runner_2.state.pending_attack_element == godfield_core.Element.ELEM_LIGHT

    runner_2.step(ActionType.ACTION_CONFIRM)
    assert runner_2.state.get_mp(0) == 0

    # 3. マジカルステッキ ＋ 流星 ＋ 精霊 (所持MP 10, 精霊効果で流星消費 0)
    runner_3 = SimulationRunner()
    runner_3.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner_3.state.current_actor_id = 0
    runner_3.state.set_mp(0, 10)
    runner_3.state.set_true_hand(0, 0, magical_stick_id)
    runner_3.state.set_true_hand(0, 1, meteor_id)
    runner_3.state.set_true_hand(0, 2, doll_id)

    runner_3.step(ActionType.ACTION_SELECT_HAND_0)  # マジカルステッキ

    # まだ精霊のぬいぐるみを仮置きしていないが、手札にあるため流星を重ねがけできる (can_afford = True) を確認
    legal_actions = godfield_core.get_legal_actions(runner_3.state)
    assert legal_actions[ActionType.ACTION_SELECT_HAND_1] == True  # 流星が選択可能であること

    runner_3.step(ActionType.ACTION_SELECT_HAND_1)  # 流星を置く
    runner_3.step(ActionType.ACTION_SELECT_HAND_2)  # 精霊を置く
    runner_3.step(ActionType.ACTION_TARGET_OPP)

    # 攻撃力: マジカルステッキ(10-0)*2=20 + 流星10 = 30
    assert runner_3.state.pending_attack_power == 30
    assert runner_3.state.pending_attack_element == godfield_core.Element.ELEM_LIGHT

    runner_3.step(ActionType.ACTION_CONFIRM)
    assert runner_3.state.get_mp(0) == 0

    # 4. MP不足時の重ねがけ不可 (所持MP 5, 流星消費 7)
    runner_4 = SimulationRunner()
    runner_4.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner_4.state.current_actor_id = 0
    runner_4.state.set_mp(0, 5)
    runner_4.state.set_true_hand(0, 0, magical_stick_id)
    runner_4.state.set_true_hand(0, 1, meteor_id)

    runner_4.step(ActionType.ACTION_SELECT_HAND_0)  # マジカルステッキ

    # 手札に精霊がないため、流星を重ねがけできない (can_afford = False) を確認
    legal_actions_4 = godfield_core.get_legal_actions(runner_4.state)
    assert legal_actions_4[ActionType.ACTION_SELECT_HAND_1] == False  # 流星が選択不可であること

    # 5. MP 0 での使用 (所持MP 0)
    runner_5 = SimulationRunner()
    runner_5.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner_5.state.current_actor_id = 0
    runner_5.state.set_mp(0, 0)
    runner_5.state.set_true_hand(0, 0, magical_stick_id)

    runner_5.step(ActionType.ACTION_SELECT_HAND_0)  # マジカルステッキ
    runner_5.step(ActionType.ACTION_TARGET_OPP)

    # 攻撃力: (0-0)*2 = 0
    assert runner_5.state.pending_attack_power == 0
    runner_5.step(ActionType.ACTION_CONFIRM)
    assert runner_5.state.get_mp(0) == 0


def test_dangerous_pestle_and_mortar():
    """
    検証内容: あぶないキネとあぶないウスのランダム対象・比率解決・被弾側のみ1枚消費・太陽のお守り連動。
    1. ウスが存在しない場合 (T = 0) の 50:50 ランダム解決:
       - 100回試行して、自傷 (get_hp(0)=10, またはミス) と 相手への攻撃 (PHASE_DEFENSE) が約50%ずつ発生することを確認。
    2. ウスが存在する場合 (T > 0) の比率解決と被弾側の1枚消費:
       - プレイヤー0がウス3枚、プレイヤー1がウス2枚所持。
       - 100回試行して、約60%でプレイヤー0が被弾、約40%でプレイヤー1が被弾することを確認。
       - 被弾側のウスが「1枚だけ」消費され、被弾しなかった側のウスは消費されないことを確認。
    3. ウス2枚＋太陽のお守りでの復活と2回目のキネでの死亡（ユーザー様指定シナリオ）:
       - プレイヤー0がキネを使用。
       - プレイヤー1がキネ, ウス2枚, 太陽のお守りを所持。
       - 1回目のキネで、B(プレイヤー1)が100%の確率で99被弾。HPは40 -> 0 -> 10(お守りで復活)に。
       - Bの手札のウスが1枚だけ消費され残り1枚になることを確認。
       - 次にBのターンになり、Bがキネを撃つと、残った1枚のウスで自分に99被弾し、今度はお守りがないので死亡（HP0）することを検証。
    """
    pestle_id = find_card_by_name("weapons/dangerous-pestle")
    mortar_id = find_card_by_name("sundries/dangerous-mortar")
    sun_amulet_id = find_card_by_name("sundries/sun-amulet")
    super_mirror_id = find_card_by_name("armor/super-mirror")

    # 1. ウスが存在しない場合の 50:50 ランダム解決
    self_damage_count = 0
    opp_attack_count = 0
    trials = 100
    for idx in range(trials):
        runner = SimulationRunner()
        runner.state.seed_rng(idx)
        runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
        runner.state.current_actor_id = 0
        runner.set_status(0, hp=40)
        runner.set_status(1, hp=40)
        runner.state.set_true_hand(0, 0, pestle_id)
        runner.state.set_true_hand(1, 0, super_mirror_id)

        runner.step(ActionType.ACTION_SELECT_HAND_0)
        runner.step(ActionType.ACTION_TARGET_OPP)

        if runner.state.current_phase == godfield_core.GamePhase.PHASE_MAIN:
            # PHASE_MAIN になった場合: 自傷ダメージ解決後、またはミスの場合
            if runner.state.get_hp(0) == 10:
                self_damage_count += 1
                assert runner.state.get_hp(1) == 40
            else:
                assert runner.state.get_hp(0) == 40
                assert runner.state.get_hp(1) == 40
        else:
            opp_attack_count += 1
            # 相手への攻撃の場合、防御フェイズに移行
            assert runner.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
            assert runner.state.pending_attack_power == 30
            assert runner.state.pending_attack_element == godfield_core.Element.ELEM_LIGHT

    # 50% 確率の統計的検証 (100回試行中、30〜70回の範囲内に入ることを期待)
    assert 30 <= self_damage_count <= 70

    # 2. ウスが存在する場合 (T > 0) の比率解決と被弾側の1枚消費
    p0_hit = 0
    p1_hit = 0
    for idx in range(trials):
        runner = SimulationRunner()
        runner.state.seed_rng(idx)
        runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
        runner.state.current_actor_id = 0
        runner.set_status(0, hp=100)
        runner.set_status(1, hp=100)
        # プレイヤー0がキネ + ウス3枚
        runner.state.set_true_hand(0, 0, pestle_id)
        runner.state.set_true_hand(0, 1, mortar_id)
        runner.state.set_true_hand(0, 2, mortar_id)
        runner.state.set_true_hand(0, 3, mortar_id)
        # プレイヤー1がウス2枚
        runner.state.set_true_hand(1, 0, mortar_id)
        runner.state.set_true_hand(1, 1, mortar_id)

        runner.step(ActionType.ACTION_SELECT_HAND_0)
        runner.step(ActionType.ACTION_TARGET_OPP)

        # 防御フェイズを介さずに自動解決され PHASE_MAIN になる
        assert runner.state.current_phase == godfield_core.GamePhase.PHASE_MAIN

        if runner.state.get_hp(0) == 1:
            p0_hit += 1
            # プレイヤー0が被弾。0のウスが1枚消費され(残り2枚)、1のウスは消費されていない(残り2枚)
            count_0 = sum(
                1
                for j in range(18)
                if runner.state.get_true_hand(0, j) == mortar_id
                and not runner.state.get_is_used(0, j)
            )
            count_1 = sum(
                1
                for j in range(18)
                if runner.state.get_true_hand(1, j) == mortar_id
                and not runner.state.get_is_used(1, j)
            )
            assert count_0 == 2
            assert count_1 == 2
        else:
            p1_hit += 1
            # プレイヤー1が被弾。1のウスが1枚消費され(残り1枚)、0のウスは消費されていない(残り3枚)
            count_0 = sum(
                1
                for j in range(18)
                if runner.state.get_true_hand(0, j) == mortar_id
                and not runner.state.get_is_used(0, j)
            )
            count_1 = sum(
                1
                for j in range(18)
                if runner.state.get_true_hand(1, j) == mortar_id
                and not runner.state.get_is_used(1, j)
            )
            assert count_0 == 3
            assert count_1 == 1

    # 3/5 (60%) 確率の統計的検証 (100回試行中、プレイヤー0被弾が 45〜75回の範囲内に入ることを期待)
    assert 45 <= p0_hit <= 75

    # 3. 複数ウスと太陽のお守り（ユーザー様ご提示シナリオ）
    runner_scenario = SimulationRunner()
    runner_scenario.state.seed_rng(42)
    runner_scenario.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner_scenario.state.current_actor_id = 0
    runner_scenario.set_status(0, hp=40)
    runner_scenario.set_status(1, hp=40)

    # A (プレイヤー0): キネ
    runner_scenario.state.set_true_hand(0, 0, pestle_id)

    # B (プレイヤー1): キネ, ウス2枚, 太陽のお守り
    runner_scenario.state.set_true_hand(1, 0, pestle_id)
    runner_scenario.state.set_true_hand(1, 1, mortar_id)
    runner_scenario.state.set_true_hand(1, 2, mortar_id)
    runner_scenario.state.set_true_hand(1, 3, sun_amulet_id)

    # 1回目のキネ (AがBに向けて撃つ)
    runner_scenario.step(ActionType.ACTION_SELECT_HAND_0)
    runner_scenario.step(ActionType.ACTION_TARGET_OPP)

    # Bが100%被弾するが、お守りでHP10に復活していること
    assert runner_scenario.state.get_hp(1) == 10

    # Bのお守りは消費され、かつウスが「1枚だけ」消費されていること (残り1枚)
    count_1_after_1st = sum(
        1
        for j in range(18)
        if runner_scenario.state.get_true_hand(1, j) == mortar_id
        and not runner_scenario.state.get_is_used(1, j)
    )
    assert count_1_after_1st == 1

    # ターンエンドしてBのターンへ
    runner_scenario.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner_scenario.state.current_actor_id = 1

    # 2回目のキネ (Bが撃つ)
    # 現在Bの手札にはウスが1枚残っている
    runner_scenario.step(ActionType.ACTION_SELECT_HAND_0)  # Bがキネを選択
    runner_scenario.step(ActionType.ACTION_TARGET_OPP)

    # 残り1枚のウスで自分が99ダメージを食らい、お守りはもうないので死亡 (HP 0)
    assert runner_scenario.state.get_hp(1) == 0
    # Bの残りのウスも消費されたこと (残り0枚)
    count_1_after_2nd = sum(
        1
        for j in range(18)
        if runner_scenario.state.get_true_hand(1, j) == mortar_id
        and not runner_scenario.state.get_is_used(1, j)
    )
    assert count_1_after_2nd == 0


def test_fever_mask_and_dreaming_hat():
    """
    検証内容: 熱狂仮面による熱病付与、および夢見る帽子による夢付与＋手札一新。
    1. 熱狂仮面:
       - プレイヤー0がパンチ(攻撃力10)でプレイヤー1を攻撃。
       - プレイヤー1が熱狂仮面(防御力10)で防御。
       - 被ダメージは 10 - 10 = 0 になる。
       - プレイヤー1の sickness が SICKNESS_FEVER (2) になり、HPは40のまま。
    2. 夢見る帽子:
       - プレイヤー0がパンチ(攻撃力10)でプレイヤー1を攻撃。
       - プレイヤー1が夢見る帽子(防御力14)で防御。手札に他のカードを複数枚所持。
       - 被ダメージは 10 - 14 = 0 になる。
       - プレイヤー1の curses の夢フラグ (CURSE_DREAM = 3) が True になる。
       - プレイヤー1の元の手札がすべて消費され、山札から新しく引いたカードに一新されていることを確認。
    """
    fever_mask_id = find_card_by_name("armor/fever-mask")
    dreaming_hat_id = find_card_by_name("armor/dreaming-hat")
    punch_id = find_card_by_name("weapons/punch")

    # 1. 熱狂仮面のテスト
    runner_fever = SimulationRunner()
    runner_fever.state.seed_rng(42)
    runner_fever.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner_fever.state.current_actor_id = 0
    runner_fever.set_status(0, hp=40)
    runner_fever.set_status(1, hp=40)

    # プレイヤー0にパンチ、プレイヤー1に熱狂仮面を持たせる
    runner_fever.state.set_true_hand(0, 0, punch_id)
    runner_fever.state.set_true_hand(1, 0, fever_mask_id)

    # 攻撃アクション
    runner_fever.step(ActionType.ACTION_SELECT_HAND_0)
    runner_fever.step(ActionType.ACTION_TARGET_OPP)

    # 防御フェイズ
    assert runner_fever.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
    assert runner_fever.state.current_actor_id == 1

    # 防御選択 -> 確定
    runner_fever.step(ActionType.ACTION_SELECT_HAND_0)
    runner_fever.step(ActionType.ACTION_CONFIRM)

    # ダメージ解決され、ターン終了処理を経て PHASE_MAIN に戻る
    assert runner_fever.state.current_phase == godfield_core.GamePhase.PHASE_MAIN
    # 被ダメージは 0 だが、熱病にかかったためターン終了時に2ダメージ受けて HP は 38 になる
    assert runner_fever.state.get_hp(1) == 38
    # 熱病状態になっていること (SicknessType.SICKNESS_FEVER = 2)
    assert runner_fever.state.get_sickness(1) == godfield_core.SicknessType.SICKNESS_FEVER

    # 2. 夢見る帽子のテスト
    runner_dream = SimulationRunner()
    runner_dream.state.seed_rng(42)
    runner_dream.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner_dream.state.current_actor_id = 0
    runner_dream.set_status(0, hp=40)
    runner_dream.set_status(1, hp=40)

    # プレイヤー0にパンチ
    runner_dream.state.set_true_hand(0, 0, punch_id)
    # プレイヤー1に夢見る帽子 + 他のダミーカード3枚を持たせる
    dummy_card_id = find_card_by_name("weapons/punch")
    runner_dream.state.set_true_hand(1, 0, dreaming_hat_id)
    runner_dream.state.set_true_hand(1, 1, dummy_card_id)
    runner_dream.state.set_true_hand(1, 2, dummy_card_id)
    runner_dream.state.set_true_hand(1, 3, dummy_card_id)

    # 攻撃アクション
    runner_dream.step(ActionType.ACTION_SELECT_HAND_0)
    runner_dream.step(ActionType.ACTION_TARGET_OPP)

    # 防御選択 -> 確定
    runner_dream.step(ActionType.ACTION_SELECT_HAND_0)

    # 確定する前の、プレイヤー1の手札（スロット1, 2, 3）が dummy_card_id であることを確認
    assert runner_dream.state.get_true_hand(1, 1) == dummy_card_id
    assert runner_dream.state.get_true_hand(1, 2) == dummy_card_id
    assert runner_dream.state.get_true_hand(1, 3) == dummy_card_id

    runner_dream.step(ActionType.ACTION_CONFIRM)

    # ダメージ解決され、ターン終了処理（ドロー補充）を経て PHASE_MAIN に戻る
    assert runner_dream.state.current_phase == godfield_core.GamePhase.PHASE_MAIN
    # 被ダメージは 0 なので HP は 40 のまま
    assert runner_dream.state.get_hp(1) == 40
    # 夢状態になっていること
    assert runner_dream.state.get_curses(1, godfield_core.CurseType.CURSE_DREAM) == True

    # 手札が一新（リフレッシュ）されていることを検証
    # 元々の dummy_card_id (punch_id) はすべて消失し、山札から新しく引いたカードになっているはず
    # 最低限、各スロットが CARD_EMPTY ではなくなり、is_used が False にクリアされドロー補充が完了していることを確認。
    for j in range(4):
        assert runner_dream.state.get_true_hand(1, j) != -1
        assert runner_dream.state.get_is_used(1, j) == False


def test_saw_bunbun_multiple_attacks():
    """
    検証内容: のこぶんぶん（基本2回攻撃）と蜃気楼（重ねがけ倍）の複数回攻撃解決処理。
    1. のこぶんぶん単体（2回攻撃）:
       - Aが「のこぶんぶん」（ATK3）を使用、B（HP40）をターゲット。
       - 1回目：Bが「木の盾」（DEF2）で防御して確定。ダメージは 3 - 2 = 1。
       - フェイズが依然として PHASE_DEFENSE で、Bの仮置き場がクリアされていることを確認。
       - 2回目：Bが何も出さずに確定（CONFIRM）。ダメージ 3 が適用され、合計で B の HP が 40 - 1 - 3 = 36 になる。
       - 2回目の解決でターンが終了し PHASE_MAIN に戻ることを確認。
    2. のこぶんぶん ＋ 流星 ＋ 蜃気楼 x 3 (6回攻撃):
       - Aが「のこぶんぶん」（ATK3）、「流星」（ATK10、光属性、MP7）、「蜃気楼」3枚を使用。
       - 蜃気楼3枚なので、攻撃回数は 2 * 3 = 6回。
       - 5回目までBが防御なしで CONFIRM。毎解決ごとに PHASE_DEFENSE に戻る。
       - 6回目で CONFIRM するとターンが解決し、合計 13 * 6 = 78 ダメージが適用されて B の HP が 100 - 78 = 22 になる。
    """
    saw_bunbun_id = find_card_by_name("weapons/saw-boom-boom")
    mirage_id = find_card_by_name("＜蜃気楼＞")
    meteor_id = find_card_by_name("＜流星＞")
    wood_shield_id = find_card_by_name("armor/wood-shield")

    # 1. のこぶんぶん単体のテスト
    runner1 = SimulationRunner()
    runner1.state.seed_rng(42)
    runner1.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner1.state.current_actor_id = 0
    runner1.set_status(0, hp=40, mp=10)
    runner1.set_status(1, hp=40, mp=10)

    runner1.state.set_true_hand(0, 0, saw_bunbun_id)
    runner1.state.set_true_hand(1, 0, wood_shield_id)

    # 攻撃選択 -> ターゲット
    runner1.step(ActionType.ACTION_SELECT_HAND_0)
    runner1.step(ActionType.ACTION_TARGET_OPP)

    # 防御フェイズ
    assert runner1.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
    assert runner1.state.current_actor_id == 1
    assert runner1.state.remaining_attacks == 2

    # 1回目の防御：木の盾を選択して確定
    runner1.step(ActionType.ACTION_SELECT_HAND_0)
    runner1.step(ActionType.ACTION_CONFIRM)

    # まだ攻撃が残っているので、フェイズは PHASE_DEFENSE のまま
    assert runner1.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
    assert runner1.state.current_actor_id == 1
    assert runner1.state.remaining_attacks == 1
    # 1回目のダメージ 3 - 2 = 1 がすでに適用されていること
    assert runner1.state.get_hp(1) == 39
    # 防御側の仮置き場がクリアされていること
    assert runner1.state.get_num_staged_cards(1) == 0

    # 2回目の防御：何も出さずに確定
    runner1.step(ActionType.ACTION_CONFIRM)

    # 2回目が終了したのでターン終了処理を経て PHASE_MAIN に戻る
    assert runner1.state.current_phase == godfield_core.GamePhase.PHASE_MAIN
    # 2回目のダメージ 3 が追加で適用され、合計HPは 39 - 3 = 36
    assert runner1.state.get_hp(1) == 36
    assert runner1.state.remaining_attacks == 0

    # 2. のこぶんぶん ＋ 流星 ＋ 蜃気楼 x 3 のテスト
    runner2 = SimulationRunner()
    runner2.state.seed_rng(42)
    runner2.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner2.state.current_actor_id = 0
    # MPが十分にある状態にする（蜃気楼はMP5消費、流星はMP7消費）
    runner2.set_status(0, hp=100, mp=40)
    runner2.set_status(1, hp=100, mp=40)

    runner2.state.set_true_hand(0, 0, saw_bunbun_id)
    runner2.state.set_true_hand(0, 1, meteor_id)
    runner2.state.set_true_hand(0, 2, mirage_id)
    runner2.state.set_true_hand(0, 3, mirage_id)
    runner2.state.set_true_hand(0, 4, mirage_id)

    # のこぶんぶん選択 -> 流星重ね -> 蜃気楼重ね (蜃気楼追加でPHASE_GROUP_WEAPONに遷移するはず)
    runner2.step(ActionType.ACTION_SELECT_HAND_0)
    runner2.step(ActionType.ACTION_SELECT_HAND_1)
    runner2.step(ActionType.ACTION_SELECT_HAND_2)
    assert runner2.state.current_phase == godfield_core.GamePhase.PHASE_GROUP_WEAPON

    # 残りの蜃気楼も重ねる
    runner2.step(ActionType.ACTION_SELECT_HAND_3)
    runner2.step(ActionType.ACTION_SELECT_HAND_4)

    # ターゲット
    runner2.step(ActionType.ACTION_TARGET_OPP)

    # 攻撃回数は 2 * 3 = 6回
    assert runner2.state.remaining_attacks == 6
    assert runner2.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE

    # 1〜5回目までの攻撃解決 (防御なしで CONFIRM)
    for i in range(5):
        runner2.step(ActionType.ACTION_CONFIRM)
        assert runner2.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
        assert runner2.state.remaining_attacks == (5 - i)
        # ダメージ (3 + 10 = 13) が被弾するごとに適用されていること
        assert runner2.state.get_hp(1) == 100 - 13 * (i + 1)

    # 6回目の解決
    runner2.step(ActionType.ACTION_CONFIRM)

    # 解決完了、ターン終了処理を経て PHASE_MAIN に戻る
    assert runner2.state.current_phase == godfield_core.GamePhase.PHASE_MAIN
    # 合計 13 * 6 = 78 ダメージが適用されて HP は 22 になる
    assert runner2.state.get_hp(1) == 22
    assert runner2.state.remaining_attacks == 0


def test_aura_miracle_effects():
    """
    検証内容: ＜オーラ＞による攻撃力倍化、無属性化、評価順序の維持、およびマジカルステッキとの連動。
    1. パンチ ＋ オーラ (ATK 20, 無属性):
       - パンチ(ATK10)、オーラを重ねて攻撃。
       - 合計攻撃力 10 * 2 = 20、属性は ELEM_NONE (無属性) に解決されることを確認。
    2. オーラの後ろに置いた攻撃の挙動 (パンチ ＋ オーラ ＋ 吹き矢 = ATK 25, 無属性):
       - パンチ(10)、オーラ、吹き矢(ATK5)を順に重ねて攻撃.
       - 合計攻撃力が (10 * 2) + 5 = 25 になることを検証（吹き矢は倍化されない）。
    3. 属性の上書き検証 (流星 ＋ オーラ = ATK 26, 無属性):
       - 流星（ATK13、光属性）、オーラを重ねて攻撃。
       - 合計攻撃力 13 * 2 = 26、属性が ELEM_NONE に解決されることを確認。
    4. オーラの重ねがけ (パンチ ＋ オーラ ＋ オーラ = ATK 40, 無属性):
       - パンチ(10)、オーラ、オーラを重ねて攻撃。
       - 合計攻撃力 10 * 2 * 2 = 40 になることを検証。
    5. マジカルステッキとの連動 (ステッキ ＋ 流星 ＋ オーラ = ATK 28, 無属性, 消費MP15):
       - MP15 のプレイヤー0が、[マジカルステッキ, 流星, オーラ] を重ねて攻撃。
       - 流星MP7 ＋ オーラMP6 ＝ 他の合計消費MP 13。残りMP 2。
       - ステッキは 2 * 2 = 4 の攻撃力を追加し、残りMP2も消費されるため合計消費MPは15になる。
       - オーラ前の合計攻撃力は 4 + 10 (流星の力) = 14。
       - オーラで2倍になり、最終攻撃力は 14 * 2 = 28、属性は ELEM_NONE、消費MPは15になることを確認。
    """
    aura_id = find_card_by_name("＜オーラ＞")
    punch_id = find_card_by_name("weapons/punch")
    blowpipe_id = find_card_by_name("吹き矢")
    meteor_id = find_card_by_name("＜流星＞")
    magical_stick_id = find_card_by_name("weapons/magical-stick")

    # 1. パンチ ＋ オーラ のテスト
    runner1 = SimulationRunner()
    runner1.state.seed_rng(42)
    runner1.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner1.state.current_actor_id = 0
    runner1.set_status(0, hp=40, mp=10)
    runner1.set_status(1, hp=40, mp=10)
    runner1.state.set_true_hand(0, 0, punch_id)
    runner1.state.set_true_hand(0, 1, aura_id)

    # 重ねがけ
    runner1.step(ActionType.ACTION_SELECT_HAND_0)
    runner1.step(ActionType.ACTION_SELECT_HAND_1)
    runner1.step(ActionType.ACTION_TARGET_OPP)

    # 攻撃力評価の検証
    assert runner1.state.pending_attack_power == 6
    assert runner1.state.pending_attack_element == godfield_core.Element.ELEM_NONE
    assert runner1.state.get_mp(0) == 4  # 10 - 6

    # 2. オーラの後ろに置いた攻撃の挙動テスト
    runner2 = SimulationRunner()
    runner2.state.seed_rng(42)
    runner2.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner2.state.current_actor_id = 0
    runner2.set_status(0, hp=40, mp=10)
    runner2.set_status(1, hp=40, mp=10)
    runner2.state.set_true_hand(0, 0, punch_id)
    runner2.state.set_true_hand(0, 1, aura_id)
    runner2.state.set_true_hand(0, 2, blowpipe_id)

    runner2.step(ActionType.ACTION_SELECT_HAND_0)
    runner2.step(ActionType.ACTION_SELECT_HAND_1)
    runner2.step(ActionType.ACTION_SELECT_HAND_2)
    runner2.step(ActionType.ACTION_TARGET_OPP)

    # (3 * 2) + 1 = 7
    assert runner2.state.pending_attack_power == 7
    assert runner2.state.pending_attack_element == godfield_core.Element.ELEM_NONE
    assert runner2.state.get_mp(0) == 4  # 10 - 6

    # 3. 属性の上書き検証テスト (パンチ ＋ 流星 ＋ オーラ = ATK 26, 無属性)
    runner3 = SimulationRunner()
    runner3.state.seed_rng(42)
    runner3.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner3.state.current_actor_id = 0
    runner3.set_status(0, hp=40, mp=20)
    runner3.set_status(1, hp=40, mp=20)
    runner3.state.set_true_hand(0, 0, punch_id)
    runner3.state.set_true_hand(0, 1, meteor_id)
    runner3.state.set_true_hand(0, 2, aura_id)

    runner3.step(ActionType.ACTION_SELECT_HAND_0)
    runner3.step(ActionType.ACTION_SELECT_HAND_1)
    runner3.step(ActionType.ACTION_SELECT_HAND_2)
    runner3.step(ActionType.ACTION_TARGET_OPP)

    # (3 + 10) * 2 = 26
    assert runner3.state.pending_attack_power == 26
    # 属性は無属性(ELEM_NONE)に上書きされること
    assert runner3.state.pending_attack_element == godfield_core.Element.ELEM_NONE
    assert runner3.state.get_mp(0) == 7  # 20 - (7 + 6)

    # 4. オーラの重ねがけテスト
    runner4 = SimulationRunner()
    runner4.state.seed_rng(42)
    runner4.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner4.state.current_actor_id = 0
    runner4.set_status(0, hp=40, mp=20)
    runner4.state.set_true_hand(0, 0, punch_id)
    runner4.state.set_true_hand(0, 1, aura_id)
    runner4.state.set_true_hand(0, 2, aura_id)

    runner4.step(ActionType.ACTION_SELECT_HAND_0)
    runner4.step(ActionType.ACTION_SELECT_HAND_1)
    runner4.step(ActionType.ACTION_SELECT_HAND_2)
    runner4.step(ActionType.ACTION_TARGET_OPP)

    # 3 * 2 * 2 = 12
    assert runner4.state.pending_attack_power == 12
    assert runner4.state.get_mp(0) == 8  # 20 - 12

    # 5. マジカルステッキとの連動テスト (MP15のケース)
    runner5 = SimulationRunner()
    runner5.state.seed_rng(42)
    runner5.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner5.state.current_actor_id = 0
    runner5.set_status(0, hp=40, mp=15)
    runner5.set_status(1, hp=40, mp=15)
    runner5.state.set_true_hand(0, 0, magical_stick_id)
    runner5.state.set_true_hand(0, 1, meteor_id)
    runner5.state.set_true_hand(0, 2, aura_id)

    runner5.step(ActionType.ACTION_SELECT_HAND_0)
    runner5.step(ActionType.ACTION_SELECT_HAND_1)
    runner5.step(ActionType.ACTION_SELECT_HAND_2)
    runner5.step(ActionType.ACTION_TARGET_OPP)

    # 流星MP7 + オーラMP6 = 13. 残りMP = 2
    # ステッキ攻撃力 = 2 * 2 = 4
    # オーラ前の合計 = 4 + 10 = 14
    # オーラによる倍化 = 14 * 2 = 28
    assert runner5.state.pending_attack_power == 28
    assert runner5.state.pending_attack_element == godfield_core.Element.ELEM_NONE
    assert runner5.state.get_mp(0) == 0  # 全消費


def test_saw_bunbun_bounce_target_reset():
    """
    検証内容: のこぶんぶん（2回攻撃）中に反射が発生した際のターゲット正常リセット検証。
    - プレイヤー0（のこぶんぶん）がプレイヤー1を攻撃。
    - プレイヤー1が反射剣で防御し、1回目を反射。
    - 攻守交代してプレイヤー0に跳ね返り攻撃が当たる。プレイヤー0がCONFIRMして被弾（残り攻撃回数1）。
    - 2回目の連撃が、正しく元の攻撃の向き（プレイヤー0からプレイヤー1）にリセットされ、
      プレイヤー1が防御フェイズ（PHASE_DEFENSE, current_actor_id = 1）になることを確認する。
    """
    saw_bunbun_id = find_card_by_name("weapons/saw-boom-boom")
    reflect_sword_id = find_card_by_name("反射剣")

    runner = SimulationRunner()
    runner.state.seed_rng(42)
    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.set_status(0, hp=40, mp=10)
    runner.set_status(1, hp=40, mp=10)

    runner.state.set_true_hand(0, 0, saw_bunbun_id)
    runner.state.set_true_hand(1, 0, reflect_sword_id)

    # 攻撃
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_TARGET_OPP)

    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
    assert runner.state.current_actor_id == 1
    assert runner.state.remaining_attacks == 2

    # 1回目を反射
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_CONFIRM)

    # 反射により攻守交代。 me=0 が防御側になり、防御フェイズに入る
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
    assert runner.state.current_actor_id == 0

    # プレイヤー0が被弾を確定 (CONFIRM)
    runner.step(ActionType.ACTION_CONFIRM)

    # この被弾解決により remaining_attacks == 1 になる。
    # 2回目が本来の方向（プレイヤー0からプレイヤー1への攻撃）で再開し、
    # プレイヤー1が防御フェイズになっていることを確認。
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
    assert runner.state.current_actor_id == 1
    assert runner.state.remaining_attacks == 1


def test_dreaming_hat_miracle_clearance():
    """
    検証内容: 夢見る帽子による手札・展開済み奇跡の完全破棄とドロー補充。
    - プレイヤー1が手札に複数の奇跡（＜火の玉＞など）と、展開された奇跡を持っている。
    - プレイヤー1が夢見る帽子で防御。
    - 防御解決後、プレイヤー1の手札および展開済み奇跡がすべて破棄（消滅）され、
      ターン終了時に新しい手札（奇跡が自動展開されていないもの）が一新されて補充されることを確認。
    """
    punch_id = find_card_by_name("weapons/punch")
    dreaming_hat_id = find_card_by_name("armor/dreaming-hat")
    fireball_id = find_card_by_name("＜火の玉＞")

    runner = SimulationRunner()
    runner.state.seed_rng(42)
    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.set_status(0, hp=40, mp=20)
    runner.set_status(1, hp=40, mp=20)

    runner.state.set_true_hand(0, 0, punch_id)

    # プレイヤー1に手札をフルに持たせ（すべてパンチ）、そのうちスロット0を夢見る帽子、スロット1を奇跡カードにする
    for j in range(18):
        runner.state.set_true_hand(1, j, punch_id)
    runner.state.set_true_hand(1, 0, dreaming_hat_id)
    runner.state.set_true_hand(1, 1, fireball_id)

    # プレイヤー1の奇跡を場に展開する (スロット1に fireball を展開)
    runner.state.set_is_deployed(1, 1, True)

    # 攻撃
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_TARGET_OPP)

    # プレイヤー1が夢見る帽子で防御し、確定
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_CONFIRM)

    # ターン解決後
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_MAIN
    assert runner.state.get_curses(1, godfield_core.CurseType.CURSE_DREAM) == True

    # 展開されていた奇跡が消滅していることを確認
    assert runner.state.get_is_deployed(1, 1) == False

    # すべての手札が CARD_EMPTY 以外の新しいカードになり、それらが deploy されていないことを確認
    # (MAX_HAND_SIZE = 18)
    for j in range(18):
        assert runner.state.get_true_hand(1, j) != -1
        assert runner.state.get_is_deployed(1, j) == False
        assert runner.state.get_is_used(1, j) == False


def test_mars_ring_counter():
    """
    検証内容: 火星の指輪による反撃ダメージ処理。
    - Aが「パンチ」（ATK3）でB（HP40）を攻撃。
    - Bが「火星の指輪」（確率75%、火属性、ATK=被ダメ）で防御し確定。
    - 被ダメージ3（HP40->37）を受け、75%の確率ロールに成功すれば、Aに対して火属性・ATK3の反撃が飛ぶ。
    - 反撃によりAが防御フェイズになり、Aが「木の盾」（DEF2）で防御して確定。被ダメージ1（HP40->39）となり終了。
    """
    punch_id = find_card_by_name("weapons/punch")
    mars_ring_id = find_card_by_name("armor/mars-ring")
    ice_shield_id = find_card_by_name("アイスシールド")

    runner = SimulationRunner()
    runner.state.seed_rng(42)  # ロール成功するシード値
    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.set_status(0, hp=40, mp=10)
    runner.set_status(1, hp=40, mp=10)

    runner.state.set_true_hand(0, 0, punch_id)
    runner.state.set_true_hand(0, 1, ice_shield_id)
    runner.state.set_true_hand(1, 0, mars_ring_id)

    # A 攻撃
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_TARGET_OPP)

    # B 火星の指輪で防御し確定
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_CONFIRM)

    # 被ダメージ 3 なので B の HP は 37 になるはず
    assert runner.state.get_hp(1) == 37

    # 火星の指輪反撃が起動し、A(0) が防御側、フェイズは PHASE_DEFENSE、属性は火、攻撃力 3 になっていること
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
    assert runner.state.current_actor_id == 0
    assert runner.state.pending_attack_power == 3
    assert runner.state.pending_attack_element == godfield_core.Element.ELEM_FIRE

    # A 川の盾で防御し確定
    runner.step(ActionType.ACTION_SELECT_HAND_1)
    runner.step(ActionType.ACTION_CONFIRM)

    # A の被ダメージは 3 - 3 = 0 なので HP は 40 になり、フェイズは PHASE_MAIN に戻る
    assert runner.state.get_hp(0) == 40
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_MAIN


def test_jupiter_ring_curse():
    """
    検証内容: 木星の指輪による状態異常（夢）反撃。
    - Aが「パンチ」（ATK3）でB（HP40）を攻撃。
    - Bが「木星の指輪」（木属性、ATK0、夢付与）で防御し確定。 BのHPは37。
    - 反撃によりAに対して木属性・ATK0・夢の攻撃が起動。
    - Aが防具を出さずに確定（被弾）し、Aが「夢」状態になることを確認。
    """
    punch_id = find_card_by_name("weapons/punch")
    jupiter_ring_id = find_card_by_name("armor/jupiter-ring")

    runner = SimulationRunner()
    runner.state.seed_rng(42)
    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.set_status(0, hp=40, mp=10)
    runner.set_status(1, hp=40, mp=10)

    runner.state.set_true_hand(0, 0, punch_id)
    runner.state.set_true_hand(1, 0, jupiter_ring_id)

    # 攻撃
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_TARGET_OPP)

    # 防御
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_CONFIRM)

    # 反撃起動
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
    assert runner.state.current_actor_id == 0
    assert runner.state.pending_attack_power == 0
    assert runner.state.pending_attack_element == godfield_core.Element.ELEM_WOOD

    # 確定して被弾
    runner.step(ActionType.ACTION_CONFIRM)

    # ダメージは 0 なので A の HP は 40 のまま、夢状態になること
    assert runner.state.get_hp(0) == 40
    assert runner.state.get_curses(0, godfield_core.CurseType.CURSE_DREAM) == True
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_MAIN


def test_neptune_venus_rings():
    """
    検証内容: 海王の指輪によるMP回復と、金星の指輪によるお金没収およびミラー反射。
    - Aが「パンチ」（ATK3）でBを攻撃。 Bは海王の指輪、金星の指輪で防御し確定。
    - 海王の効果により、BのMPが被ダメージ3*2 = 6回復。
    - 金星の反撃により、Aに対して無属性・ATK3・没収フラグありの反撃が起動。
    - Aが何も出さずに被弾し、Aのお金が3減り、Bのお金が3増える。
    """
    punch_id = find_card_by_name("weapons/punch")
    neptune_ring_id = find_card_by_name("armor/neptune-ring")
    venus_ring_id = find_card_by_name("armor/venus-ring")

    runner = SimulationRunner()
    runner.state.seed_rng(42)
    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.set_status(0, hp=40, mp=10, money=20)
    runner.set_status(1, hp=40, mp=10, money=20)

    runner.state.set_true_hand(0, 0, punch_id)
    runner.state.set_true_hand(1, 0, neptune_ring_id)
    runner.state.set_true_hand(1, 1, venus_ring_id)

    # 攻撃
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_TARGET_OPP)

    # 重ねがけ防御
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_SELECT_HAND_1)
    runner.step(ActionType.ACTION_CONFIRM)

    # BのMPが 10 -> 16 (海王の効果) になっていること
    assert runner.state.get_mp(1) == 16
    assert runner.state.get_hp(1) == 37

    # 金星の没収反撃が起動 (Aが防御側、ATK3)
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
    assert runner.state.current_actor_id == 0
    assert runner.state.pending_attack_power == 3

    # Aが被弾
    runner.step(ActionType.ACTION_CONFIRM)

    # Aのお金が 20->17、Bのお金が 20->23 になっていること
    assert runner.state.get_money(0) == 17
    assert runner.state.get_money(1) == 23


def test_ring_multiple_attacks_delay():
    """
    検証内容: 連撃終了後の指輪一括解決。
    - Aが「のこぶんぶん」（2回攻撃）でBを攻撃。
    - 1回目：Bが「土星の指輪」で防御し確定（ダメージ3、土6反撃予約）。連撃中なので反撃はまだ起動しない。
    - 2回目：Bが「木の盾」で防御し確定（ダメージ1）。
    - 2回目の解決で連撃が終わり、予約されていた土星の指輪の反撃がここで初めて起動することを確認。
    """
    saw_bunbun_id = find_card_by_name("weapons/saw-boom-boom")
    saturn_ring_id = find_card_by_name("armor/saturn-ring")
    wood_shield_id = find_card_by_name("armor/wood-shield")

    runner = SimulationRunner()
    runner.state.seed_rng(42)
    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.set_status(0, hp=40, mp=10)
    runner.set_status(1, hp=40, mp=10)

    runner.state.set_true_hand(0, 0, saw_bunbun_id)
    runner.state.set_true_hand(1, 0, saturn_ring_id)
    runner.state.set_true_hand(1, 1, wood_shield_id)

    # A のこぶんぶん攻撃
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_TARGET_OPP)

    # B 1回目を土星の指輪で防御し確定
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_CONFIRM)

    # 1回目解決。まだ連撃残り1回あるため、フェイズはBの防御のまま（反撃は起動しない）
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
    assert runner.state.current_actor_id == 1
    assert runner.state.remaining_attacks == 1
    assert runner.state.get_hp(1) == 37

    # B 2回目を木の盾で防御し確定
    runner.step(ActionType.ACTION_SELECT_HAND_1)
    runner.step(ActionType.ACTION_CONFIRM)

    # 2回目解決。連撃終了し、予約されていた土星の反撃（土・ATK6 = 3*2）がAに対して起動することを確認
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
    assert runner.state.current_actor_id == 0
    assert runner.state.pending_attack_power == 6
    assert runner.state.pending_attack_element == godfield_core.Element.ELEM_STONE


def test_ring_counter_super_mirror_chain():
    """
    検証内容: 指輪反撃に対するスーパーミラーによる反射（没収効果含む）。
    - Aが「パンチ」（ATK3）でBを攻撃。 Bが「金星の指輪」で防御確定。被ダメ3。
    - Bからの金星反撃（ATK3、没収）に対し、Aが「スーパーミラー」で反射確定。
    - 反射により、Bに対して金星没収（ATK3）が戻り、Bが被弾してBのお金がAに没収されることを検証。
    """
    punch_id = find_card_by_name("weapons/punch")
    venus_ring_id = find_card_by_name("armor/venus-ring")
    super_mirror_id = find_card_by_name("armor/super-mirror")

    runner = SimulationRunner()
    runner.state.seed_rng(42)
    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.set_status(0, hp=40, mp=10, money=20)
    runner.set_status(1, hp=40, mp=10, money=20)

    runner.state.set_true_hand(0, 0, punch_id)
    runner.state.set_true_hand(0, 1, super_mirror_id)
    runner.state.set_true_hand(1, 0, venus_ring_id)

    # 攻撃
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_TARGET_OPP)

    # Bが金星の指輪で防御し確定
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_CONFIRM)

    # Aに対して金星の没収反撃（ATK3）が起動
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
    assert runner.state.current_actor_id == 0

    # Aがスーパーミラーで反射し確定
    runner.step(ActionType.ACTION_SELECT_HAND_1)
    runner.step(ActionType.ACTION_CONFIRM)

    # 反射により、Bに対して再び金星没収（ATK3）が返る (current_actor_id = 1)
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
    assert runner.state.current_actor_id == 1
    assert runner.state.pending_attack_power == 3

    # Bが被弾
    runner.step(ActionType.ACTION_CONFIRM)

    # Bのお金が没収され 20->17、Aのお金が 20->23 になること。かつBはダメージ3を受けること
    assert runner.state.get_money(1) == 17
    assert runner.state.get_money(0) == 23
    assert runner.state.get_hp(1) == 34


def test_pending_attack_source_id_and_observation():
    """
    検証内容:
    1. 通常攻撃時、 pending_attack_source_id に攻撃武器のカードIDが格納されること。
    2. 守護神仮想カードIDが正常に取得でき、pending_attack_source_id にセットされた際、
       AI 観測 (Observation) の opponent_staged_cards[0] に正しく統合・注入されていること。
    """
    punch_id = find_card_by_name("weapons/punch")
    ice_shield_id = find_card_by_name("アイスシールド")

    # 守護神の仮想カードが正しくロードできていることの検証
    fire_roar_id = find_card_by_name("gurdians/fire-roar")
    blessing_id = find_card_by_name("gurdians/blessing")
    full_moon_blade_id = find_card_by_name("gurdians/full-moon-blade")

    assert fire_roar_id > 0
    assert blessing_id > 0
    assert full_moon_blade_id > 0

    runner = SimulationRunner()
    runner.state.seed_rng(42)
    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.set_status(0, hp=40, mp=10)
    runner.set_status(1, hp=40, mp=10)

    runner.state.set_true_hand(0, 0, punch_id)
    runner.state.set_true_hand(0, 1, ice_shield_id)

    # --- 1. 通常攻撃の検証 ---
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_TARGET_OPP)

    # 防御フェイズになり、攻撃発生源 ID がパンチの ID になっていること
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
    assert runner.state.pending_attack_source_id == punch_id

    # 防御側 (プレイヤー1) の AI 観測で opponent_staged_cards[0] がパンチ ID であること
    obs_opponent_staged = godfield_core.get_opponent_staged_cards_for_obs(runner.state, 1)
    assert obs_opponent_staged[0] == punch_id

    # 防御確定して解決
    runner.step(ActionType.ACTION_CONFIRM)
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_MAIN
    # 解決後は source_id がクリアされていること
    assert runner.state.pending_attack_source_id == -1

    # --- 2. 守護神攻撃および Observation 統合の検証 ---
    # 状態を手動で「火星神の咆哮(火25)攻撃を受けている状態」に設定する
    runner.state.current_phase = godfield_core.GamePhase.PHASE_DEFENSE
    runner.state.attacker_id = 1
    runner.state.defender_id = 0
    runner.state.current_actor_id = 0
    # 相手(1)の staged は 0 枚
    runner.state.set_num_staged_cards(1, 0)

    # 発生源に火星神の仮想カードをセット
    runner.state.pending_attack_source_id = fire_roar_id

    # 防御側 (自分=0) の AI 観測で opponent_staged_cards[0] に火星神の仮想カードIDが統合されていることを検証
    obs_opponent_staged_me = godfield_core.get_opponent_staged_cards_for_obs(runner.state, 0)
    assert obs_opponent_staged_me[0] == fire_roar_id
