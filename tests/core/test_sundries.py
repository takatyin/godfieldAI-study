import godfield_core
from godfield_core import ActionType, CurseType, SicknessType, GamePhase
from tests.core.test_utils import SimulationRunner, find_card_by_name, find_card_by_type


def test_healing_sundry_smile_drop_exclusivity():
    """
    検証内容: 雑貨使用時における複数雑貨の同時使用禁止ルール。
    - メインフェイズで雑貨（スマイルのしずく）を選択した際、手札にある別の雑貨（ロマンスの香木）が非合法手（False）になり、同時使用できないことを確認します。
    """
    runner = SimulationRunner()
    runner.reset_state()

    smile_drop_id = find_card_by_name("スマイルのしずく")
    romance_wood_id = find_card_by_name("ロマンスの香木")

    runner.set_status(0, hp=10, mp=0)
    runner.set_hand(0, [smile_drop_id, romance_wood_id])

    # スマイルのしずくを選択
    runner.step(ActionType.ACTION_SELECT_HAND_0)

    # ロマンスの香木（スロット1）が非合法手になっていることを確認
    mask = godfield_core.get_legal_actions(runner.state)
    assert mask[ActionType.ACTION_SELECT_HAND_1] == False
    assert mask[ActionType.ACTION_TARGET_SELF] == True


def test_healing_sundry_smile_drop_resolves():
    """
    検証内容: スマイルのしずくによるHP回復解決テスト。
    - 自分を対象に「スマイルのしずく」を使用し、HPが +5 回復（10 -> 15）し、ターンが相手に正常に移行することを確認します。
    """
    runner = SimulationRunner()
    runner.reset_state()

    smile_drop_id = find_card_by_name("スマイルのしずく")

    runner.set_status(0, hp=10, mp=0)
    runner.set_hand(0, [smile_drop_id])

    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_TARGET_SELF)

    # ターンが相手(1)に移り、HPが15になっていること
    assert runner.state.current_actor_id == 1
    assert runner.state.get_hp(0) == 15


def test_healing_sundry_romance_wood_resolves():
    """
    検証内容: ロマンスの香木によるMP回復解決テスト。
    - 自分を対象に「ロマンスの香木」を使用し、MPが +15 回復（0 -> 15）することを確認します。
    """
    runner = SimulationRunner()
    runner.reset_state()

    romance_wood_id = find_card_by_name("ロマンスの香木")

    runner.set_status(0, hp=10, mp=0)
    runner.set_hand(0, [romance_wood_id])

    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_TARGET_SELF)

    # MPが15になっていること
    assert runner.state.get_mp(0) == 15


def test_healing_sundry_hp_clamping():
    """
    検証内容: HP回復時の上限値（99）クランプテスト。
    - HPが 98 の状態で「スマイルのしずく（HP+5）」を使用した際、HPが 99 にクランプされることを確認します。
    """
    runner = SimulationRunner()
    runner.reset_state()

    smile_drop_id = find_card_by_name("スマイルのしずく")

    runner.set_status(0, hp=98, mp=0)
    runner.set_hand(0, [smile_drop_id])

    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_TARGET_SELF)

    assert runner.state.get_hp(0) == 99


def test_healing_sundry_mp_clamping():
    """
    検証内容: MP回復時の上限値（99）クランプテスト。
    - MPが 90 の状態で「ロマンスの香木（MP+15）」を使用した際、MPが 99 にクランプされることを確認します。
    """
    runner = SimulationRunner()
    runner.reset_state()

    romance_wood_id = find_card_by_name("ロマンスの香木")

    runner.set_status(0, hp=10, mp=90)
    runner.set_hand(0, [romance_wood_id])

    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_TARGET_SELF)

    assert runner.state.get_mp(0) == 99


def test_recovery_and_sickness_sundry():
    """
    検証内容: 天国草によるMP回復と天国病付与テスト。
    - 相手に「天国草」を使用し、相手が受諾した際、相手のMPが +20 回復（10 -> 30）し、かつ「天国病」になることを確認します。
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

    # 相手(P1)のステータス変化
    assert runner.state.get_mp(1) == 30
    assert runner.state.get_sickness(1) == SicknessType.SICKNESS_HEAVEN


def test_smile_shell_curing_sickness_and_curses():
    """
    検証内容: スマイルの貝がらによる状態異常/災い治癒テスト。
    - 「スマイルの貝がら」を使用すると、風邪（SICKNESS_COLD）および霧（CURSE_FOG）が治療される（治癒）ことを確認します。
    - スマイルでは治らない「夢（CURSE_DREAM）」が治癒されずに残ることを確認します。
    """
    runner = SimulationRunner()
    smile_shell_id = find_card_by_name("スマイルの貝がら")

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_sickness(0, SicknessType.SICKNESS_COLD)
    runner.state.set_curses(0, CurseType.CURSE_FOG, True)
    runner.state.set_curses(0, CurseType.CURSE_DREAM, True)

    runner.state.set_true_hand(0, 0, smile_shell_id)
    runner.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner.step(action=ActionType.ACTION_TARGET_SELF)

    assert runner.state.get_sickness(0) == SicknessType.SICKNESS_NONE
    assert runner.state.get_curses(0, CurseType.CURSE_FOG) == False
    assert runner.state.get_curses(0, CurseType.CURSE_DREAM) == True


def test_heart_shell_curing_sickness_and_curses():
    """
    検証内容: ハートの貝がらによる全状態異常/全災い治癒テスト。
    - 「ハートの貝がら」を使用すると、最高度の異常である「地獄病（SICKNESS_HELL）」およびすべての災い（霧、閃光、暗雲、夢）が完全に治癒されることを確認します。
    """
    runner = SimulationRunner()
    heart_shell_id = find_card_by_name("ハートの貝がら")

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_sickness(0, SicknessType.SICKNESS_HELL)
    for c in [
        CurseType.CURSE_FOG,
        CurseType.CURSE_FLASH,
        CurseType.CURSE_DARK_CLOUD,
        CurseType.CURSE_DREAM,
    ]:
        runner.state.set_curses(0, c, True)

    runner.state.set_true_hand(0, 0, heart_shell_id)
    runner.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner.step(action=ActionType.ACTION_TARGET_SELF)

    assert runner.state.get_sickness(0) == SicknessType.SICKNESS_NONE
    for c in [
        CurseType.CURSE_FOG,
        CurseType.CURSE_FLASH,
        CurseType.CURSE_DARK_CLOUD,
        CurseType.CURSE_DREAM,
    ]:
        assert runner.state.get_curses(0, c) == False


def test_guardian_pot_dwells_guardian():
    """
    検証内容: 守護封印のつぼによる守護神 Dwelling テスト。
    - 「守護封印のつぼ」を使用した際、自分の守護神スロットに 1 〜 10 のいずれかの有効な守護神IDが宿ることを確認します。
    """
    runner = SimulationRunner()
    pot_id = find_card_by_name("守護封印のつぼ")
    
    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_guardian(0, 0)
    runner.state.set_true_hand(0, 0, pot_id)

    runner.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner.step(action=ActionType.ACTION_TARGET_SELF)

    # 守護神IDが1から10の範囲で割り振られていること
    assert 1 <= runner.state.get_guardian(0) <= 10


def test_thump_tear_random_healing_or_damage():
    """
    検証内容: ドキドキ涙による確率的HP増減テスト。
    - 「ドキドキ涙」を使用した際、結果としてHPが +10（50）または -10（30）のいずれかに確率変動することを確認します。
    """
    runner = SimulationRunner()
    tear_id = find_card_by_name("ドキドキ涙")
    
    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_hp(0, 40)
    runner.state.set_true_hand(0, 0, tear_id)

    runner.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner.step(action=ActionType.ACTION_TARGET_SELF)

    # 30 または 50 になっていること
    assert runner.state.get_hp(0) in [30, 50]


def test_broom_self_target_discard():
    """
    検証内容: 夜空のホウキによる自己手札破棄とドロー補充。
    - 手札 [木刀, 木の盾, ホウキ] の状態で自分に「夜空のホウキ」を使用。
    - ホウキ以外の他カード（木刀、木の盾）が破棄され、CARD_EMPTY になることを確認します。
    - ターン終了時のドロー補充により、ホウキのスロット（スロット2）のみに新しいカードが入ることを確認します。
    """
    runner = SimulationRunner()
    broom_id = find_card_by_name("夜空のホウキ")
    dummy_a = find_card_by_type("weapon")
    dummy_b = find_card_by_type("defense")

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_mp(0, 20)

    # 手札初期化
    for i in range(18):
        runner.state.set_true_hand(0, i, godfield_core.CARD_EMPTY)
        runner.state.set_is_used(0, i, False)
        runner.state.set_is_deployed(0, i, False)

    runner.state.set_true_hand(0, 0, dummy_a)
    runner.state.set_true_hand(0, 1, dummy_b)
    runner.state.set_true_hand(0, 2, broom_id)

    runner.step(action=ActionType.ACTION_SELECT_HAND_2)
    runner.step(action=ActionType.ACTION_TARGET_SELF)

    # 他カードが破棄されていること
    assert runner.state.get_true_hand(0, 0) == godfield_core.CARD_EMPTY
    assert runner.state.get_true_hand(0, 1) == godfield_core.CARD_EMPTY

    # スロット2のみ新規カードがドローされていること
    assert runner.state.get_true_hand(0, 2) != godfield_core.CARD_EMPTY
    assert runner.state.get_true_hand(0, 2) != broom_id


def test_goddess_soap_miracle_discard():
    """
    検証内容: 女神の石けんによる相手の展開中奇跡の破棄。
    - 相手（P1）が展開している奇跡に対し、自分が「女神の石けん」を使用した際、相手の展開中の奇跡が破棄されて手札スロットが CARD_EMPTY になることを確認します。
    """
    runner = SimulationRunner()
    soap_id = find_card_by_name("女神の石けん")
    miracle_a = find_card_by_type("miracle")

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_mp(0, 20)

    # 相手のスロット5に奇跡を展開
    runner.state.set_true_hand(1, 5, miracle_a)
    runner.state.set_is_deployed(1, 5, True)
    runner.state.set_true_hand(0, 0, soap_id)

    runner.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner.step(action=ActionType.ACTION_TARGET_OPP)
    runner.step(action=ActionType.ACTION_CONFIRM)

    # 展開中奇跡が解除されていること
    assert runner.state.get_true_hand(1, 5) == godfield_core.CARD_EMPTY
    assert runner.state.get_is_deployed(1, 5) == False


def test_sundry_logic_self_target():
    """
    検証内容: 雑貨の自分対象時の即時適用テスト。
    - 自分を対象に雑貨（天国草）を使用した際、ミラー確認フェイズをスキップして即座に解決され、相手のメインフェイズに遷移することを確認します。
    """
    runner = SimulationRunner()
    sundry_id = find_card_by_name("天国草")

    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_mp(0, 10)
    runner.state.set_true_hand(0, 0, sundry_id)

    runner.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner.step(action=ActionType.ACTION_TARGET_SELF)

    # ミラー確認を経ず即解決
    assert runner.state.current_phase == GamePhase.PHASE_MAIN
    assert runner.state.current_actor_id == 1
    assert runner.state.get_mp(0) > 10


def test_sundry_logic_opp_target_accept():
    """
    検証内容: 相手対象時の雑貨受諾テスト。
    - 相手を対象に雑貨（天国草）を使用した際、一度ミラー確認フェイズ（PHASE_SUNDRY_SELECT_MIRROR）に遷移することを確認します。
    - 相手が受諾（CONFIRM）した時点で、効果（MP回復）が相手に適用されることを確認します。
    """
    runner = SimulationRunner()
    sundry_id = find_card_by_name("天国草")

    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_mp(1, 10)
    runner.state.set_true_hand(0, 0, sundry_id)

    runner.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner.step(action=ActionType.ACTION_TARGET_OPP)

    # ミラー選択フェイズへ
    assert runner.state.current_phase == GamePhase.PHASE_SUNDRY_SELECT_MIRROR
    assert runner.state.current_actor_id == 1

    # 相手が受諾
    runner.step(action=ActionType.ACTION_CONFIRM)

    # 解決されて相手のMPが回復していること
    assert runner.state.current_phase == GamePhase.PHASE_MAIN
    assert runner.state.current_actor_id == 1
    assert runner.state.get_mp(1) > 10


def test_sundry_logic_opp_target_mirror_reflect():
    """
    検証内容: 相手対象時の雑貨ミラー反射テスト。
    - 相手を対象に雑貨を使用し、相手が「スーパーミラー」で反射した場合、反射フェイズのままアクターが自分（0）に戻ることを確認します。
    - 自分が受諾（CONFIRM）した時点で、効果が本来の使用者の自分自身に跳ね返って適用されることを確認します。
    """
    runner = SimulationRunner()
    sundry_id = find_card_by_name("天国草")
    super_mirror_id = find_card_by_name("スーパーミラー")

    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_mp(0, 10)
    runner.state.set_mp(1, 10)

    runner.state.set_true_hand(0, 0, sundry_id)
    runner.state.set_true_hand(1, 0, super_mirror_id)

    runner.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner.step(action=ActionType.ACTION_TARGET_OPP)

    # 相手がスーパーミラー使用
    runner.step(action=ActionType.ACTION_SELECT_HAND_0)

    # アクターが自分(0)に交代
    assert runner.state.current_phase == GamePhase.PHASE_SUNDRY_SELECT_MIRROR
    assert runner.state.current_actor_id == 0

    # 自分が受諾
    runner.step(action=ActionType.ACTION_CONFIRM)

    # 自分のMPが回復し、相手のMPは10のまま維持されていること
    assert runner.state.get_mp(0) > 10
    assert runner.state.get_mp(1) == 10
