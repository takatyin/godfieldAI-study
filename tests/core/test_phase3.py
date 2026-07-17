import godfield_core
from godfield_core import ActionType

from .test_utils import SimulationRunner, find_card_by_name, get_all_cards


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


def test_miracle_deployment_and_draw():
    """
    検証内容: 「オーラ (aura)」などの展開型奇跡のテストとドロー処理。
    - 奇跡を使用すると、手札の同じスロットに留まり（is_deployed = true, is_known_to_opp = true）、消費されないこと。
    - 手札の空き枠の数だけ、使用したカード枚数分（今回は武器+オーラで2枚）ターン終了時（あるいは使用直後）にドローが行われること。
    - 手札が一杯であればドローが行われないこと。
    """
    runner = SimulationRunner()

    aura_id = find_card_by_name("＜オーラ＞")
    weapon_id = find_card_by_name("パンチ")

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_mp(0, 20)

    runner.state.set_true_hand(0, 0, weapon_id)
    runner.state.set_true_hand(0, 1, aura_id)

    # メイン武器を選択
    runner.step(action=ActionType.ACTION_SELECT_HAND_0)
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_ATTACK_PLUS

    # オーラを追加選択
    runner.step(action=ActionType.ACTION_SELECT_HAND_1)

    # 攻撃確定
    runner.step(action=ActionType.ACTION_TARGET_OPP)

    # 相手が防御確定
    runner.step(action=ActionType.ACTION_CONFIRM)

    # ターンが移行
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_MAIN
    assert runner.state.current_actor_id == 1

    # オーラはスロット1に展開されたまま残る
    assert runner.state.get_is_deployed(0, 1) == True
    assert runner.state.get_true_hand(0, 1) == aura_id

    # 武器は消費されたためスロット0には新たなカードがドローされているはず
    assert runner.state.get_is_deployed(0, 0) == False
    assert runner.state.get_true_hand(0, 0) != godfield_core.CARD_EMPTY
    # オーラの分、さらにドローされているはず
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
    # プレースホルダーの武器の実際のATKに合わせて期待値を計算
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


def test_miracle_status_ailment_cure():
    """
    検証内容: 対象の状態異常を回復する奇跡のテスト。
    - 「音色 (tone)」などの奇跡を使用した際、対象の特定の状態異常（風邪、熱病、霧、閃光）がクリアされること。
    - 自分自身を対象に「音色」を使用し、状態異常が回復してターンが終了すること。
    """
    runner = SimulationRunner()

    tone_id = find_card_by_name("＜音色＞")

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_mp(0, 20)

    # 事前に状態異常を付与しておく
    runner.state.set_sickness(0, godfield_core.SicknessType.SICKNESS_FEVER)
    runner.state.set_curses(0, godfield_core.CurseType.CURSE_FLASH, True)

    runner.state.set_true_hand(0, 0, tone_id)

    runner.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner.step(action=ActionType.ACTION_TARGET_SELF)

    # TODO: 状態異常回復が正しく機能し、自身の状態異常がリセットされることを期待するアサーション
    # 自己対象回復はPHASE_MIRACLE_DEFENSEを経由せず即時適用される
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_MAIN
    assert runner.state.current_actor_id == 1

    # 状態異常が回復しているか
    assert runner.state.get_sickness(0) == godfield_core.SicknessType.SICKNESS_NONE
    assert runner.state.get_curses(0, godfield_core.CurseType.CURSE_FLASH) == False


# def test_miracle_defense_bounce():
#     """
#     検証内容: 奇跡を反射する防具・奇跡（「乱気流 (turbulence)」「スーパーミラー」等）のテスト。
#     - P0が奇跡攻撃を行い、P1が「乱気流」を使用して防御確定した場合。
#     - 反射により、効果（ダメージや状態異常）が本来の攻撃者であるP0に跳ね返ること。
#     - ※注意: 現在のMVP実装では跳ね返しが相手に直接適用されるか、実装未完の場合はスキップされる可能性があります。
#       このテストは将来的な実装の網羅性を担保するためのスケルトンです。
#     """
#     runner = SimulationRunner()

#     # TODO: 攻撃奇跡と反射奇跡（防具扱いの場合あり）のプレースホルダー。実際のカード名に変更してください。
#     fireball_id = find_card_by_name("__PLACEHOLDER_MIRACLE_ATTACK__")
#     turbulence_id = find_card_by_name("__PLACEHOLDER_MIRACLE_BOUNCE__")

#     runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
#     runner.state.current_actor_id = 0
#     runner.state.set_mp(0, 20)
#     runner.state.set_mp(1, 20)
#     runner.state.set_hp(0, 40)
#     runner.state.set_hp(1, 40)

#     runner.state.set_true_hand(0, 0, fireball_id)
#     runner.state.set_true_hand(1, 0, turbulence_id)

#     runner.step(action=ActionType.ACTION_SELECT_HAND_0)
#     runner.step(action=ActionType.ACTION_TARGET_OPP)

#     # P1の防御ターン
#     assert runner.state.current_phase == godfield_core.GamePhase.PHASE_MIRACLE_DEFENSE
#     runner.step(action=ActionType.ACTION_SELECT_HAND_0)  # 乱気流を選択
#     runner.step(action=ActionType.ACTION_CONFIRM)

#     # 反射により、本来の攻撃者であるP0がダメージを受け、防御側のP1は無傷になることを期待するアサーション
#     # TODO: 反射ロジックが実装された際、以下の結果になるようにしてください
#     assert runner.state.get_hp(0) < 40
#     assert runner.state.get_hp(1) == 40


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

    # TODO: C++側で命中率<100の場合にターゲット自分を禁止するロジックが実装されているかを期待するアサーション
    assert legal_actions[ActionType.ACTION_TARGET_SELF.value] == False
    assert legal_actions[ActionType.ACTION_TARGET_OPP.value] == True


def test_miracle_deployment_limit_fifo():
    """
    検証内容: 奇跡の展開数は最大6つであり、それ以上展開しようとすると最も古いものから上書き（FIFO）で消滅する仕様のテスト。
    """
    runner = SimulationRunner()
    
    # 奇跡のIDを取得
    fireball_id = find_card_by_name("＜火の玉＞")
    
    # 6つのスロットに奇跡を展開する（0から5）
    for i in range(6):
        runner.state.set_true_hand(0, i, fireball_id)
        runner.state.set_is_deployed(0, i, True)
        
    # 現在展開されている奇跡が6つあることを確認
    deployed_count = sum(1 for i in range(18) if runner.state.get_is_deployed(0, i))
    assert deployed_count == 6
    
    # 7つ目の奇跡を展開する（スロット6）
    runner.state.set_true_hand(0, 6, fireball_id)
    runner.state.set_is_deployed(0, 6, True)
    
    # 結果確認:
    # 1. 総展開数は6個のまま維持されていること
    deployed_count_after = sum(1 for i in range(18) if runner.state.get_is_deployed(0, i))
    assert deployed_count_after == 6
    
    # 2. 最も古かったスロット0の奇跡の展開状態が解除され、さらに手札からも消滅（CARD_EMPTY）していること
    assert runner.state.get_is_deployed(0, 0) == False
    assert runner.state.get_true_hand(0, 0) == godfield_core.CARD_EMPTY
    
    # 3. 新しく展開したスロット6の奇跡は展開されていること
    assert runner.state.get_is_deployed(0, 6) == True
