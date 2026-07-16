
import godfield_core
from godfield_core import ActionType
from tests.core.test_utils import SimulationRunner, find_card_by_name


def test_pray_action():
    """
    検証内容: 「祈る」アクションの動作と、それに伴う基本状態遷移のテスト。
    - 手札に武器（攻撃カード）がない場合、合法手として「祈る」が選択可能になること。
    - 「祈る」を実行すると、プレイヤーのターンが終了して相手のターンに移行すること。
    - 祈ったことで手札の空き枠にカードが1枚ドローされ、それが未使用状態で保持されていること。
    """
    runner = SimulationRunner()
    runner.reset_state()

    # 手札を空にする (is_weapon がない状態にする)
    runner.set_hand(0, [])

    mask = godfield_core.get_legal_actions(runner.state)
    assert mask[ActionType.ACTION_PRAY] == True
    assert mask[ActionType.ACTION_SELECT_HAND_0] == False  # empty slot

    runner.step(ActionType.ACTION_PRAY)

    # アクターが相手(1)に交代していること
    assert runner.state.current_actor_id == 1

    # 祈ったことでカードを1枚ドローしているはず
    assert runner.state.get_true_hand(0, 0) != godfield_core.CARD_EMPTY
    assert not runner.state.get_is_used(0, 0)


def test_healing_sundry_smile_drop():
    """
    検証内容: 雑貨アイテム（スマイルのしずく）の回復動作と、複数雑貨の同時使用禁止ルールのテスト。
    - HPが減った状態で「スマイルのしずく」を使用選択したとき、他の雑貨（ロマンスの香木など）が追加選択できなくなる（排他仕様）ことを確認。
    - 自分を対象に確定実行した際、HPが +5 回復し、ターンが相手に移ることを確認。
    """
    runner = SimulationRunner()
    runner.reset_state()

    smile_drop_id = find_card_by_name("スマイルのしずく")
    romance_wood_id = find_card_by_name("ロマンスの香木")

    runner.set_status(0, hp=10, mp=0)
    runner.set_hand(0, [smile_drop_id, romance_wood_id])

    mask = godfield_core.get_legal_actions(runner.state)
    assert mask[ActionType.ACTION_SELECT_HAND_0] == True
    assert mask[ActionType.ACTION_SELECT_HAND_1] == True
    assert mask[ActionType.ACTION_TARGET_SELF] == False

    # スマイルのしずく(HP+5)を使う
    runner.step(ActionType.ACTION_SELECT_HAND_0)

    # 雑貨は複数同時に使えないため、他の手札は選択不可になるはず
    mask = godfield_core.get_legal_actions(runner.state)
    assert mask[ActionType.ACTION_SELECT_HAND_1] == False
    assert mask[ActionType.ACTION_TARGET_SELF] == True
    assert mask[ActionType.ACTION_TARGET_OPP] == True

    # 確定（自分対象）
    runner.step(ActionType.ACTION_TARGET_SELF)

    # ターンが相手(1)に移っていること
    assert runner.state.current_actor_id == 1

    # HPが回復していること (10->15)
    assert runner.state.get_hp(0) == 15
    assert runner.state.get_mp(0) == 0


def test_healing_sundry_romance_wood():
    """
    検証内容: 雑貨アイテム（ロマンスの香木）のMP回復動作のテスト。
    - 「ロマンスの香木」を自分に対して使用したとき、MPが正常に +15 回復することを確認。
    """
    runner = SimulationRunner()
    runner.reset_state()

    romance_wood_id = find_card_by_name("ロマンスの香木")

    runner.set_status(0, hp=10, mp=0)
    runner.set_hand(0, [romance_wood_id])

    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_TARGET_SELF)

    # MPが回復していること (0->15)
    assert runner.state.get_hp(0) == 10
    assert runner.state.get_mp(0) == 15


def test_healing_sundry_clamping():
    """
    検証内容: HP/MP回復量が上限値（99）を超えた際のクランプ処理（上限張り付き）のテスト。
    - HP 98 から「スマイルのしずく (HP+5)」を使用した際、HPが 103 ではなく 99 にクランプされることを確認。
    - MP 90 から「ロマンスの香木 (MP+15)」を使用した際、MPが 105 ではなく 99 にクランプされることを確認。
    """
    runner = SimulationRunner()
    runner.reset_state()

    smile_drop_id = find_card_by_name("スマイルのしずく")
    romance_wood_id = find_card_by_name("ロマンスの香木")

    # HP98, MP90から回復させてオーバーフロー(99超え)をテスト
    runner.set_status(0, hp=98, mp=90)
    runner.set_hand(0, [smile_drop_id, romance_wood_id])

    # スマイルのしずく(HP+5)を使用 -> 99で止まるか
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    runner.step(ActionType.ACTION_TARGET_SELF)

    assert runner.state.get_hp(0) == 99

    # ターンが移るので戻すか、そのまま相手(1)のターンとしてテストを続けるか。
    # SimulationRunnerで強制的に自分のターンに戻す
    runner.state.current_actor_id = 0
    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN

    # ロマンスの香木(MP+15)を使用 -> 99で止まるか
    runner.step(ActionType.ACTION_SELECT_HAND_1)
    runner.step(ActionType.ACTION_TARGET_SELF)

    assert runner.state.get_mp(0) == 99
