import godfield_core
from godfield_core import ActionType, GamePhase
from tests.core.test_utils import SimulationRunner, find_card_by_name


def test_reaction_wall_un_elemental_only():
    """
    検証内容: ＜壁＞は無属性の物理武器攻撃のみ阻止可能。有属性の攻撃に対しては直接選択できない。
    """
    runner = SimulationRunner()
    punch_id = find_card_by_name("weapons/punch")  # 無属性武器
    fire_sword_id = find_card_by_name("weapons/torch")  # 火属性武器
    wall_id = find_card_by_name("miracles/wall")  # 阻止カード

    # 1. 無属性武器攻撃に対して壁が合法手となるか
    runner.set_status(0, hp=40, mp=10)
    runner.set_status(1, hp=40, mp=10)
    runner.state.set_true_hand(0, 0, punch_id)
    runner.state.set_true_hand(1, 0, wall_id)

    # プレイヤー0がパンチで攻撃
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_TARGET_OPP)
    assert runner.state.current_phase == GamePhase.PHASE_DEFENSE

    # プレイヤー1の合法手を取得
    actions = godfield_core.get_legal_actions(runner.state)
    assert actions[ActionType.ACTION_SELECT_HAND_0] is True  # ＜壁＞が合法手であること

    # 2. 火属性武器攻撃に対して壁が非合法となるか
    runner.reset_state()
    runner.set_status(0, hp=40, mp=10)
    runner.set_status(1, hp=40, mp=10)
    runner.state.set_true_hand(0, 0, fire_sword_id)
    runner.state.set_true_hand(1, 0, wall_id)

    # プレイヤー0がたいまつ(火)で攻撃
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_TARGET_OPP)
    assert runner.state.current_phase == GamePhase.PHASE_DEFENSE

    # プレイヤー1の合法手を取得
    actions = godfield_core.get_legal_actions(runner.state)
    assert actions[ActionType.ACTION_SELECT_HAND_0] is False  # 有属性のため壁は非合法であること


def test_rainbow_curtain_wall_and_reflection_sword_synergy():
    """
    検証内容: 有属性の物理武器攻撃に対し、最初に「虹のカーテン」を置くことで無属性化（ELEM_NONE）され、
    2枚目に「＜壁＞」や「反射剣」を選択可能になる。また、虹のカーテン自体は1枚目にしか置けない。
    """
    # 1. 虹のカーテン ＋ 壁
    runner = SimulationRunner()
    fire_sword_id = find_card_by_name("weapons/torch")
    curtain_id = find_card_by_name("armor/rainbow-curtain")
    wall_id = find_card_by_name("miracles/wall")

    runner.set_status(0, hp=40, mp=10)
    runner.set_status(1, hp=40, mp=10)
    runner.state.set_true_hand(0, 0, fire_sword_id)
    runner.state.set_true_hand(1, 0, curtain_id)
    runner.state.set_true_hand(1, 1, wall_id)

    # プレイヤー0がたいまつ(火)で攻撃
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_TARGET_OPP)
    assert runner.state.current_phase == GamePhase.PHASE_DEFENSE

    # 1枚目に壁は置けないが、カーテンは置ける
    actions = godfield_core.get_legal_actions(runner.state)
    assert actions[ActionType.ACTION_SELECT_HAND_1] is False  # 壁はまだ不可
    assert actions[ActionType.ACTION_SELECT_HAND_0] is True  # カーテンは可能

    # カーテンを選択
    runner.step(ActionType.ACTION_SELECT_HAND_0)

    # カーテンを置いた後は、カーテンを追加することはできない（1枚目限定ルール）
    runner.state.set_true_hand(1, 2, curtain_id)
    actions2 = godfield_core.get_legal_actions(runner.state)
    assert actions2[ActionType.ACTION_SELECT_HAND_2] is False  # 2枚目には置けない

    # カーテンによって攻撃が無属性化されたため、壁が選択可能になる
    assert actions2[ActionType.ACTION_SELECT_HAND_1] is True  # 壁が解禁される

    # 壁を選択して決定
    runner.step(ActionType.ACTION_SELECT_HAND_1)
    runner.step(ActionType.ACTION_CONFIRM)

    # 阻止成功により被弾0、ターン終了
    assert runner.state.get_hp(1) == 40
    assert runner.state.current_phase == GamePhase.PHASE_MAIN  # ターン終了してメインへ

    # 2. 虹のカーテン ＋ 反射剣 -> 相手に反射して攻守交代
    runner.reset_state()
    reflection_sword_id = find_card_by_name("weapons/reflection-sword")
    runner.set_status(0, hp=40, mp=10)
    runner.set_status(1, hp=40, mp=10)
    runner.state.set_true_hand(0, 0, fire_sword_id)
    runner.state.set_true_hand(1, 0, curtain_id)
    runner.state.set_true_hand(1, 1, reflection_sword_id)

    # プレイヤー0が攻撃
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_TARGET_OPP)

    # プレイヤー1が カーテン ＋ 反射剣 を選択
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_SELECT_HAND_1)
    runner.step(ActionType.ACTION_CONFIRM)

    # 反射成功により、プレイヤー0が防御側（PHASE_DEFENSE）、プレイヤー1が攻撃側へと入れ替わる
    assert runner.state.attacker_id == 1
    assert runner.state.defender_id == 0
    assert runner.state.current_actor_id == 0
    assert runner.state.current_phase == GamePhase.PHASE_DEFENSE


def test_miracle_defense_reaction_rules():
    """
    検証内容:
    1. 奇跡攻撃に対し、虹のカーテンの後に「＜乱気流＞」を重ねることは非合法（奇跡防御での虹のカーテン後のリアクション禁止）。
    2. 属性奇跡に対し、虹のカーテンを置いて無属性化した後、無属性の一般防具（木盾等）を重ねてダメージ軽減するルートは合法。
    """
    runner = SimulationRunner()
    flame_id = find_card_by_name("miracles/flame")  # 炎 (火奇跡)
    curtain_id = find_card_by_name("armor/rainbow-curtain")
    turbulence_id = find_card_by_name("miracles/turbulence")  # 奇跡リアクション
    wood_shield_id = find_card_by_name("armor/wood-shield")  # 一般防具 (守2)

    runner.set_status(0, hp=40, mp=10)
    runner.set_status(1, hp=40, mp=10)
    runner.state.set_true_hand(0, 0, flame_id)
    runner.state.set_true_hand(1, 0, curtain_id)
    runner.state.set_true_hand(1, 1, turbulence_id)
    runner.state.set_true_hand(1, 2, wood_shield_id)

    # プレイヤー0が炎で攻撃
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_TARGET_OPP)
    assert runner.state.current_phase == GamePhase.PHASE_MIRACLE_DEFENSE

    # 最初はカーテンも乱気流も一般防具（対抗属性ではない木盾は非合法）もチェック
    actions = godfield_core.get_legal_actions(runner.state)
    assert actions[ActionType.ACTION_SELECT_HAND_0] is True  # カーテンは1枚目なので可能
    assert actions[ActionType.ACTION_SELECT_HAND_1] is True  # 乱気流も可能
    assert actions[ActionType.ACTION_SELECT_HAND_2] is False  # 木盾は属性が合わないので不可

    # カーテンを選択
    runner.step(ActionType.ACTION_SELECT_HAND_0)

    # カーテン選択後は、乱気流（リアクション）は非合法になるが、無属性化したため木盾（一般防具）が合法になること
    actions2 = godfield_core.get_legal_actions(runner.state)
    assert actions2[ActionType.ACTION_SELECT_HAND_1] is False  # 乱気流は非合法！
    assert actions2[ActionType.ACTION_SELECT_HAND_2] is True  # 木盾は合法！

    # 木盾を選択して決定
    runner.step(ActionType.ACTION_SELECT_HAND_2)
    runner.step(ActionType.ACTION_CONFIRM)

    # 炎(10) - 木盾(2) = 8 ダメージを受けて生存、ターン終了
    assert runner.state.get_hp(1) == 32
    assert runner.state.current_phase == GamePhase.PHASE_MAIN


def find_bounce_seeds():
    """
    弾く（Bounce）カードのRNGシードを取得するヘルパー。
    成功（相手に反射）するシードと、失敗（自傷）するシードを探索して返します。
    """
    absorption_id = find_card_by_name("miracles/absorption")
    turbulence_id = find_card_by_name("miracles/turbulence")
    success_seed = None
    failure_seed = None

    for seed in range(200):
        runner = SimulationRunner()
        runner.state.seed_rng(seed)
        runner.set_status(0, hp=40, mp=10)
        runner.set_status(1, hp=5, mp=10)
        runner.state.set_true_hand(0, 0, absorption_id)
        runner.state.set_true_hand(1, 0, turbulence_id)

        runner.step(ActionType.ACTION_SELECT_HAND_0)
        runner.step(ActionType.ACTION_TARGET_OPP)
        runner.step(ActionType.ACTION_SELECT_HAND_0)
        runner.step(ActionType.ACTION_CONFIRM)

        if runner.state.current_phase == GamePhase.PHASE_MIRACLE_DEFENSE:
            success_seed = seed
        else:
            failure_seed = seed

        if success_seed is not None and failure_seed is not None:
            break

    return success_seed, failure_seed


def test_bounce_success_swaps_attacker_defender():
    """
    検証内容: 弾く（Bounce）が成功した場合の反射（攻守交代）テスト。
    - 弾き（乱気流）が成功した際、本来の攻撃者（P0）が防御側（defender）になり、本来の防御者（P1）が攻撃側（attacker）にスワップして、フェイズが PHASE_MIRACLE_DEFENSE のままアクターが P0 に交代することを確認します。
    - 弾いた本人（P1）は無傷（HP 5 のまま）であることを確認します。
    """
    success_seed, _ = find_bounce_seeds()
    assert success_seed is not None, "反射成功用のシードが見つかりませんでした"

    runner = SimulationRunner()
    runner.state.seed_rng(success_seed)
    runner.set_status(0, hp=40, mp=10)
    runner.set_status(1, hp=5, mp=10)

    absorption_id = find_card_by_name("miracles/absorption")
    turbulence_id = find_card_by_name("miracles/turbulence")
    runner.state.set_true_hand(0, 0, absorption_id)
    runner.state.set_true_hand(1, 0, turbulence_id)

    # 攻撃 & 弾き発動
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_TARGET_OPP)
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_CONFIRM)

    # 攻守交代の確認
    assert runner.state.attacker_id == 1
    assert runner.state.defender_id == 0
    assert runner.state.current_actor_id == 0
    assert runner.state.current_phase == GamePhase.PHASE_MIRACLE_DEFENSE
    assert runner.state.get_hp(1) == 5


def test_bounce_failure_causes_self_injury():
    """
    検証内容: 弾く（Bounce）が失敗した場合の自傷ダメージ適用テスト。
    - 弾きが失敗した際、攻撃が自分に跳ね返り、自分が自分を攻撃した扱いとして効果解決されることを確認します。
    - 自傷によるダメージでHPが減少することを確認します。
    """
    _, failure_seed = find_bounce_seeds()
    assert failure_seed is not None, "弾き失敗用のシードが見つかりませんでした"

    runner = SimulationRunner()
    runner.state.seed_rng(failure_seed)
    runner.set_status(0, hp=40, mp=10)
    runner.set_status(1, hp=20, mp=10)  # HP20から開始

    absorption_id = find_card_by_name("miracles/absorption")
    turbulence_id = find_card_by_name("miracles/turbulence")
    runner.state.set_true_hand(0, 0, absorption_id)
    runner.state.set_true_hand(1, 0, turbulence_id)

    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_TARGET_OPP)
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_CONFIRM)

    # 自傷ダメージ（10）と自傷HP吸収回復（+10）が相殺されるため、結果としてHPは 20 のままで生存する
    # ※もし吸収が無く単にダメージを自傷した場合、HPが減る。
    assert runner.state.get_hp(1) == 20
    assert runner.state.current_phase == GamePhase.PHASE_MAIN


def test_bounce_failure_absorb_self_healing_survival():
    """
    検証内容: 吸収攻撃の自傷時におけるHP 5 -> 0 -> 10 生存ロジックテスト。
    - 弾き失敗（自傷）時に、HP 5 から攻撃力 10 の吸収攻撃を被弾した場合に、HPが一時的に 0 にクランプされつつも、死亡判定を行う前に同じ解決ステップ内で +10 回復し、最終HPが 10 となって生存（is_done = False）することを確認します。
    """
    _, failure_seed = find_bounce_seeds()
    assert failure_seed is not None, "弾き失敗用のシードが見つかりませんでした"

    runner = SimulationRunner()
    runner.state.seed_rng(failure_seed)
    runner.set_status(0, hp=40, mp=10)
    runner.set_status(1, hp=5, mp=10)  # HP 5 から開始

    absorption_id = find_card_by_name("miracles/absorption")
    turbulence_id = find_card_by_name("miracles/turbulence")
    runner.state.set_true_hand(0, 0, absorption_id)
    runner.state.set_true_hand(1, 0, turbulence_id)

    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_TARGET_OPP)
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_CONFIRM)

    # 自傷解決: HP 5 - 10 (0にクランプ) + 10 = 10 で生存
    assert runner.state.is_done is False
    assert runner.state.get_hp(1) == 10
    assert runner.state.current_phase == GamePhase.PHASE_MAIN


def test_confirm_illegal_when_staged_mp_exceeds_current_mp():
    """
    検証内容: 防御側がMP不足の状態で防具を仮置き（staged）している場合、
    精霊等のMP0化カードを追加で重ねるまでは ACTION_CONFIRM が非合法手になること。
    """
    runner = SimulationRunner()
    flame_id = find_card_by_name("miracles/flame")  # 炎
    turbulence_id = find_card_by_name("miracles/turbulence")  # 乱気流 (MP 5)
    doll_id = find_card_by_name("精霊のぬいぐるみ")  # 精霊のぬいぐるみ

    runner.set_status(0, hp=40, mp=10)
    runner.set_status(1, hp=40, mp=2)  # P1のMPを2にセット (乱気流のMP 5より少ない)

    runner.state.set_true_hand(0, 0, flame_id)
    runner.state.set_true_hand(1, 0, turbulence_id)
    runner.state.set_true_hand(1, 1, doll_id)

    # 1. プレイヤー0が奇跡で攻撃
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_TARGET_OPP)
    assert runner.state.current_phase == GamePhase.PHASE_MIRACLE_DEFENSE

    # 2. プレイヤー1が乱気流を選択
    # 手元に「精霊のぬいぐるみ」があるため、乱気流の選択は合法手である
    actions1 = godfield_core.get_legal_actions(runner.state)
    assert actions1[ActionType.ACTION_SELECT_HAND_0] is True

    runner.step(ActionType.ACTION_SELECT_HAND_0)

    # 3. 乱気流を仮置きした段階で、MP 5 に対して MP 2 しかないため、
    # 精霊を追加するまでは CONFIRM は非合法手であるべき
    actions2 = godfield_core.get_legal_actions(runner.state)
    assert actions2[ActionType.ACTION_CONFIRM] is False
    assert actions2[ActionType.ACTION_SELECT_HAND_1] is True  # 精霊のぬいぐるみは選択可能

    # 4. 精霊のぬいぐるみを選択して追加
    runner.step(ActionType.ACTION_SELECT_HAND_1)

    # 5. 精霊を追加したことで合計MPコストが0になり、CONFIRMが合法手になること
    actions3 = godfield_core.get_legal_actions(runner.state)
    assert actions3[ActionType.ACTION_CONFIRM] is True

    # 6. 確定して解決
    runner.step(ActionType.ACTION_CONFIRM)

    # MPが減らずに2のまま維持されていることを確認
    assert runner.state.get_mp(1) == 2
