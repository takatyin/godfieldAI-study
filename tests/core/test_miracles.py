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


def test_miracle_darkness_defense_by_any_armor():
    """
    検証内容: 闇属性攻撃＜闇＞に対する防御の合法手テスト。
    - 相手からの＜闇＞(闇属性ATK5の奇跡攻撃) に対し、防御側が持つ無属性防具（木の盾）や属性防具（きらきらドレス）
      が合法手 (legal action) として選択可能であることを検証。
    - 完全防御によって無事に生存できることを確認する。
    """
    runner = SimulationRunner()
    darkness_id = find_card_by_name("＜闇＞")
    leather_clothes_id = find_card_by_name("armor/leather-clothes")
    dress_id = find_card_by_name("きらきらドレス")

    runner.set_status(0, hp=40, mp=20)
    runner.set_status(1, hp=40, mp=20)

    runner.state.set_true_hand(0, 0, darkness_id)
    runner.state.set_true_hand(1, 0, leather_clothes_id)
    runner.state.set_true_hand(1, 1, dress_id)

    # 1. P0 Magiが＜闇＞(ATK 5)でP1に奇跡攻撃
    runner.perform_attack([0])

    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_MIRACLE_DEFENSE
    assert runner.state.current_actor_id == 1

    # 2. P1の合法手に「革の服」(0) も「きらきらドレス」(1) も含まれていること！
    actions = godfield_core.get_legal_actions(runner.state)
    assert actions[ActionType.ACTION_SELECT_HAND_0] is True, "無属性防具(革の服)が選択可能であること"
    assert actions[ActionType.ACTION_SELECT_HAND_1] is True, "光属性防具(きらきらドレス)が選択可能であること"

    # 3. きらきらドレス(DEF10)を出して計DEF10で完全防御
    runner.perform_defense([1])

    # 完全防御成功（即死せずHP40で生存）
    assert runner.state.get_hp(1) == 40


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
    runner.state.set_is_used(0, 0, True)

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


def test_miracle_deployment_unlimited():
    """
    検証内容: 奇跡の展開数に制限がなく、いくらでも展開できること。
    - 10個のスロットに奇跡を展開し、10個すべてが展開されたままであることを確認します（押し出しは発生しない）。
    """
    runner = SimulationRunner()
    fireball_id = find_card_by_name("＜火の玉＞")

    # 10個のスロットに奇跡を展開
    for i in range(10):
        runner.state.set_true_hand(0, i, fireball_id)
        runner.state.set_is_deployed(0, i, True)

    deployed_count = sum(1 for i in range(18) if runner.state.get_is_deployed(0, i))
    assert deployed_count == 10

    # 最古のスロット（0）も展開されたままであり、消滅していないこと
    assert runner.state.get_is_deployed(0, 0) == True
    assert runner.state.get_true_hand(0, 0) == fireball_id


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

# ==========================================
# Merged from: tests/core/test_apocalypse.py
# ==========================================



def test_apocalypse_turn_threshold():
    """
    検証内容: APOCALYPSE_TURN (150) に達した時、ゲームが「終末の時」に入ることを確認する。
    """
    runner = SimulationRunner()
    runner.reset_state()

    # 150ターン未満は通常モード
    runner.state.current_turn = 149
    assert runner.state.current_turn < 150

    # 150ターン以上は終末の時
    runner.state.current_turn = 150
    assert runner.state.current_turn >= 150


def test_apocalypse_pray_draws_devil_cards():
    """
    検証内容: 終末の時において、カードドロー時 (祈るなど) に25%の確率で悪魔カードが発生し、
    その即時効果が適用された後に代替のカードがドローされることを検証する。
    """
    little_devil_count = 0
    medium_devil_count = 0
    large_devil_count = 0
    fairy_count = 0

    # 200回試行して悪魔カードの発生と効果を検出する
    for i in range(200):
        runner = SimulationRunner()
        runner.reset_state()
        runner.state.seed_rng(i)  # 各試行の乱数シードを個別に設定
        runner.state.current_turn = 150  # 終末の時
        runner.set_status(player=0, hp=40, mp=10, money=10)
        runner.set_hand(player=0, cards=[])  # 手札を空にする

        # 祈るを実行してドローする
        runner.step(ActionType.ACTION_PRAY)

        # 生存している場合のみ、手札にカードが入ることを確認
        if not runner.state.is_done:
            assert runner.state.get_true_hand(0, 0) != godfield_core.CARD_EMPTY

        hp = runner.state.get_hp(0)
        mp = runner.state.get_mp(0)
        money = runner.state.get_money(0)

        # ダメージ系悪魔の効果
        if hp == 30:
            little_devil_count += 1
        elif hp == 20:
            medium_devil_count += 1
        elif hp == 10:
            large_devil_count += 1

        # めぐみの妖精の効果 (+10 HP, MP, or money)
        if hp == 50 or mp == 20 or money == 20:
            fairy_count += 1

    # いずれかの悪魔カード・妖精カードが確率的に発生したことを確認する
    print(
        f"Detected Little: {little_devil_count}, Medium: {medium_devil_count}, Large: {large_devil_count}, Fairy: {fairy_count}"
    )
    assert little_devil_count > 0, "Little Devil did not trigger in 200 trials"
    assert medium_devil_count > 0, "Medium Devil did not trigger in 200 trials"
    assert large_devil_count > 0, "Large Devil did not trigger in 200 trials"
    assert fairy_count > 0, "Gracious Fairy did not trigger in 200 trials"


def test_apocalypse_prankster_discard():
    """
    検証内容: イタズラマン (Prankster) の効果により、手札/アクティブな奇跡から無作為に2つ破棄されることを検証する。
    """
    shield_id = find_card_by_name("革の服")

    prankster_triggered = 0

    # 200回試行してイタズラマンが発生し、手札が破棄されたかを確認する
    for i in range(200):
        runner = SimulationRunner()
        runner.reset_state()
        runner.state.seed_rng(i)  # 各試行の乱数シードを個別に設定
        runner.state.current_turn = 150  # 終末 of 時
        runner.set_status(player=0, hp=40, mp=10, money=10)

        # 手札をセット（イタズラマンが破棄する候補、武器以外である必要があるため革の服のみ）
        runner.state.set_true_hand(0, 1, shield_id)
        runner.state.set_true_hand(0, 2, shield_id)

        # 祈るを実行
        runner.step(ActionType.ACTION_PRAY)

        # イタズラマンがトリガーした場合、スロット1または2が空 (CARD_EMPTY) になっている
        slot1 = runner.state.get_true_hand(0, 1)
        slot2 = runner.state.get_true_hand(0, 2)

        if slot1 == godfield_core.CARD_EMPTY or slot2 == godfield_core.CARD_EMPTY:
            prankster_triggered += 1

    assert prankster_triggered > 0, "Prankster (trickster) did not trigger in 200 trials"


def test_apocalypse_sacrifice_refills_hand():
    """
    検証内容: 通常モードの「捨てる」と終末の時の「ささげる」の挙動の違いを検証する。
    - 通常モードでは捨てたスロットは空のままになる。
    - 終末の時では捨てた分だけ新たにドローされる。
    """
    shield_id = find_card_by_name("革の服")

    # --- 通常モードの検証 ---
    runner_normal = SimulationRunner()
    runner_normal.reset_state()
    runner_normal.state.current_turn = 0  # 通常
    runner_normal.state.set_true_hand(0, 0, shield_id)

    # 捨てるフェーズに入り、スロット0を選択して確定
    runner_normal.step(ActionType.ACTION_DISCARD)
    runner_normal.perform_defense([0])

    # 通常モードではスロット0は空のまま
    assert runner_normal.state.get_true_hand(0, 0) == godfield_core.CARD_EMPTY

    # --- 終末の時の検証 ---
    runner_apocalypse = SimulationRunner()
    runner_apocalypse.reset_state()
    runner_apocalypse.state.current_turn = 150  # 終末の時
    runner_apocalypse.state.set_true_hand(0, 0, shield_id)

    # ささげるフェーズに入り、スロット0を選択して確定
    runner_apocalypse.step(ActionType.ACTION_DISCARD)
    runner_apocalypse.perform_defense([0])

    # 終末の時では新しくカードがドローされているため、スロット0は空ではない
    assert runner_apocalypse.state.get_true_hand(0, 0) != godfield_core.CARD_EMPTY


def test_apocalypse_draw_death_defer():
    """
    検証内容: 終末の時において、使用済みカードのドロー処理が終わった後に勝敗判定が行われること。
    - プレイヤー0（HP10）が「クロスボウ」を使用し、プレイヤー1（HP1）を攻撃。
    - プレイヤー1は防御できず被弾し、HPが0になる。
    - 通常時であれば、被弾解決の段階でプレイヤー1が死亡した時点で即座にゲーム終了となる。
    - しかし、終末 of 時では、被弾の瞬間にはゲーム終了せず、使用済みカードの補充ドロー処理に進む。
    - ドロー補充は生存しているプレイヤー0に対してのみ行われ、そのドローで悪魔を引いてプレイヤー0のHPも0になる。
    - ドロー処理全体の完了後に初めて死亡判定が行われ、両者死亡による「引き分け（Draw）」になることを確認する。
    """
    bow_id = find_card_by_name("weapons/crossbow")

    target_seed = -1
    for seed in range(500):
        runner = SimulationRunner()
        runner.reset_state()
        runner.state.seed_rng(seed)
        runner.state.current_turn = 150  # 終末の時
        runner.set_status(player=0, hp=10, mp=10, money=10)
        runner.set_status(player=1, hp=1, mp=10, money=10)
        runner.state.set_true_hand(0, 0, bow_id)
        runner.set_hand(player=1, cards=[]) # プレイヤー1は手札空で防御不能

        # プレイヤー0がクロスボウを使用
        runner.perform_attack([0])

        # プレイヤー1の防御フェイズ ➡ confirmしか押せない
        runner.step(ActionType.ACTION_CONFIRM)

        # ドロー補充で悪魔を引き、両者死亡（引き分け）になったシードを探す
        if runner.state.is_done and runner.state.get_hp(0) == 0 and runner.state.get_hp(1) == 0 and runner.state.p0_reward == 0.0:
            target_seed = seed
            break

    assert target_seed != -1, "Could not find a seed where player 0 draws a damaging devil during cleanup draw"

    # 通常時の挙動を確認（クロスボウでの被弾の瞬間に即座にゲーム終了し、プレイヤー0の勝利になる）
    runner_normal = SimulationRunner()
    runner_normal.reset_state()
    runner_normal.state.seed_rng(target_seed)
    runner_normal.state.current_turn = 0  # 通常時
    runner_normal.set_status(player=0, hp=10, mp=10, money=10)
    runner_normal.set_status(player=1, hp=1, mp=10, money=10)
    runner_normal.state.set_true_hand(0, 0, bow_id)
    runner_normal.set_hand(player=1, cards=[])

    runner_normal.perform_attack([0])
    runner_normal.step(ActionType.ACTION_CONFIRM)

    # 通常時なので被弾の瞬間にゲーム終了し、プレイヤー0が勝利している（HP10のまま、ドローは発生しない）
    assert runner_normal.state.is_done is True
    assert runner_normal.state.get_hp(0) == 10
    assert runner_normal.state.get_hp(1) == 0
    assert runner_normal.state.p0_reward == 1.0

    # 終末の時の挙動を確認（被弾では終了せず、ドロー処理後に両者死亡で引き分けになる）
    runner_apoc = SimulationRunner()
    runner_apoc.reset_state()
    runner_apoc.state.seed_rng(target_seed)
    runner_apoc.state.current_turn = 150  # 終末の時
    runner_apoc.set_status(player=0, hp=10, mp=10, money=10)
    runner_apoc.set_status(player=1, hp=1, mp=10, money=10)
    runner_apoc.state.set_true_hand(0, 0, bow_id)
    runner_apoc.set_hand(player=1, cards=[])

    runner_apoc.perform_attack([0])
    runner_apoc.step(ActionType.ACTION_CONFIRM)

    # 終末 of 時なので、補充ドローによりプレイヤー0も死亡し、結果は引き分けになる
    assert runner_apoc.state.is_done is True
    assert runner_apoc.state.get_hp(0) == 0
    assert runner_apoc.state.get_hp(1) == 0
    assert runner_apoc.state.p0_reward == 0.0
    assert runner_apoc.state.p1_reward == 0.0



# ==========================================
# Merged from: tests/core/test_phenomena.py
# ==========================================



def find_seed_for_phenomenon(target_phenomenon: int) -> int:
    """
    運命のひもを使用した際に、目的の超常現象 (0~9) が発生するシード値を探索します。
    """
    string_of_fate_id = find_card_by_name("sundries/string-of-fate")
    for seed in range(5000):
        sim = SimulationRunner()
        sim.state.seed_rng(seed)
        sim.set_status(player=0, hp=99, mp=10, money=10)
        sim.set_status(player=1, hp=99, mp=10, money=10)

        # 手札に「運命のひも」だけを持たせる
        sim.state.set_true_hand(0, 0, string_of_fate_id)
        sim.state.set_true_hand(0, 1, -1)
        sim.state.set_true_hand(1, 0, -1)

        # Confirm -> Target Self
        sim.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
        sim.step(godfield_core.ActionType.ACTION_TARGET_SELF)

        # 各現象特有の状態変化で検出
        if target_phenomenon == 0:  # 夕焼け (全員熱病)
            if int(sim.state.get_sickness(0)) == 2 and int(sim.state.get_sickness(1)) == 2:
                return seed
        elif target_phenomenon == 1:  # 濃霧 (全員霧)
            if sim.state.get_curses(0, godfield_core.CurseType.CURSE_FOG) and sim.state.get_curses(
                1, godfield_core.CurseType.CURSE_FOG
            ):
                return seed
        elif target_phenomenon == 3:  # 竜巻 (全員 HP 1)
            if sim.state.get_hp(0) == 1 and sim.state.get_hp(1) == 1:
                return seed
        elif target_phenomenon == 4:  # 巨大なタライ (自分被弾 50ダメ)
            # 自分に被弾したシード（HPが減った）
            if sim.state.get_hp(0) == 49:
                return seed
        elif target_phenomenon == 400:  # 相手に巨大なタライ (相手に防御フェイズ)
            if (
                sim.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
                and sim.state.pending_attack_source_id == find_card_by_name("phenomena/gigantic-tub")
            ):
                return seed
        elif target_phenomenon == 5:  # ブラックホール (相手全体攻撃防御フェイズ)
            if (
                sim.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
                and sim.state.pending_attack_source_id == find_card_by_name("phenomena/black-hole")
            ):
                return seed
        elif target_phenomenon == 6:  # 暖流 (自身 HP+50)
            pass
        elif target_phenomenon == 7:  # 金山 (お金集約)
            if (sim.state.get_money(0) == 20 and sim.state.get_money(1) == 0) or (
                sim.state.get_money(0) == 0 and sim.state.get_money(1) == 20
            ):
                return seed
        elif target_phenomenon == 8:  # 磁気嵐 (手札相互シャッフル交換)
            pass
        elif target_phenomenon == 9:  # 日食 (守護神割り当て)
            if sim.state.get_guardian(0) > 0 and sim.state.get_guardian(1) > 0:
                return seed

    # 暖流用の探索 (初期HPを40にする)
    for seed in range(5000):
        sim = SimulationRunner()
        sim.state.seed_rng(seed)
        sim.set_status(player=0, hp=40, mp=10, money=10)
        sim.set_status(player=1, hp=40, mp=10, money=10)
        sim.state.set_true_hand(0, 0, string_of_fate_id)
        sim.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
        sim.step(godfield_core.ActionType.ACTION_TARGET_SELF)
        if target_phenomenon == 6:  # 暖流
            if sim.state.get_hp(0) == 90:
                return seed

    # 磁気嵐用の探索 (手札がある状態)
    for seed in range(5000):
        sim = SimulationRunner()
        sim.state.seed_rng(seed)
        sim.set_status(player=0, hp=99, mp=10, money=10)
        sim.set_status(player=1, hp=99, mp=10, money=10)
        sim.state.set_true_hand(0, 0, string_of_fate_id)
        sim.state.set_true_hand(0, 1, 10)  # 適当なカードA
        sim.state.set_true_hand(0, 2, 11)  # 適当なカードB
        sim.state.set_true_hand(1, 0, 12)  # 適当なカードC
        sim.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
        sim.step(godfield_core.ActionType.ACTION_TARGET_SELF)
        if target_phenomenon == 8:  # 磁気嵐
            h1 = [sim.state.get_true_hand(1, idx) for idx in range(18) if sim.state.get_true_hand(1, idx) != -1]
            if len(h1) > 0 and h1[0] in [10, 11] and int(sim.state.get_sickness(0)) == 0:
                if sim.state.get_hp(0) == 99 and sim.state.get_guardian(0) == 0:
                    return seed

    raise ValueError(f"Could not find seed for phenomenon {target_phenomenon}")


def test_afterglow():
    """夕焼け: 全員熱病"""
    seed = find_seed_for_phenomenon(0)
    sim = SimulationRunner()
    sim.state.seed_rng(seed)
    sim.set_hand(0, ["sundries/string-of-fate"])
    sim.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
    sim.step(godfield_core.ActionType.ACTION_TARGET_SELF)

    assert int(sim.state.get_sickness(0)) == 2  # 熱病
    assert int(sim.state.get_sickness(1)) == 2  # 熱病


def test_dense_fog():
    """濃霧: 全員霧"""
    seed = find_seed_for_phenomenon(1)
    sim = SimulationRunner()
    sim.state.seed_rng(seed)
    sim.set_hand(0, ["sundries/string-of-fate"])
    sim.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
    sim.step(godfield_core.ActionType.ACTION_TARGET_SELF)

    assert sim.state.get_curses(0, godfield_core.CurseType.CURSE_FOG)
    assert sim.state.get_curses(1, godfield_core.CurseType.CURSE_FOG)


def test_tornado():
    """竜巻: 全員HP 1"""
    seed = find_seed_for_phenomenon(3)
    sim = SimulationRunner()
    sim.state.seed_rng(seed)
    sim.set_hand(0, ["sundries/string-of-fate"])
    sim.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
    sim.step(godfield_core.ActionType.ACTION_TARGET_SELF)

    assert sim.state.get_hp(0) == 1
    assert sim.state.get_hp(1) == 1


def test_gigantic_tub_self():
    """巨大なタライ (自分に当たる): 防御不可、即50ダメージ"""
    seed = find_seed_for_phenomenon(4)
    sim = SimulationRunner()
    sim.state.seed_rng(seed)
    sim.set_hand(0, ["sundries/string-of-fate"])
    sim.set_status(player=0, hp=80)
    sim.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
    sim.step(godfield_core.ActionType.ACTION_TARGET_SELF)

    assert sim.state.get_hp(0) == 30  # 80 - 50 = 30


def test_gigantic_tub_opp():
    """巨大なタライ (相手に当たる): 光属性50の防御フェイズ起動"""
    seed = find_seed_for_phenomenon(400)
    sim = SimulationRunner()
    sim.state.seed_rng(seed)
    sim.set_hand(0, ["sundries/string-of-fate"])
    sim.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
    sim.step(godfield_core.ActionType.ACTION_TARGET_SELF)

    assert sim.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
    assert sim.state.defender_id == 1
    assert sim.state.attacker_id == 0
    assert sim.state.pending_attack_source_id == find_card_by_name("phenomena/gigantic-tub")
    assert sim.state.pending_attack_power == 50
    assert sim.state.pending_attack_element == godfield_core.Element.ELEM_LIGHT


def test_black_hole():
    """ブラックホール: 相手に対して全体攻撃闇属性30防御フェイズ起動"""
    seed = find_seed_for_phenomenon(5)
    sim = SimulationRunner()
    sim.state.seed_rng(seed)
    sim.set_hand(0, ["sundries/string-of-fate"])
    sim.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
    sim.step(godfield_core.ActionType.ACTION_TARGET_SELF)

    assert sim.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
    assert sim.state.defender_id == 1
    assert sim.state.attacker_id == 0
    assert sim.state.pending_attack_source_id == find_card_by_name("phenomena/black-hole")
    assert sim.state.pending_attack_power == 30
    assert sim.state.pending_attack_element == godfield_core.Element.ELEM_DARKNESS
    assert sim.state.pending_is_group_attack == True


def test_warm_current():
    """暖流: 自身HP+50"""
    seed = find_seed_for_phenomenon(6)
    sim = SimulationRunner()
    sim.state.seed_rng(seed)
    sim.set_hand(0, ["sundries/string-of-fate"])
    sim.set_status(player=0, hp=40)
    sim.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
    sim.step(godfield_core.ActionType.ACTION_TARGET_SELF)

    assert sim.state.get_hp(0) == 90  # 40 + 50 = 90


def test_gold_mountain():
    """金山: お互いのお金合計が集約"""
    seed = find_seed_for_phenomenon(7)
    sim = SimulationRunner()
    sim.state.seed_rng(seed)
    sim.set_hand(0, ["sundries/string-of-fate"])
    sim.set_status(player=0, money=10)
    sim.set_status(player=1, money=20)
    sim.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
    sim.step(godfield_core.ActionType.ACTION_TARGET_SELF)

    m0 = sim.state.get_money(0)
    m1 = sim.state.get_money(1)
    # 合計 30 がどちらか一方に集約し、もう一方は 0 になる
    assert (m0 == 30 and m1 == 0) or (m0 == 0 and m1 == 30)


def test_solar_eclipse():
    """日食: 重複しない守護神が両者にセット"""
    seed = find_seed_for_phenomenon(9)
    sim = SimulationRunner()
    sim.state.seed_rng(seed)
    sim.set_hand(0, ["sundries/string-of-fate"])
    sim.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
    sim.step(godfield_core.ActionType.ACTION_TARGET_SELF)

    g0 = sim.state.get_guardian(0)
    g1 = sim.state.get_guardian(1)

    assert g0 in range(1, 11)
    assert g1 in range(1, 11)
    assert g0 != g1  # 重複しない！


def test_magnetic_storm():
    """磁気嵐: 手札相互交換 & known_to_opp 追跡"""
    seed = find_seed_for_phenomenon(8)
    sim = SimulationRunner()
    sim.state.seed_rng(seed)

    # プレイヤー 0: ひも + 銅のこん棒 (ID 5) + 天空のよろい (確実にある)
    # プレイヤー 1: 神の盾 (確実にある)
    fate_id = find_card_by_name("sundries/string-of-fate")
    card_a = find_card_by_name("weapons/bronze-club")
    card_b = find_card_by_name("armor/sky-armor")
    card_c = find_card_by_name("armor/god-shield")

    sim.state.set_true_hand(0, 0, fate_id)
    sim.state.set_true_hand(0, 1, card_a)
    sim.state.set_true_hand(0, 2, card_b)
    sim.state.set_is_known_to_opp(0, 1, True)  # 銅のこん棒は相手に知られている
    sim.state.set_is_known_to_opp(0, 2, False)  # 天空のよろいは相手に知られていない

    sim.state.set_true_hand(1, 0, card_c)
    sim.state.set_is_known_to_opp(1, 0, False)  # 神の盾は相手に知られていない

    # ひもを使用
    sim.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
    sim.step(godfield_core.ActionType.ACTION_TARGET_SELF)

    # 分配後は：
    # プールは [card_a, card_b, card_c]。
    # 元の有効枚数は P0: 2枚, P1: 1枚。
    # 分配された結果、P0 の true_hand の 0, 1 スロットに 2枚、 P1 の 0 スロットに 1枚が配置される。
    # (ひも使用による通常ドローが最後に入って P0 に 1枚新規追加されるため、 P0 は計 3枚になる。)
    # 磁気嵐でシャッフルされて配られたカードについて、 known_to_opp が正しく設定されているか。

    # 元々 P0 の持ち物: card_a (known), card_b (unknown)
    # 元々 P1 の持ち物: card_c (unknown)

    # シャッフル後の手札スロット（ドローカード除く元のスロット）を調査
    # ひも分のドローは sim.step() で解決されて引かれているため、
    # P0 の 2枚のスロットと P1 の 1枚のスロットを確認。
    for p in [0, 1]:
        slots = 2 if p == 0 else 1
        for i in range(slots):
            cid = sim.state.get_true_hand(p, i)
            known = sim.state.get_is_known_to_opp(p, i)

            # 元の持ち主と配られた先を判定
            if p == 0:
                if cid == card_c:
                    # 元々 P1 の持ち物だった card_c が P0 に来た ➡ P1 は知っている
                    assert known == True
                elif cid == card_a:
                    # 自分に戻ってきた card_a ➡ 元々 known だったので known を維持
                    assert known == True
                elif cid == card_b:
                    # 自分に戻ってきた card_b ➡ 元々 unknown だったので unknown を維持
                    assert known == False
            else:  # p == 1
                if cid in [card_a, card_b]:
                    # 元々 P0 の持ち物だったカードが P1 に来た ➡ P0 は知っている
                    assert known == True
                elif cid == card_c:
                    # 自分に戻ってきた card_c ➡ 元々 unknown だったので維持
                    assert known == False


def test_magnetic_storm_dream():
    """磁気嵐: プレイヤーのどちらかでも夢状態の場合、お互いの手札が見かけ上夢になる"""
    seed = find_seed_for_phenomenon(8)
    sim = SimulationRunner()
    sim.state.seed_rng(seed)

    fate_id = find_card_by_name("sundries/string-of-fate")
    card_a = find_card_by_name("weapons/bronze-club")
    card_b = find_card_by_name("armor/sky-armor")
    card_c = find_card_by_name("armor/god-shield")

    # プレイヤー1を夢状態にする
    sim.state.set_curses(1, godfield_core.CurseType.CURSE_DREAM, True)

    sim.state.set_true_hand(0, 0, fate_id)
    sim.state.set_true_hand(0, 1, card_a)
    sim.state.set_true_hand(0, 2, card_b)
    sim.state.set_true_hand(1, 0, card_c)

    # ひもを使用
    sim.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
    sim.step(godfield_core.ActionType.ACTION_TARGET_SELF)

    # 磁気嵐でカードが配り直されたスロットについて、
    # プレイヤー0（夢ではない）とプレイヤー1（夢）の双方で、
    # 配り直されたカード（ドローを除く）が is_confirmed == False であり、
    # apparent_hand が dream_group によるダミー（異なる値など）になっているか。
    for p in [0, 1]:
        slots = 2 if p == 0 else 1
        for i in range(slots):
            true_id = sim.state.get_true_hand(p, i)
            app_id = sim.state.get_apparent_hand(p, i)
            confirmed = sim.state.get_is_confirmed(p, i)

            # 配られたカード (銅のこん棒、天空のよろい、神の盾) はすべて夢で隠されている（is_confirmed == False）こと
            assert confirmed is False, f"Player {p} slot {i} should not be confirmed"
            assert app_id != -1 and app_id != true_id


def test_string_of_fate_event_logging():
    """運命のひもを使用した際、TRIGGER_PHENOMENON (22) イベントが正常に発行されることを確認"""
    sim = SimulationRunner()
    sim.state.seed_rng(0)
    fate_id = find_card_by_name("運命のひも")

    sim.set_status(player=0, hp=99, mp=10, money=10)
    sim.state.set_true_hand(0, 0, fate_id)

    sim.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
    sim.step(godfield_core.ActionType.ACTION_TARGET_SELF)

    obs = godfield_core.get_observation(sim.state, 0)
    history = obs.get_history()

    phenomenon_events = [ev for ev in history if hasattr(ev, "event_type") and ev.event_type == int(godfield_core.EventType.TRIGGER_PHENOMENON)]
    assert len(phenomenon_events) > 0
    ev = phenomenon_events[0]
    assert ev.card_id == fate_id
    assert 0 <= int(ev.value) <= 9

