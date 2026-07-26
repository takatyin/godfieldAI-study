import godfield_core
from godfield_core import ActionType
from tests.core.test_utils import find_card_by_name


def test_pray_action_transitions_actor(sim):
    """
    検証内容: 「祈る」実行時のアクター（手番）交代テスト。
    - 「祈る」を選択してアクションを実行した際、手番プレイヤー（アクター）が相手（プレイヤー1）に交代することを確認します。
    """
    sim.reset_state()
    sim.set_hand(0, [])

    # 祈るを実行
    sim.step(ActionType.ACTION_PRAY)

    # アクターが相手(1)に交代していることを確認
    assert sim.state.current_actor_id == 1


def test_pray_action_draws_card(sim):
    """
    検証内容: 「祈る」実行時のカードドロー処理テスト。
    - 「祈る」を実行すると、山札からカードが1枚手札の空き枠（スロット0）にドローされることを確認します。
    - ドローされたカードは未使用状態（is_used = False）であることを確認します。
    """
    sim.reset_state()
    sim.set_hand(0, [])

    # 祈るを実行
    sim.step(ActionType.ACTION_PRAY)

    # 空だったスロット0にカードがドローされていることを確認
    assert sim.state.get_true_hand(0, 0) != godfield_core.CARD_EMPTY
    # ドローされたカードは未使用状態であることを確認
    assert not sim.state.get_is_used(0, 0)


def test_discard_action_availability(sim):
    """
    検証内容: メインフェイズにおける「捨てる」アクションの合法性テスト。
    - メインフェイズ（PHASE_MAIN）において、「捨てる（ACTION_DISCARD）」アクションが合法手となることを確認します。
    - メインフェイズにおいて、防具（革の服）を直接選択することは非合法（直接使用できない）であり、武器（パンチ）は直接選択可能であることを確認します。
    """
    shield_id = find_card_by_name("革の服")
    weapon_id = find_card_by_name("パンチ")
    sun_amulet_id = find_card_by_name("太陽のお守り")

    sim.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    sim.state.current_actor_id = 0

    sim.state.set_true_hand(0, 0, shield_id)  # スロット0: 盾
    sim.state.set_true_hand(0, 1, weapon_id)  # スロット1: 武器
    sim.state.set_true_hand(0, 2, sun_amulet_id)  # スロット2: お守り

    actions = godfield_core.get_legal_actions(sim.state)

    # 捨てるアクション自体は選択可能であること
    assert actions[ActionType.ACTION_DISCARD] is True
    # 防具（スロット0）はお守り（スロット2）と同様に直接メインフェイズで選択不可であること
    assert actions[ActionType.ACTION_SELECT_HAND_0] is False
    assert actions[ActionType.ACTION_SELECT_HAND_2] is False
    # 武器（スロット1）は直接メインフェイズで選択可能（攻撃のため）であること
    assert actions[ActionType.ACTION_SELECT_HAND_1] is True


def test_discard_phase_selection_rules(sim):
    """
    検証内容: 破棄フェイズにおけるカード選択制限ルール。
    - 破棄フェイズ（PHASE_DISCARD）に移行後、防具（スロット0）は破棄対象として選択可能となることを確認します。
    - 武器（スロット1）や奇跡・お守り（スロット2）は破棄不可（非合法）であることを確認します。
    - 何も選択していない状態では「確定（ACTION_CONFIRM）」が非合法であることを確認します。
    """
    shield_id = find_card_by_name("革の服")
    weapon_id = find_card_by_name("パンチ")
    sun_amulet_id = find_card_by_name("太陽のお守り")

    sim.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    sim.state.current_actor_id = 0

    sim.state.set_true_hand(0, 0, shield_id)
    sim.state.set_true_hand(0, 1, weapon_id)
    sim.state.set_true_hand(0, 2, sun_amulet_id)

    # 破棄フェイズへ遷移
    sim.step(action=ActionType.ACTION_DISCARD)
    assert sim.state.current_phase == godfield_core.GamePhase.PHASE_DISCARD

    actions_discard = godfield_core.get_legal_actions(sim.state)

    # 防具（スロット0）のみが選択可能であること
    assert actions_discard[ActionType.ACTION_SELECT_HAND_0] is True
    assert actions_discard[ActionType.ACTION_SELECT_HAND_1] is False
    assert actions_discard[ActionType.ACTION_SELECT_HAND_2] is False
    # 未選択時は確定不可であること
    assert actions_discard[ActionType.ACTION_CONFIRM] is False


def test_discard_confirm_executes_discard(sim):
    """
    検証内容: 破棄の確定とスロット空化のテスト。
    - 破棄フェイズで防具を選択すると、「確定」アクションが合法手となることを確認します。
    - 確定を実行すると、選択したスロットが空（CARD_EMPTY）になり、使用済みフラグ（is_used）は False のまま（次のターンエンド時にドロー補填されない）になることを確認します。
    """
    shield_id = find_card_by_name("革の服")

    sim.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    sim.state.current_actor_id = 0
    sim.state.set_true_hand(0, 0, shield_id)

    # 破棄フェイズへ遷移し、防具を選択
    sim.step(action=ActionType.ACTION_DISCARD)
    sim.step(action=ActionType.ACTION_SELECT_HAND_0)

    actions_staged = godfield_core.get_legal_actions(sim.state)
    assert actions_staged[ActionType.ACTION_CONFIRM] is True

    # 確定実行
    sim.step(action=ActionType.ACTION_CONFIRM)

    # スロットが空になり、かつ is_used は False のままであることを確認
    assert sim.state.get_true_hand(0, 0) == godfield_core.CARD_EMPTY
    assert sim.state.get_is_used(0, 0) is False


def test_discard_action_available_and_executes_for_deployed_miracles(sim):
    """
    検証内容: 展開済みの奇跡のみの場合に「捨てる」アクションが合法手になり、かつ正常に破棄できるかのテスト。
    - 手札に展開済みの奇跡（例: 雷）しかない場合でも、メインフェイズで「捨てる（ACTION_DISCARD）」アクションが合法手となることを確認します。
    - 破棄フェイズで展開済みの奇跡を選択して確定すると、スロットが空になり、展開フラグ（is_deployed）が解除されることを確認します。
    """
    thunder_id = find_card_by_name("＜雷＞")

    sim.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    sim.state.current_actor_id = 0

    # スロット0に雷を設定し、展開済み(is_deployed = True)にする
    sim.state.set_true_hand(0, 0, thunder_id)
    sim.state.set_is_deployed(0, 0, True)

    # 他のスロットはすべて空
    for i in range(1, 18):
        sim.state.set_true_hand(0, i, godfield_core.CARD_EMPTY)

    actions = godfield_core.get_legal_actions(sim.state)

    # 展開済みの奇跡であっても捨てるアクションは合法であること
    assert actions[ActionType.ACTION_DISCARD] is True

    # 捨てるを選択
    sim.step(action=ActionType.ACTION_DISCARD)
    assert sim.state.current_phase == godfield_core.GamePhase.PHASE_DISCARD

    actions_discard = godfield_core.get_legal_actions(sim.state)
    # 展開済みの奇跡（スロット0）が破棄対象として選択可能であること
    assert actions_discard[ActionType.ACTION_SELECT_HAND_0] is True

    # スロット0を選択して確定する
    sim.step(action=ActionType.ACTION_SELECT_HAND_0)
    sim.step(action=ActionType.ACTION_CONFIRM)

    # スロットが空になり、かつ展開フラグも解除されていることを確認
    assert sim.state.get_true_hand(0, 0) == godfield_core.CARD_EMPTY
    assert sim.state.get_is_deployed(0, 0) is False
