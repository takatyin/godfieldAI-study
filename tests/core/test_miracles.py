import godfield_core
from godfield_core import ActionType
from tests.core.test_utils import SimulationRunner, find_card_by_name, get_all_cards


def test_miracle_attack_basic():
    """
    検証内容: 単体対象の奇跡（攻撃）と、それに対する奇跡防御（PHASE_MIRACLE_DEFENSE）の基本フローテスト。
    - P0が「火の玉 (fireball)」などの単体奇跡を選択し、相手 (P1) を対象に攻撃を実行すること。
    - MPが正しく消費されること（例: 火の玉なら2MP）。
    - 攻撃実行後、ゲーム状態が奇跡防御フェーズ (PHASE_MIRACLE_DEFENSE) に移行し、被攻撃者 (P1) に攻守交代すること。
    - P1が防御を確定させた後、ダメージ計算が行われ、P1のHPが減少し、P1のターンに移行すること。
    """
    runner = SimulationRunner()

    miracle_attack_id = find_card_by_name("＜火の玉＞")  # MP2, ATK2

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.set_status(0, 40, 10)
    runner.set_status(1, 40, 10)

    runner.state.set_true_hand(0, 0, miracle_attack_id)

    # P0が奇跡を選択
    runner.step(action=ActionType.ACTION_SELECT_HAND_0)
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_MIRACLE_PLUS

    # 相手をターゲット
    runner.step(action=ActionType.ACTION_TARGET_OPP)

    # MPが消費され、奇跡防御フェーズに移行すること
    assert runner.state.get_mp(0) == 10 - 2
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_MIRACLE_DEFENSE
    assert runner.state.current_actor_id == 1

    # P1が防御を確定
    runner.step(action=ActionType.ACTION_CONFIRM)

    assert runner.state.get_hp(1) == 40 - 2
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_MAIN
    assert runner.state.current_actor_id == 1


def test_miracle_absorption():
    """
    検証内容: 「吸収 (absorption)」などのHP吸収系奇跡のテスト。
    - P0が自身または相手に「吸収」を使用した際、対象の残りHPに関係なく「本来与えるはずだったダメージ量（攻撃力分）」が回復すること。
    - 例えば、HPが残り5の対象にATK10の吸収を撃った場合、対象のHPは0でストップし、撃った側は+10回復すること。
    """
    runner = SimulationRunner()

    absorption_id = find_card_by_name("＜吸収＞")  # MP10, ATK10, HP吸収

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_hp(0, 5)  # 吸収を撃つ側（HP5から15に回復する想定）
    runner.state.set_mp(0, 20)

    runner.state.set_true_hand(0, 0, absorption_id)

    runner.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner.step(action=ActionType.ACTION_TARGET_SELF)  # 自分自身に吸収を撃つ

    # 吸収ダメージ10を受けるが即座に10回復するため、HPは5 - 10(0でストップ) + 10 = 10 になる
    assert runner.state.get_hp(0) == 10
    assert runner.state.get_mp(0) == 10
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_MAIN
    assert runner.state.current_actor_id == 1


def test_miracle_deployment_retains_card():
    """
    検証内容: 展開型奇跡「＜オーラ＞」使用時の手札維持テスト。
    - 奇跡「＜オーラ＞」を使用（展開）して戦闘を解決した際、カードが手札から消滅せず、使用したスロット（スロット1）に展開フラグ（is_deployed = True）および公開フラグ（is_known_to_opp = True）がオンの状態で留まることを確認します。
    """
    runner = SimulationRunner()
    aura_id = find_card_by_name("＜オーラ＞")
    weapon_id = find_card_by_name("パンチ")

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_mp(0, 20)

    runner.state.set_true_hand(0, 0, weapon_id)
    runner.state.set_true_hand(0, 1, aura_id)

    runner.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner.step(action=ActionType.ACTION_SELECT_HAND_1)
    runner.step(action=ActionType.ACTION_TARGET_OPP)
    runner.step(action=ActionType.ACTION_CONFIRM)

    # オーラはスロット1に展開されたまま残る
    assert runner.state.get_is_deployed(0, 1) == True
    assert runner.state.get_true_hand(0, 1) == aura_id


def test_miracle_deployment_triggers_draw():
    """
    検証内容: 展開型奇跡と通常消費武器の混成使用時のドロー補充テスト。
    - 武器とオーラを同時に使用し、ターンが移行した際、消費された武器のスロット0および追加のカード補充により、手札スロット0とスロット2の空き枠に新規カードが正しくドローされることを確認します。
    """
    runner = SimulationRunner()
    aura_id = find_card_by_name("＜オーラ＞")
    weapon_id = find_card_by_name("パンチ")

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_mp(0, 20)

    # スロット2以降は空にしておく
    for i in range(2, 18):
        runner.state.set_true_hand(0, i, godfield_core.CARD_EMPTY)

    runner.state.set_true_hand(0, 0, weapon_id)
    runner.state.set_true_hand(0, 1, aura_id)

    runner.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner.step(action=ActionType.ACTION_SELECT_HAND_1)
    runner.step(action=ActionType.ACTION_TARGET_OPP)
    runner.step(action=ActionType.ACTION_CONFIRM)

    # 武器は消費されたためスロット0には新たなカードがドローされている
    assert runner.state.get_is_deployed(0, 0) == False
    assert runner.state.get_true_hand(0, 0) != godfield_core.CARD_EMPTY
    # オーラの分、スロット2にもさらにドローされている
    assert runner.state.get_true_hand(0, 2) != godfield_core.CARD_EMPTY


def test_miracle_aura_doubling():
    """
    検証内容: 「オーラ (aura)」による攻撃力2倍化のテスト。
    - 武器のATKに対して、追加でオーラを使用した場合に最終的な攻撃力(pending_attack_power)が2倍になること。
    - 複数重ねた場合の処理（例: ATK5 * 2 = 10）が正しく適用されていること。
    - 属性が無属性になっていること
    """
    runner = SimulationRunner()

    weapon_id = find_card_by_name("ブレイズブレイド")  # 火ATK5
    aura_id = find_card_by_name("＜オーラ＞")

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_mp(0, 20)

    runner.state.set_true_hand(0, 0, weapon_id)
    runner.state.set_true_hand(0, 1, aura_id)

    runner.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner.step(action=ActionType.ACTION_SELECT_HAND_1)
    runner.step(action=ActionType.ACTION_TARGET_OPP)

    # ATK5 -> オーラで2倍 -> ATK10 になっているか
    cards = get_all_cards()
    card_info = next(c for c in cards if c["id"] == weapon_id)
    expected_atk = card_info.get("attack_power", 0) * 2
    assert runner.state.pending_attack_power == expected_atk
    assert runner.state.pending_attack_element == godfield_core.ELEM_NONE


def test_miracle_status_ailment_application():
    """
    検証内容: 対象を状態異常（病・災い）にする奇跡のテスト。
    - 「風 (wind)」などの奇跡を相手に使用した際、相手が正しく「風邪」状態になること。
    - ダメージ0の奇跡であっても、PHASE_MIRACLE_DEFENSEへ移行し、相手が「乱気流」等で防御する機会が与えられること。
    """
    runner = SimulationRunner()

    wind_id = find_card_by_name("＜風＞")

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_mp(0, 20)
    runner.state.set_true_hand(0, 0, wind_id)

    runner.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner.step(action=ActionType.ACTION_TARGET_OPP)

    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_MIRACLE_DEFENSE
    assert runner.state.current_actor_id == 1

    runner.step(action=ActionType.ACTION_CONFIRM)

    # 風邪状態になっているか (sickness == SICKNESS_COLD)
    assert runner.state.get_sickness(1) == godfield_core.SicknessType.SICKNESS_COLD


def test_miracle_cure_sickness_fever():
    """
    検証内容: 音色による熱病の治癒テスト。
    - 自身が「熱病（SICKNESS_FEVER）」である状態で、自分自身を対象に奇跡「＜音色＞」を使用した際、熱病状態が「SICKNESS_NONE」へと完全に治癒されることを確認します。
    """
    runner = SimulationRunner()
    tone_id = find_card_by_name("＜音色＞")

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_mp(0, 20)
    runner.state.set_sickness(0, godfield_core.SicknessType.SICKNESS_FEVER)
    runner.state.set_true_hand(0, 0, tone_id)

    runner.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner.step(action=ActionType.ACTION_TARGET_SELF)

    # 治癒解決
    assert runner.state.get_sickness(0) == godfield_core.SicknessType.SICKNESS_NONE


def test_miracle_cure_curse_flash():
    """
    検証内容: 音色による閃光の災い（Curse）治癒テスト。
    - 自身が「閃光の災い（CURSE_FLASH）」である状態で、自分自身を対象に奇跡「＜音色＞」を使用した際、閃光の災いが False（治癒）になることを確認します。
    """
    runner = SimulationRunner()
    tone_id = find_card_by_name("＜音色＞")

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_mp(0, 20)
    runner.state.set_curses(0, godfield_core.CurseType.CURSE_FLASH, True)
    runner.state.set_true_hand(0, 0, tone_id)

    runner.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner.step(action=ActionType.ACTION_TARGET_SELF)

    # 治癒解決
    assert runner.state.get_curses(0, godfield_core.CurseType.CURSE_FLASH) == False


def test_miracle_multiple_uses_per_turn():
    """
    検証内容: 一度展開された奇跡の同ターン中の複数回使用禁止ルールのテスト。
    - 一度使用されて盤面に展開された(is_deployed=True)奇跡カードは、次の自ターンにならないと再使用できない。
    - 同ターン中に同じカードを2回選択しようとした際、非合法手(Illegal Action)として扱われること。
    """
    runner = SimulationRunner()

    cascade_id = find_card_by_name("＜滝＞")

    runner.state.current_phase = godfield_core.GamePhase.PHASE_ATTACK_PLUS
    runner.state.current_actor_id = 0
    runner.state.set_mp(0, 40)

    # 既に展開済みで、このターン中に使用したフラグを立てる
    runner.state.set_true_hand(0, 0, cascade_id)
    runner.state.set_is_deployed(0, 0, True)
    runner.state.set_miracle_used_this_turn(0, 0, True)

    # 合法手を取得し、既にこのターン使用した奇跡は選択できないことを確認
    legal_actions = godfield_core.get_legal_actions(runner.state)
    assert legal_actions[ActionType.ACTION_SELECT_HAND_0.value] == False


def test_unstable_accuracy_cannot_target_self():
    """
    検証内容: 命中不安の奇跡・武器（命中率 < 100）は自分自身を対象に取れないルール。
    - 命中率75%の「煙」などを選択した場合、PHASE_MIRACLE_PLUS 時に ACTION_TARGET_SELF が非合法手になること。
    - 命中率100%のカードを選択した場合は ACTION_TARGET_SELF が合法手になること。
    """
    runner = SimulationRunner()

    unstable_miracle_id = find_card_by_name("＜煙＞")

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_mp(0, 20)

    # 命中不安の奇跡を使用
    runner.state.set_true_hand(0, 0, unstable_miracle_id)
    runner.step(action=ActionType.ACTION_SELECT_HAND_0)

    legal_actions = godfield_core.get_legal_actions(runner.state)

    assert legal_actions[ActionType.ACTION_TARGET_SELF.value] == False
    assert legal_actions[ActionType.ACTION_TARGET_OPP.value] == True


def test_miracle_deployment_limit_six():
    """
    検証内容: 奇跡の最大展開数制限。
    - 6つのスロットに既に奇跡が展開されている状態で、現在展開されている奇跡の総数が 6 個であることを確認します。
    """
    runner = SimulationRunner()
    fireball_id = find_card_by_name("＜火の玉＞")

    # 6つのスロットに奇跡を展開
    for i in range(6):
        runner.state.set_true_hand(0, i, fireball_id)
        runner.state.set_is_deployed(0, i, True)

    deployed_count = sum(1 for i in range(18) if runner.state.get_is_deployed(0, i))
    assert deployed_count == 6


def test_miracle_deployment_limit_fifo_eviction():
    """
    検証内容: 奇跡展開オーバー時のFIFO（押し出し）ルールテスト。
    - 既に 6 つ展開されている状態で、7 つ目の奇跡をスロット6に新しく展開した際、最も古いスロット0の奇跡の展開フラグが False になり、かつ手札から完全に消滅（CARD_EMPTY）することを確認します。
    - 総展開数が 6 個のままで維持されることを確認します。
    """
    runner = SimulationRunner()
    fireball_id = find_card_by_name("＜火の玉＞")

    # 6つ展開
    for i in range(6):
        runner.state.set_true_hand(0, i, fireball_id)
        runner.state.set_is_deployed(0, i, True)

    # 7つ目の奇跡を展開
    runner.state.set_true_hand(0, 6, fireball_id)
    runner.state.set_is_deployed(0, 6, True)

    # 1. 総数は6のまま維持
    deployed_count_after = sum(1 for i in range(18) if runner.state.get_is_deployed(0, i))
    assert deployed_count_after == 6

    # 2. スロット0（最も古い奇跡）が消滅
    assert runner.state.get_is_deployed(0, 0) == False
    assert runner.state.get_true_hand(0, 0) == godfield_core.CARD_EMPTY

    # 3. スロット6（新しい奇跡）が展開済み
    assert runner.state.get_is_deployed(0, 6) == True


def test_weapon_and_miracle_stacking():
    """
    検証内容: 武器 + 奇跡の重ねがけは「武器攻撃」として扱われ、PHASE_DEFENSEへ遷移する。
    """
    runner = SimulationRunner()
    punch_id = find_card_by_name("パンチ")
    fireball_id = find_card_by_name("＜火の玉＞")

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.set_status(0, hp=40, mp=10)  # 十分なMPを付与

    runner.state.set_true_hand(0, 0, punch_id)
    runner.state.set_true_hand(0, 1, fireball_id)

    # 1. 武器 (パンチ) を出す -> PHASE_ATTACK_PLUSへ
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_ATTACK_PLUS

    # 2. 火の玉を追加で出す (TIMING_ATK_PLUS)
    runner.step(ActionType.ACTION_SELECT_HAND_1)

    # 3. 相手を対象に攻撃決定 -> PHASE_DEFENSE (武器攻撃の守り) へ遷移するはず
    runner.step(ActionType.ACTION_TARGET_OPP)
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE


def test_miracle_and_miracle_stacking_is_illegal():
    """
    検証内容: 奇跡を1枚目に使用した場合、追加できるのは精霊系（MP0化）のみ。
    火の玉 ＋ 火の玉、火の玉 ＋ プラス武器、火の玉 ＋ 他の奇跡などはすべて非合法手となることを確認する。
    """
    runner = SimulationRunner()
    fireball_id = find_card_by_name("＜火の玉＞")
    blowgun_id = find_card_by_name("吹き矢")  # プラス武器 (TIMING_ATK_PLUS)
    ice_id = find_card_by_name("＜氷＞")  # 通常奇跡
    doll_id = find_card_by_name("精霊のぬいぐるみ")

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.set_status(0, hp=40, mp=10)  # 十分なMPを付与

    runner.state.set_true_hand(0, 0, fireball_id)
    runner.state.set_true_hand(0, 1, fireball_id)
    runner.state.set_true_hand(0, 2, blowgun_id)
    runner.state.set_true_hand(0, 3, ice_id)
    runner.state.set_true_hand(0, 4, doll_id)

    # 1. 火の玉を出す -> PHASE_MIRACLE_PLUSへ
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_MIRACLE_PLUS

    # 2. 重ねがけ可能なカードの検証
    legal_actions = godfield_core.get_legal_actions(runner.state)

    # 火の玉（2枚目）は非合法
    assert legal_actions[ActionType.ACTION_SELECT_HAND_1] is False
    # プラス武器（吹き矢）は非合法
    assert legal_actions[ActionType.ACTION_SELECT_HAND_2] is False
    # 通常奇跡（氷）は非合法
    assert legal_actions[ActionType.ACTION_SELECT_HAND_3] is False
    # 精霊系（ぬいぐるみ）は合法
    assert legal_actions[ActionType.ACTION_SELECT_HAND_4] is True
