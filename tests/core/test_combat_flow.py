import godfield_core
from godfield_core import ActionType, GamePhase
from tests.core.test_utils import SimulationRunner, find_card_by_name, get_all_cards, find_card_by_type
import pytest


# ==========================================
# Merged from: tests/core/test_basic.py
# ==========================================



def test_basic_attack_state_transition():
    """
    検証内容: 非合法手（違法なアクション）を選択した際に、ゲーム状態が遷移せずに無視されることをテストする。
    具体的には、守護神フェーズ (PHASE_GUARDIAN) において、手札決定アクション (ACTION_TARGET_OPP) は非合法であるため、
    ステップを実行してもフェーズやアクティブプレイヤーなどの状態が一切変化しないことを確認する。
    """
    sim = SimulationRunner()

    sim.set_status(player=0, hp=40)
    sim.set_status(player=1, hp=40)

    # 初期状態のアクティブプレイヤーが 0 であることを確認
    assert sim.state.current_actor_id == 0
    sim.state.current_phase = godfield_core.GamePhase.PHASE_GUARDIAN
    assert sim.state.current_phase == godfield_core.GamePhase.PHASE_GUARDIAN

    # 守護神フェーズにおいて無効なアクション 18 (ACTION_TARGET_OPP) を実行
    sim.step(godfield_core.ActionType.ACTION_TARGET_OPP)

    # アクションは無視され、状態が変わっていないことをアサート
    assert sim.state.current_phase == godfield_core.GamePhase.PHASE_GUARDIAN
    assert sim.state.current_actor_id == 0


def test_env_pool_reset_clears_events():
    """EnvPool.reset(seed) がイベント履歴(events)や状態異常・守護神を完全にクリアすることを確認"""
    pool = godfield_core.EnvPool(1)
    pool.reset(0)

    state = pool.get_state(0)
    godfield_core.step_game(state, godfield_core.ActionType.ACTION_PRAY)
    obs = godfield_core.get_observation(state, 0)
    assert len(obs.get_history()) > 0

    # リセット実行
    pool.reset(42)
    new_state = pool.get_state(0)
    new_obs = godfield_core.get_observation(new_state, 0)

    # リセット直後は過去のイベントログがクリアされ初期状態になっていること
    valid_events = [ev for ev in new_obs.get_history() if hasattr(ev, "event_type") and ev.event_type != 0]
    assert len(valid_events) == 0

# ==========================================
# Merged from: tests/core/test_weapon_attacks.py
# ==========================================



def test_physical_attack_phase_transition():
    runner = SimulationRunner()
    weapon_id = find_card_by_name("パンチ")

    runner.state.set_true_hand(0, 0, weapon_id)
    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0

    runner.perform_attack([0])

    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
    assert runner.state.defender_id == 1
    assert runner.state.current_actor_id == 1


def test_physical_attack_pending_atk_power():
    runner = SimulationRunner()
    weapon_id = find_card_by_name("パンチ")

    runner.state.set_true_hand(0, 0, weapon_id)
    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0

    runner.perform_attack([0])

    assert runner.state.pending_attack_power == 3


def test_physical_defense_resolves_damage_and_turns():
    runner = SimulationRunner()
    weapon_id = find_card_by_name("パンチ")
    shield_id = find_card_by_name("革の服")

    runner.state.set_true_hand(0, 0, weapon_id)
    runner.state.set_true_hand(1, 0, shield_id)
    runner.set_status(1, hp=40)

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0

    runner.perform_attack([0])
    runner.perform_defense([0])

    assert runner.state.get_hp(1) == 39
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_MAIN
    assert runner.state.current_actor_id == 1


def test_physical_self_attack_resolves_instantly():
    runner = SimulationRunner()
    weapon_id = find_card_by_name("パンチ")

    runner.state.set_true_hand(0, 0, weapon_id)
    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.set_status(0, hp=40)

    runner.perform_attack([0], to_self=True)

    assert runner.state.get_hp(0) < 40
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
    runner.perform_attack([0])

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
    runner_real.perform_attack([0])

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

    runner.perform_attack([0])
    runner.step(ActionType.ACTION_CONFIRM)  # 防御側は確定

    assert runner.state.get_hp(1) == 26  # 40 - 14
    assert runner.state.get_hp(0) == 26  # 40 - 14 (自傷)

    # 2. 自分をターゲットにした時の2倍自傷
    runner_self = SimulationRunner()
    runner_self.set_status(0, hp=40, mp=0)
    runner_self.state.set_true_hand(0, 0, evil_id)

    runner_self.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner_self.state.current_actor_id = 0

    runner_self.perform_attack([0], to_self=True)  # 自分を攻撃して即時解決

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
    runner_bounce.perform_defense([0])

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
    assert runner_2.state.pending_attack_element == godfield_core.Element.ELEM_NONE

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
    assert runner_3.state.pending_attack_element == godfield_core.Element.ELEM_NONE

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

        runner.perform_attack([0])

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

        runner.perform_attack([0])

        # 防御フェイズを介さずに自動解決され PHASE_MAIN になる
        assert runner.state.current_phase == godfield_core.GamePhase.PHASE_MAIN

        if runner.state.get_hp(0) == 1:
            p0_hit += 1
            # プレイヤー0が被弾。0のウスが1枚消費され(残り2枚)、1のウスは消費されていない(残り2枚)
            count_0 = sum(
                1
                for j in range(18)
                if runner.state.get_true_hand(0, j) == mortar_id and not runner.state.get_is_used(0, j)
            )
            count_1 = sum(
                1
                for j in range(18)
                if runner.state.get_true_hand(1, j) == mortar_id and not runner.state.get_is_used(1, j)
            )
            assert count_0 == 2
            assert count_1 == 2
        else:
            p1_hit += 1
            # プレイヤー1が被弾。1のウスが1枚消費され(残り1枚)、0のウスは消費されていない(残り3枚)
            count_0 = sum(
                1
                for j in range(18)
                if runner.state.get_true_hand(0, j) == mortar_id and not runner.state.get_is_used(0, j)
            )
            count_1 = sum(
                1
                for j in range(18)
                if runner.state.get_true_hand(1, j) == mortar_id and not runner.state.get_is_used(1, j)
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
    runner_scenario.perform_attack([0])

    # Bが100%被弾するが、お守りでHP10に復活していること
    assert runner_scenario.state.get_hp(1) == 10

    # Bのお守りは消費され、かつウスが「1枚だけ」消費されていること (残り1枚)
    count_1_after_1st = sum(
        1
        for j in range(18)
        if runner_scenario.state.get_true_hand(1, j) == mortar_id and not runner_scenario.state.get_is_used(1, j)
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
        if runner_scenario.state.get_true_hand(1, j) == mortar_id and not runner_scenario.state.get_is_used(1, j)
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
    runner_fever.perform_attack([0])

    # 防御フェイズ
    assert runner_fever.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
    assert runner_fever.state.current_actor_id == 1

    # 防御選択 -> 確定
    runner_fever.perform_defense([0])

    # ダメージ解決され、ターン終了処理を経て PHASE_MAIN に戻る
    assert runner_fever.state.current_phase == godfield_core.GamePhase.PHASE_MAIN
    # 被ダメージは 0。熱病にかかったが、ターン終了判定はターンプレイヤー(P0)に対して行われるため、P1のHPは40のまま
    assert runner_fever.state.get_hp(1) == 40
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
    runner_dream.perform_attack([0])

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
    leather_clothes_id = find_card_by_name("armor/leather-clothes")

    # 1. のこぶんぶん単体のテスト
    runner1 = SimulationRunner()
    runner1.state.seed_rng(42)
    runner1.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner1.state.current_actor_id = 0
    runner1.set_status(0, hp=40, mp=10)
    runner1.set_status(1, hp=40, mp=10)

    runner1.state.set_true_hand(0, 0, saw_bunbun_id)
    runner1.state.set_true_hand(1, 0, leather_clothes_id)

    # 攻撃選択 -> ターゲット
    runner1.perform_attack([0])

    # 防御フェイズ
    assert runner1.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
    assert runner1.state.current_actor_id == 1
    assert runner1.state.remaining_attacks == 2

    # 1回目の防御：革の服を選択して確定
    runner1.perform_defense([0])

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
    runner1.perform_attack([1])

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
    runner2.perform_attack([2])

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
    runner3.perform_attack([2])

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
    runner4.perform_attack([2])

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
    runner5.perform_attack([2])

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
    runner.perform_attack([0])

    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
    assert runner.state.current_actor_id == 1
    assert runner.state.remaining_attacks == 2

    # 1回目を反射
    runner.perform_defense([0])

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
    runner.perform_attack([0])

    # プレイヤー1が夢見る帽子で防御し、確定
    runner.perform_defense([0])

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
    runner.perform_attack([0])

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


def test_attack_on_dead_player():
    """
    検証内容: HPが0の相手への複数回攻撃。
    - Aがノコギリブンブン（2回攻撃）で、すでにHPが0のBを攻撃。
    - Bの防御フェイズが2回発生し、いずれも confirm しか選択できない（非合法な防具選択はできない）。
    - 2回の攻撃とも confirm を押して消化され、最後まで攻撃が継続し、その後にターン終了（Aの勝利）となること。
    """
    saw_id = find_card_by_name("weapons/saw-boom-boom")
    leather_clothes_id = find_card_by_name("armor/leather-clothes")

    runner = SimulationRunner()
    runner.state.seed_rng(42)
    runner.set_status(0, hp=40, mp=10)
    runner.set_status(1, hp=0, mp=10) # すでに死亡

    runner.state.set_true_hand(0, 0, saw_id)
    runner.state.set_true_hand(1, 0, leather_clothes_id)

    # A 攻撃
    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.perform_attack([0])

    # 1回目の攻撃の防御フェイズ
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
    assert runner.state.current_actor_id == 1

    # B（HP0）の合法手を検証
    actions = godfield_core.get_legal_actions(runner.state)
    # 革の服（スロット0）は選択不可（非合法手）であること
    assert actions[ActionType.ACTION_SELECT_HAND_0] is False
    # confirm（受諾）のみが合法手であること
    assert actions[ActionType.ACTION_CONFIRM] is True

    # 1回目被弾
    runner.step(ActionType.ACTION_CONFIRM)

    # 2回目の攻撃の防御フェイズが起動すること
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
    assert runner.state.current_actor_id == 1

    actions = godfield_core.get_legal_actions(runner.state)
    assert actions[ActionType.ACTION_SELECT_HAND_0] is False
    assert actions[ActionType.ACTION_CONFIRM] is True

    # 2回目被弾
    runner.step(ActionType.ACTION_CONFIRM)

    # 攻撃がすべて終了し、勝敗決定（Aの勝利、B死亡による）になること
    assert runner.state.is_done is True
    # A(0)が勝利、B(1)が敗北
    assert runner.state.get_hp(1) == 0


def test_amulet_revive_mid_attack():
    """
    検証内容: 複数回攻撃の途中で死亡した際のお守り即時復活。
    - Aがノコギリブンブン（2回攻撃、ATK5）でB（HP5）を攻撃。
    - Bは「太陽のお守り」を所持。
    - 1回目の攻撃でBが被弾 ➡ HP0になるが、お守りで即時にHP10で復活する。
    - そのため、2回目の攻撃の防御フェイズ移行時にはBのHPは10に回復している。
    """
    saw_id = find_card_by_name("weapons/saw-boom-boom")
    amulet_id = find_card_by_name("sundries/sun-amulet")

    runner = SimulationRunner()
    runner.state.seed_rng(42)
    runner.set_status(0, hp=40, mp=10)
    runner.set_status(1, hp=3, mp=10)

    runner.state.set_true_hand(0, 0, saw_id)
    runner.state.set_true_hand(1, 0, amulet_id)

    # A 攻撃
    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.perform_attack([0])

    # 1回目の防御フェイズ
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
    runner.step(ActionType.ACTION_CONFIRM) # B被弾

    # 被弾したその瞬間に復活してHPが10になり、かつ2回目の攻撃の防御フェイズが起動していること
    assert runner.state.get_hp(1) == 10
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
    assert runner.state.current_actor_id == 1

    # 2回目被弾
    runner.step(ActionType.ACTION_CONFIRM)

    # 2回目の被弾でHPが 10 - 3 = 7 になること。攻撃終了で PHASE_MAIN に戻る（お守りがないのでもう復活はないが死亡もしていない）
    assert runner.state.get_hp(1) == 7
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_MAIN
    assert runner.state.is_done is False


def test_ascension_bow_deferred_to_turn_end():
    """
    検証内容: 複数回攻撃中にHP0になっても、昇天弓は即座に発射されず、すべての攻撃が終了してターンエンドになった後に発射されること。
    - Aがノコギリブンブン（2回攻撃、ATK5）でB（HP5）を攻撃。
    - Bは「昇天弓」を所持。
    - 1回目の攻撃でBが被弾 ➡ HP0になる。お守りがないのでHP0のまま。
    - しかし即時に昇天弓は発射されず、2回目の攻撃が起動する。
    - BはHP0なので confirm しか押せず、2回目被弾。
    - 攻撃完了後、ターン終了処理（PHASE_END以降）に移行したタイミングで初めて昇天弓が発射され、Aに対する光属性30の防御フェイズが起動すること。
    """
    saw_id = find_card_by_name("weapons/saw-boom-boom")
    bow_id = find_card_by_name("weapons/ascension-bow")

    runner = SimulationRunner()
    # 昇天弓の確率ロール（75%）が成功するシード値を選択
    # 昇天弓の発射確率は75%
    runner.state.seed_rng(42)
    runner.set_status(0, hp=40, mp=10)
    runner.set_status(1, hp=3, mp=10)

    runner.state.set_true_hand(0, 0, saw_id)
    runner.state.set_true_hand(1, 0, bow_id)

    # A 攻撃
    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.perform_attack([0])

    # 1回目の防御フェイズ
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
    runner.step(ActionType.ACTION_CONFIRM) # B被弾、HP0になる

    # HPは0。昇天弓は即座に発射されず、2回目の防御フェイズが起動していること
    assert runner.state.get_hp(1) == 0
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
    assert runner.state.current_actor_id == 1

    # B（HP0）は confirm しか選択できない
    actions = godfield_core.get_legal_actions(runner.state)
    assert actions[ActionType.ACTION_CONFIRM] is True

    # 2回目被弾
    runner.step(ActionType.ACTION_CONFIRM)

    # 攻撃がすべて終了し、ターン終了処理（resolve_turn_end_steps）に進み、
    # そこで昇天弓の判定が行われ、昇天弓が発射（Aに対する光属性30ダメージの防御フェイズ）されること。
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
    assert runner.state.current_actor_id == 0 # Aが防御側
    assert runner.state.pending_attack_source_id == bow_id
    assert runner.state.pending_attack_power == 30
    assert runner.state.pending_attack_element == godfield_core.Element.ELEM_LIGHT


def test_dangerous_pestle_targets_only_alive():
    """
    検証内容: あぶないキネの対象は、生存している（HP > 0）のプレイヤーのみから選択されること。
    - プレイヤー0 (生存: HP40), プレイヤー1 (死亡: HP0)。
    - プレイヤー0があぶないキネを使用。
    - プレイヤー1が死亡しているため、プレイヤー1がキネの対象になることは絶対にない。
    - 100回試行し、すべてにおいてプレイヤー1が対象（PHASE_DEFENSEでアクターがプレイヤー1になる状態）にならないことをアサート。
    """
    pestle_id = find_card_by_name("weapons/dangerous-pestle")
    mortar_id = find_card_by_name("sundries/dangerous-mortar")
    super_mirror_id = find_card_by_name("armor/super-mirror")

    for idx in range(100):
        runner = SimulationRunner()
        runner.state.seed_rng(idx)
        runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
        runner.state.current_actor_id = 0
        runner.set_status(0, hp=40, mp=10)
        runner.set_status(1, hp=0, mp=10) # プレイヤー1は死亡

        runner.state.set_true_hand(0, 0, pestle_id)
        # プレイヤー1がウスを持っているが、死亡しているので無視されるべき
        runner.state.set_true_hand(1, 0, mortar_id)

        runner.perform_attack([0])

        # プレイヤー1が死亡しているので、絶対に攻撃対象にはならず、唯一の生存プレイヤーであるプレイヤー0（自分自身）が100%対象になる
        # 自分への自傷攻撃（光30ダメージ）が必ず適用され、HPが10になり、ターン終了（PHASE_END）に移行すること
        assert runner.state.get_hp(0) == 10
        assert runner.state.get_hp(1) == 0
        assert runner.state.current_phase == godfield_core.GamePhase.PHASE_END


def test_attack_plus_multi_index():
    """
    検証内容: スロット0以外の複数スロット武器プラス検証 (AGENTS.mdガイドライン準拠)。
    - 攻撃者が手札スロット 2 (疾風剣: ATK9) とスロット 4 (ブーメラン: +3) にカードを持つ。
    - スロット 2 を選択したのちにスロット 4 を選択し、相手に攻撃（合計攻撃力 12）。
    - 防御側は手札スロット 3 (木盾: DEF2) とスロット 5 (革の服: DEF2) を重ねがけ防御。
    - ダメージが 12 - (2 + 2) = 8 になり、防御側のHPが 40 -> 32 になること。
    - 選択順序を逆（スロット4 ➜ スロット2）にした場合も同様に処理されること。
    """
    gale_sword = find_card_by_name("weapons/gale-sword") # ATK 9, plus対応
    boomerang = find_card_by_name("ブーメラン")          # +ATK 3
    wood_shield = find_card_by_name("armor/wood-shield")  # DEF 2
    leather_clothes = find_card_by_name("armor/leather-clothes") # DEF 2

    # パターン1: 2 -> 4 の順で攻撃選択
    runner = SimulationRunner()
    runner.state.seed_rng(42)
    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.set_status(0, hp=40, mp=10)
    runner.set_status(1, hp=40, mp=10)

    # 0以外のインデックスに設定
    runner.state.set_true_hand(0, 2, gale_sword)
    runner.state.set_true_hand(0, 4, boomerang)
    runner.state.set_true_hand(1, 3, wood_shield)
    runner.state.set_true_hand(1, 5, leather_clothes)

    runner.perform_attack([2, 4])
    assert runner.state.pending_attack_power == 12

    runner.perform_defense([3, 5])
    assert runner.state.get_hp(1) == 32

    # パターン2: プラス武器を先に選択した場合、通常武器を後から重ねることはできない（非合法手になる）
    runner2 = SimulationRunner()
    runner2.state.seed_rng(42)
    runner2.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner2.state.current_actor_id = 0
    runner2.set_status(0, hp=40, mp=10)
    runner2.set_status(1, hp=40, mp=10)

    runner2.state.set_true_hand(0, 2, gale_sword)
    runner2.state.set_true_hand(0, 4, boomerang)
    runner2.state.set_true_hand(1, 3, wood_shield)
    runner2.state.set_true_hand(1, 5, leather_clothes)

    # 先にスロット4 (ブーメラン) を選択
    runner2.step(ActionType.ACTION_SELECT_HAND_4)
    # 通常武器であるスロット2 (疾風剣) は重ねがけできないため非合法手になっていることを確認
    legal = godfield_core.get_legal_actions(runner2.state)
    assert not legal[int(ActionType.ACTION_SELECT_HAND_2)]

    # そのまま相手を対象に攻撃確定
    runner2.step(ActionType.ACTION_TARGET_OPP)
    assert runner2.state.pending_attack_power == 3




# ==========================================
# Merged from: tests/core/test_elemental_attacks.py
# ==========================================



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
    runner.perform_attack([1])

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
    runner.perform_attack([1])

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
    runner.perform_attack([1])

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
    runner.perform_attack([1])

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
    runner.perform_attack([1])

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
    runner.perform_attack([1])

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
    runner.perform_attack([1])

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

    runner.perform_attack([0])

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

    runner.perform_attack([0])

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

    runner.perform_attack([0])

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
    runner.perform_defense([0])

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
    runner.perform_attack([1])

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
    runner.perform_attack([1])

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
    runner.perform_attack([1])

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

# ==========================================
# Merged from: tests/core/test_group_attacks.py
# ==========================================



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
    runner.perform_attack([2])

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
    runner.perform_attack([3])

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


# ==========================================
# Merged from: tests/core/test_spiritual_stacking.py
# ==========================================



def test_spiritual_doll_mp_bypass_availability():
    """
    検証内容: 精霊のぬいぐるみによるMP消費踏み倒し時のカード選択権。
    - 手持ちのMPが2の状態で、消費MP 2 の奇跡「＜火の玉＞」を選択した際、重ねがけフェイズ（PHASE_MIRACLE_PLUS）に遷移することを確認します。
    - 重ねがけフェイズにおいて、手札にある「精霊のぬいぐるみ」が合法手（選択可能）であることを確認します。
    """
    runner = SimulationRunner()
    fireball_id = find_card_by_name("＜火の玉＞")
    doll_id = find_card_by_name("精霊のぬいぐるみ")

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_mp(0, 2)

    runner.state.set_true_hand(0, 0, fireball_id)
    runner.state.set_true_hand(0, 1, doll_id)

    # 火の玉を選択
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_MIRACLE_PLUS

    # 重ねがけで「精霊のぬいぐるみ」が選択可能なこと
    legal_actions = godfield_core.get_legal_actions(runner.state)
    assert legal_actions[ActionType.ACTION_SELECT_HAND_1] is True


def test_spiritual_doll_mp_bypass_executes_with_zero_mp_cost():
    """
    検証内容: 精霊のぬいぐるみ使用時のMP消費ゼロ解決。
    - 奇跡「＜火の玉＞」に「精霊 of ぬいぐるみ」を重ねて攻撃を実行した際、MPが 2 から減らずに維持された状態で奇跡防御フェイズ（PHASE_MIRACLE_DEFENSE）に移行することを確認します。
    """
    runner = SimulationRunner()
    fireball_id = find_card_by_name("＜火の玉＞")
    doll_id = find_card_by_name("精霊のぬいぐるみ")

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_mp(0, 2)

    runner.state.set_true_hand(0, 0, fireball_id)
    runner.state.set_true_hand(0, 1, doll_id)

    runner.step(ActionType.ACTION_SELECT_HAND_0)  # 火の玉
    runner.step(ActionType.ACTION_SELECT_HAND_1)  # ぬいぐるみ
    runner.step(ActionType.ACTION_TARGET_OPP)

    # MPが 2 のままであること
    assert runner.state.get_mp(0) == 2
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_MIRACLE_DEFENSE


def test_high_cost_miracle_initial_selection():
    """
    検証内容: MP不足時の高コスト奇跡の選択権（精霊存在ルール）。
    - 自身のMPが 2 の際、手札に消費MP 5 の奇跡「＜闇＞」と「精霊のぬいぐるみ」がある場合、メインフェイズにおいて「＜闇＞」が選択可能（合法手）になることを確認します。
    - 精霊が手札に無い場合は、MP不足のため「＜闇＞」が非合法手になることも併せて確認します。
    """
    runner_with_doll = SimulationRunner()
    darkness_id = find_card_by_name("＜闇＞")
    doll_id = find_card_by_name("精霊のぬいぐるみ")

    runner_with_doll.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner_with_doll.state.current_actor_id = 0
    runner_with_doll.state.set_mp(0, 2)

    runner_with_doll.state.set_true_hand(0, 0, darkness_id)
    runner_with_doll.state.set_true_hand(0, 1, doll_id)

    # 手札に精霊がある場合は、闇の選択が合法であること
    actions_with_doll = godfield_core.get_legal_actions(runner_with_doll.state)
    assert actions_with_doll[ActionType.ACTION_SELECT_HAND_0] is True

    # 手札に精霊が無い場合
    runner_no_doll = SimulationRunner()
    runner_no_doll.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner_no_doll.state.current_actor_id = 0
    runner_no_doll.state.set_mp(0, 2)
    runner_no_doll.state.set_true_hand(0, 0, darkness_id)

    actions_no_doll = godfield_core.get_legal_actions(runner_no_doll.state)
    assert actions_no_doll[ActionType.ACTION_SELECT_HAND_0] is False


def test_high_cost_miracle_cannot_target_without_doll():
    """
    検証内容: 精霊を追加する前のターゲット制限。
    - MP不足の状態で高コスト奇跡「＜闇＞」を選択して仮置き（PHASE_MIRACLE_PLUS）した際、追加で精霊を置くまでは、ターゲット決定（TARGET_OPP）が非合法手になることを確認します。
    """
    runner = SimulationRunner()
    darkness_id = find_card_by_name("＜闇＞")
    doll_id = find_card_by_name("精霊のぬいぐるみ")

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_mp(0, 2)

    runner.state.set_true_hand(0, 0, darkness_id)
    runner.state.set_true_hand(0, 1, doll_id)

    # 闇を選択した直後
    runner.step(ActionType.ACTION_SELECT_HAND_0)

    # まだコストが踏み倒されていない（不足状態）ため、ターゲット指定は非合法であること
    legal_actions = godfield_core.get_legal_actions(runner.state)
    assert legal_actions[ActionType.ACTION_TARGET_OPP] is False


def test_high_cost_miracle_can_target_after_doll():
    """
    検証内容: 精霊を追加した後のターゲット解除と解決。
    - 仮置きした高コスト奇跡に対し、さらに「精霊のぬいぐるみ」を追加した時点で、ターゲット決定（TARGET_OPP）が合法化されることを確認します。
    - 攻撃実行後、MPが 2 を維持した状態で奇跡防御フェイズに移行することを確認します。
    """
    runner = SimulationRunner()
    darkness_id = find_card_by_name("＜闇＞")
    doll_id = find_card_by_name("精霊のぬいぐるみ")

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_mp(0, 2)

    runner.state.set_true_hand(0, 0, darkness_id)
    runner.state.set_true_hand(0, 1, doll_id)

    runner.step(ActionType.ACTION_SELECT_HAND_0)  # 闇
    runner.step(ActionType.ACTION_SELECT_HAND_1)  # ぬいぐるみを追加

    # ターゲット指定が合法になること
    legal_actions = godfield_core.get_legal_actions(runner.state)
    assert legal_actions[ActionType.ACTION_TARGET_OPP] is True

    # ターゲットして確定
    runner.step(ActionType.ACTION_TARGET_OPP)
    assert runner.state.get_mp(0) == 2
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_MIRACLE_DEFENSE


def test_miracle_and_spiritual_socks_stacking():
    """
    検証内容: 奇跡 ＋ 精霊の足袋の重ねがけ処理。
    - 奇跡「＜火の玉＞」に「精霊の足袋」を重ねて攻撃を決定した際、武器攻撃フェイズ（PHASE_DEFENSE）ではなく、奇跡防御フェイズ（PHASE_MIRACLE_DEFENSE）へと遷移することを確認します。
    - 消費MPが 0 になり、MPが減少していないことを確認します。
    """
    runner = SimulationRunner()
    fireball_id = find_card_by_name("＜火の玉＞")
    socks_id = find_card_by_name("精霊の足袋")

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.set_status(0, hp=40, mp=10)

    runner.state.set_true_hand(0, 0, fireball_id)
    runner.state.set_true_hand(0, 1, socks_id)

    runner.step(ActionType.ACTION_SELECT_HAND_0)  # 火の玉
    runner.step(ActionType.ACTION_SELECT_HAND_1)  # 足袋
    runner.step(ActionType.ACTION_TARGET_OPP)

    # 奇跡防御フェイズへ移行していること
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_MIRACLE_DEFENSE
    # MPが消費されていないこと (10)
    assert runner.state.get_mp(0) == 10
