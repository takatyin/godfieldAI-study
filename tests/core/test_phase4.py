import godfield_core
from godfield_core import ActionType, CurseType, SicknessType

from .test_utils import SimulationRunner, find_card_by_name, find_card_by_type


def test_recovery_and_sickness_sundry():
    """
    検証内容: 回復と病気付与を伴う雑貨（天国草など）の解決。
    - 「天国草」を使用すると、対象のMPが20回復し、かつ対象が「天国病」になること。
    """
    runner = SimulationRunner()
    heaven_herb_id = find_card_by_name("天国草")

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_mp(1, 10)
    runner.state.set_sickness(1, SicknessType.SICKNESS_NONE)

    runner.state.set_true_hand(0, 0, heaven_herb_id)

    runner.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner.step(action=ActionType.ACTION_TARGET_OPP)
    runner.step(action=ActionType.ACTION_CONFIRM)

    # 相手(P1)のMPが30になり、天国病にかかっていること
    assert runner.state.get_mp(1) == 30
    assert runner.state.get_sickness(1) == SicknessType.SICKNESS_HEAVEN


def test_shells_curing_sickness_and_curses():
    """
    検証内容: 貝殻による状態異常と災いのクリア。
    - 「スマイルの貝がら」で風邪・熱病・霧・閃光が治療されること。
    - 「ハートの貝がら」で全ての状態異常が治療されること。
    """
    # 1. スマイルの貝がら
    runner1 = SimulationRunner()
    smile_shell_id = find_card_by_name("スマイルの貝がら")

    runner1.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner1.state.current_actor_id = 0
    runner1.state.set_sickness(0, SicknessType.SICKNESS_COLD)
    runner1.state.set_curses(0, CurseType.CURSE_FOG, True)
    runner1.state.set_curses(0, CurseType.CURSE_DREAM, True)  # スマイルでは治らない夢

    runner1.state.set_true_hand(0, 0, smile_shell_id)

    runner1.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner1.step(action=ActionType.ACTION_TARGET_SELF)

    assert runner1.state.get_sickness(0) == SicknessType.SICKNESS_NONE
    assert runner1.state.get_curses(0, CurseType.CURSE_FOG) == False
    assert runner1.state.get_curses(0, CurseType.CURSE_DREAM) == True  # 夢は残る

    # 2. ハートの貝がら
    runner2 = SimulationRunner()
    heart_shell_id = find_card_by_name("ハートの貝がら")

    runner2.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner2.state.current_actor_id = 0
    runner2.state.set_sickness(0, SicknessType.SICKNESS_HELL)
    for c in [
        CurseType.CURSE_FOG,
        CurseType.CURSE_FLASH,
        CurseType.CURSE_DARK_CLOUD,
        CurseType.CURSE_DREAM,
    ]:
        runner2.state.set_curses(0, c, True)

    runner2.state.set_true_hand(0, 0, heart_shell_id)

    runner2.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner2.step(action=ActionType.ACTION_TARGET_SELF)

    assert runner2.state.get_sickness(0) == SicknessType.SICKNESS_NONE
    for c in [
        CurseType.CURSE_FOG,
        CurseType.CURSE_FLASH,
        CurseType.CURSE_DARK_CLOUD,
        CurseType.CURSE_DREAM,
    ]:
        assert runner2.state.get_curses(0, c) == False


def test_guardian_pot_and_thump_tear():
    """
    検証内容: つぼによる守護神 Dwelling とドキドキ涙の確率的HP変化。
    - 「守護封印のつぼ」で守護神（ID 1..10）が宿ること。
    - 「ドキドキ涙」でHPが+10または-10されること。
    """
    # 1. 守護封印のつぼ
    runner = SimulationRunner()
    pot_id = find_card_by_name("守護封印のつぼ")
    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_guardian(0, 0)
    runner.state.set_true_hand(0, 0, pot_id)

    runner.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner.step(action=ActionType.ACTION_TARGET_SELF)

    # 守護神が割り振られていること (1~10)
    assert 1 <= runner.state.get_guardian(0) <= 10

    # 2. ドキドキ涙
    runner2 = SimulationRunner()
    tear_id = find_card_by_name("ドキドキ涙")
    runner2.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner2.state.current_actor_id = 0
    runner2.state.set_hp(0, 40)
    runner2.state.set_true_hand(0, 0, tear_id)

    runner2.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner2.step(action=ActionType.ACTION_TARGET_SELF)

    # HPが 50 (+10) または 30 (-10) になっていること
    assert runner2.state.get_hp(0) in [30, 50]


def test_broom_self_target_discard():
    """
    検証内容: 夜空のホウキを自分に使用した際の手札減少挙動。
    - 手札が [A, B, ホウキ] の状態で自分にホウキを使用する。
    - ホウキが使用されたスロットは is_used となり、破棄の抽選から除外される。
    - 残りの手札 A, B が破棄され CARD_EMPTY になる。
    - ターン終了時、ホウキのスロットのみにドロー補充が行われ、最終手札は [CARD_EMPTY, CARD_EMPTY, C] の1枚になる。
    """
    runner = SimulationRunner()
    broom_id = find_card_by_name("夜空のホウキ")

    # 武器と防具をダミーとして手札にセット
    dummy_a = find_card_by_type("weapon")
    dummy_b = find_card_by_type("defense")

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_mp(0, 20)

    # 手札を空にして [A, B, Broom] のみにする
    for i in range(18):
        runner.state.set_true_hand(0, i, godfield_core.CARD_EMPTY)
        runner.state.set_is_used(0, i, False)
        runner.state.set_is_deployed(0, i, False)

    runner.state.set_true_hand(0, 0, dummy_a)
    runner.state.set_true_hand(0, 1, dummy_b)
    runner.state.set_true_hand(0, 2, broom_id)

    # ホウキを選択
    runner.step(action=ActionType.ACTION_SELECT_HAND_2)
    # 自分を対象にする
    runner.step(action=ActionType.ACTION_TARGET_SELF)

    # 自分への効果適用後、A(スロット0)とB(スロット1)が破棄されていること
    assert runner.state.get_true_hand(0, 0) == godfield_core.CARD_EMPTY
    assert runner.state.get_true_hand(0, 1) == godfield_core.CARD_EMPTY

    # ターン終了時の補充処理が走った後、ホウキのスロット2のみに新規ドローが入っていること
    assert runner.state.get_true_hand(0, 2) != godfield_core.CARD_EMPTY
    assert runner.state.get_true_hand(0, 2) != broom_id


def test_goddess_soap_miracle_discard():
    """
    検証内容: 女神の石けんによる相手の展開中奇跡のランダム破棄。
    - 相手(P1)が奇跡を2枚展開している状態。
    - 女神の石けんをP1に対して使用。
    - 相手の展開中奇跡が2枚破棄されて CARD_EMPTY になること。
    """
    runner = SimulationRunner()
    soap_id = find_card_by_name("女神の石けん")
    miracle_a = find_card_by_type("miracle")

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_mp(0, 20)

    # 相手の手札スロット5に奇跡をセットして展開済みにする
    runner.state.set_true_hand(1, 5, miracle_a)
    runner.state.set_is_deployed(1, 5, True)

    runner.state.set_true_hand(0, 0, soap_id)

    # 石けんを使用して相手に撃つ
    runner.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner.step(action=ActionType.ACTION_TARGET_OPP)
    runner.step(action=ActionType.ACTION_CONFIRM)

    # 相手の展開中奇跡が破棄されていること
    assert runner.state.get_true_hand(1, 5) == godfield_core.CARD_EMPTY
    assert runner.state.get_is_deployed(1, 5) == False


def test_spiritual_doll_mp_bypass():
    """
    検証内容: 精霊のぬいぐるみによる奇跡のMP消費踏み倒し。
    - 自分のMPが2である（火の玉を出すのに最低限必要）。
    - 奇跡「火の玉」を出した後に、追加で「精霊のぬいぐるみ」を重ねる。
    - MP消費0で奇跡攻撃を発動でき、最終的なMPが2のまま保たれること。
    """
    runner = SimulationRunner()
    fireball_id = find_card_by_name("＜火の玉＞")
    doll_id = find_card_by_name("精霊のぬいぐるみ")

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_mp(0, 2)  # MP 2 (火の玉を出すのに必要)

    runner.state.set_true_hand(0, 0, fireball_id)
    runner.state.set_true_hand(0, 1, doll_id)

    # 1. まずPHASE_MAINで火の玉を選択可能であることを確認 (MP 2あるため)
    legal_main = godfield_core.get_legal_actions(runner.state)
    assert legal_main[ActionType.ACTION_SELECT_HAND_0.value] == True

    runner.step(action=ActionType.ACTION_SELECT_HAND_0)  # 火の玉選択

    # 2. PHASE_MIRACLE_PLUSで人形を選択可能であることを確認
    legal_plus = godfield_core.get_legal_actions(runner.state)
    assert legal_plus[ActionType.ACTION_SELECT_HAND_1.value] == True

    runner.step(action=ActionType.ACTION_SELECT_HAND_1)  # 人形選択
    runner.step(action=ActionType.ACTION_TARGET_OPP)  # 確定

    # 3. 消費MPが0なので、MPが2のままであり、PHASE_MIRACLE_DEFENSEへ進めていること
    assert runner.state.get_mp(0) == 2
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_MIRACLE_DEFENSE


def test_high_cost_miracle_spiritual_bypass():
    """
    検証内容: MPが不足している高コスト奇跡でも、手札に精霊系カードがあれば選択可能であること。
    - 自分のMPが2である。
    - 手札に奇跡「＜闇＞」（消費MP 5）と「精霊のぬいぐるみ」がある。
    - 1. 自身のMP（2）より高コストな奇跡「＜闇＞」（5）が、手札に人形があるため PHASE_MAIN で選択可能であることを確認。
    - 2. 「＜闇＞」を仮置きした時点（PHASE_MIRACLE_PLUS）では、消費MP（5）が手持ちMP（2）を超えているため、
         ターゲット決定（攻撃開始）が不可（非合法）であることを確認。
    - 3. 追加で「精霊のぬいぐるみ」を選択して仮置きに重ねた後、合計消費MPが0になるため、ターゲット決定が合法になることを確認。
    - 4. 攻撃を発動し、消費MPが0であるため最終的なMPが2のまま保たれることを確認。
    """
    runner = SimulationRunner()
    darkness_id = find_card_by_name("＜闇＞") # MP 5
    doll_id = find_card_by_name("精霊のぬいぐるみ")

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_mp(0, 2)  # MP 2 (＜闇＞のコスト5に不足)

    runner.state.set_true_hand(0, 0, darkness_id)
    runner.state.set_true_hand(0, 1, doll_id)

    # 1. 相手手札に精霊があるので選択可能であることを確認
    legal_main = godfield_core.get_legal_actions(runner.state)
    assert legal_main[ActionType.ACTION_SELECT_HAND_0.value] == True

    runner.step(action=ActionType.ACTION_SELECT_HAND_0)  # ＜闇＞を選択

    # 2. この段階ではMP不足のためターゲット決定はできないはず
    legal_plus = godfield_core.get_legal_actions(runner.state)
    assert legal_plus[ActionType.ACTION_TARGET_OPP.value] == False
    assert legal_plus[ActionType.ACTION_TARGET_SELF.value] == False
    assert legal_plus[ActionType.ACTION_SELECT_HAND_1.value] == True  # 精霊は選択可能

    runner.step(action=ActionType.ACTION_SELECT_HAND_1)  # 精霊を選択

    # 3. 精霊によってコストが0になったため、ターゲット決定ができるようになる
    legal_plus_2 = godfield_core.get_legal_actions(runner.state)
    assert legal_plus_2[ActionType.ACTION_TARGET_OPP.value] == True

    runner.step(action=ActionType.ACTION_TARGET_OPP)  # 確定

    # 4. 消費MPが0なので、MPが2のままであり、PHASE_MIRACLE_DEFENSEへ進めていること
    assert runner.state.get_mp(0) == 2
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_MIRACLE_DEFENSE


def test_group_attack_phases():
    """
    検証内容: 4パターンの攻撃フェイズ移行・ターゲット制限・防御フェイズ分岐のテスト。
    1. 単体武器 ➡ PHASE_ATTACK_PLUS
       - 蜃気楼を追加 ➡ PHASE_GROUP_WEAPON に遷移
       - 追加の武器（吹き矢等）が非合法になること
       - 自傷（TARGET_SELF）が非合法になること
       - 精霊をプラスして 0 MP で OPP を狙い、PHASE_DEFENSE に遷移すること
    2. 全体武器 ➡ PHASE_GROUP_WEAPON
       - 移行直後から他カードをプラスできず、TARGET_OPP のみが合法であること
       - OPP 選択により PHASE_DEFENSE に遷移すること
    3. 全体奇跡 ➡ PHASE_GROUP_MIRACLE
       - 移行直後は精霊によるMP軽減のみ可能、TARGET_OPP のみが合法であること
       - OPP 選択により PHASE_MIRACLE_DEFENSE に遷移すること
    4. 単体奇跡 ➡ PHASE_MIRACLE_PLUS
       - 2枚目の奇跡（火の玉＋火の玉など）を置いた場合、PHASE_ATTACK_PLUS に遷移すること
    """
    runner = SimulationRunner()
    runner.state.seed_rng(0)
    sword_id = find_card_by_name("銅のこん棒")
    mirage_id = find_card_by_name("＜蜃気楼＞")
    doll_id = find_card_by_name("精霊のぬいぐるみ")
    blowpipe_id = find_card_by_name("吹き矢")

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_mp(0, 10)

    runner.state.set_true_hand(0, 0, sword_id)
    runner.state.set_true_hand(0, 1, mirage_id)
    runner.state.set_true_hand(0, 2, doll_id)
    runner.state.set_true_hand(0, 3, blowpipe_id)

    runner.step(action=ActionType.ACTION_SELECT_HAND_0)  # 銅のこん棒を選択
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_ATTACK_PLUS

    # 蜃気楼をプラス
    runner.step(action=ActionType.ACTION_SELECT_HAND_1)
    # 全体武器フェイズに移行するはず
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_GROUP_WEAPON

    # 1. 通常武器（吹き矢）が非合法、かつ自傷（TARGET_SELF）が非合法であることをアサート
    legal_actions = godfield_core.get_legal_actions(runner.state)
    assert legal_actions[ActionType.ACTION_SELECT_HAND_3.value] == False  # 吹き矢は置けない
    assert legal_actions[ActionType.ACTION_TARGET_SELF.value] == False   # 自傷不可
    assert legal_actions[ActionType.ACTION_SELECT_HAND_2.value] == True   # 精霊は置ける

    # 精霊でコストを0にする
    runner.step(action=ActionType.ACTION_SELECT_HAND_2)
    # OPPを攻撃
    runner.step(action=ActionType.ACTION_TARGET_OPP)

    # 2. 物理防御フェイズ（PHASE_DEFENSE）に遷移していること、消費MPは0であること
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
    assert runner.state.get_mp(0) == 10

    # 2. 全体武器（火の粉袋）
    runner2 = SimulationRunner()
    runner2.state.seed_rng(0)
    saw_id = find_card_by_name("火の粉袋")
    runner2.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner2.state.current_actor_id = 0
    runner2.state.set_true_hand(0, 0, saw_id)

    runner2.step(action=ActionType.ACTION_SELECT_HAND_0)  # 火の粉袋を選択
    assert runner2.state.current_phase == godfield_core.GamePhase.PHASE_GROUP_WEAPON

    # のこぎりは最初から重ねられないため、ターゲットしかできないはず
    legal_actions2 = godfield_core.get_legal_actions(runner2.state)
    assert sum(1 for i in range(18) if legal_actions2[ActionType.ACTION_SELECT_HAND_0.value + i]) == 0
    assert legal_actions2[ActionType.ACTION_TARGET_OPP.value] == True
    assert legal_actions2[ActionType.ACTION_TARGET_SELF.value] == False

    runner2.step(action=ActionType.ACTION_TARGET_OPP)
    assert runner2.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE

    # 3. 全体奇跡（煙）
    runner3 = SimulationRunner()
    runner3.state.seed_rng(0)
    storm_id = find_card_by_name("＜煙＞")
    runner3.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner3.state.current_actor_id = 0
    runner3.state.set_mp(0, 20)
    runner3.state.set_true_hand(0, 0, storm_id)

    runner3.step(action=ActionType.ACTION_SELECT_HAND_0)  # 煙を選択
    assert runner3.state.current_phase == godfield_core.GamePhase.PHASE_GROUP_MIRACLE

    legal_actions3 = godfield_core.get_legal_actions(runner3.state)
    assert legal_actions3[ActionType.ACTION_TARGET_OPP.value] == True
    assert legal_actions3[ActionType.ACTION_TARGET_SELF.value] == False

    runner3.step(action=ActionType.ACTION_TARGET_OPP)
    assert runner3.state.current_phase == godfield_core.GamePhase.PHASE_MIRACLE_DEFENSE

    # 4. 単体奇跡（火の玉）の連撃による武器攻撃変化 + 蜃気楼 + 精霊のぬいぐるみ ➡ 全体武器攻撃 ➡ 物理防御
    runner4 = SimulationRunner()
    runner4.state.seed_rng(0)
    fireball_id = find_card_by_name("＜火の玉＞")
    mirage_id = find_card_by_name("＜蜃気楼＞")
    doll_id = find_card_by_name("精霊のぬいぐるみ")

    runner4.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner4.state.current_actor_id = 0
    runner4.state.set_mp(0, 20)
    runner4.state.set_true_hand(0, 0, fireball_id)
    runner4.state.set_true_hand(0, 1, fireball_id)
    runner4.state.set_true_hand(0, 2, mirage_id)
    runner4.state.set_true_hand(0, 3, doll_id)

    runner4.step(action=ActionType.ACTION_SELECT_HAND_0)  # 1枚目の火の玉を選択
    assert runner4.state.current_phase == godfield_core.GamePhase.PHASE_MIRACLE_PLUS

    # 2枚目の火の玉を選択
    runner4.step(action=ActionType.ACTION_SELECT_HAND_1)
    # 2枚重ねたので PHASE_ATTACK_PLUS（単体武器攻撃扱い）に遷移するはず
    assert runner4.state.current_phase == godfield_core.GamePhase.PHASE_ATTACK_PLUS

    # 蜃気楼をプラス
    runner4.step(action=ActionType.ACTION_SELECT_HAND_2)
    # 蜃気楼を置いたので全体化し、PHASE_GROUP_WEAPON に遷移するはず
    assert runner4.state.current_phase == godfield_core.GamePhase.PHASE_GROUP_WEAPON

    # 精霊のぬいぐるみを選択してMP消費を無効化する
    legal_actions4 = godfield_core.get_legal_actions(runner4.state)
    assert legal_actions4[ActionType.ACTION_SELECT_HAND_3.value] == True  # ぬいぐるみが置けるはず
    runner4.step(action=ActionType.ACTION_SELECT_HAND_3)

    # ターゲット OPP を指定
    assert legal_actions4[ActionType.ACTION_TARGET_OPP.value] == True
    runner4.step(action=ActionType.ACTION_TARGET_OPP)

    # 最終的に物理/属性防御（PHASE_DEFENSE）に遷移し、消費MPは4（火の玉x2のコスト分、蜃気楼は0）となりMPは16であること
    assert runner4.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
    assert runner4.state.get_mp(0) == 16
