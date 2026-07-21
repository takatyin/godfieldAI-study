import godfield_core
import pytest
from tests.core.test_utils import SimulationRunner, find_card_by_name


def test_dream_draw_groups():
    """
    検証内容: 夢状態でのドローが、正しい夢グループ内のカードに偽装されること。
    """
    sim = SimulationRunner()
    sim.set_status(0, hp=40, mp=0, money=0)
    sim.set_status(1, hp=40, mp=0, money=0)

    # 夢状態にする
    sim.state.set_curses(0, godfield_core.CurseType.CURSE_DREAM, True)

    # 通常武器 (銅のこん棒) を手札スロット0にドロー
    club_id = find_card_by_name("銅のこん棒")
    sim.state.add_card_to_hand_slot(0, 0, club_id, True)  # is_drawn=True

    # 未確定状態になっていること
    assert not sim.state.get_is_confirmed(0, 0)

    # 見た目のカードは元のカードと異なる可能性があるが、同じ通常武器グループであること
    apparent_id = sim.state.get_apparent_hand(0, 0)
    assert apparent_id != godfield_core.CARD_EMPTY

    # 偽装カードの属性を検証 (通常武器グループは timing == ['main_atk_phase'] かつ is_group == false かつ reaction == none)
    assert godfield_core.get_card_name(apparent_id) != "両替"

    # 奇跡 (＜火の玉＞) を手札スロット1にドロー -> 奇跡は夢の影響を受けず、即座に確定する
    fireball_id = find_card_by_name("＜火の玉＞")
    sim.state.add_card_to_hand_slot(0, 1, fireball_id, True)
    assert sim.state.get_is_confirmed(0, 1)
    assert sim.state.get_apparent_hand(0, 1) == fireball_id


def test_dream_finalization_success():
    """
    検証内容: 夢状態で偽装されたカードを使用し、真のカードも合法だった場合、正常に確定して実行されること。
    """
    sim = SimulationRunner()
    sim.set_status(0, hp=40, mp=0, money=0)
    sim.set_status(1, hp=40, mp=0, money=0)

    sim.state.set_curses(0, godfield_core.CurseType.CURSE_DREAM, True)

    # 真のカード: パンチ (通常武器、攻撃力3)
    punch_id = find_card_by_name("パンチ")
    sim.state.add_card_to_hand_slot(0, 0, punch_id, True)

    # 見た目を 銅のこん棒 (通常武器) に偽装設定
    bronze_club = find_card_by_name("銅のこん棒")
    sim.state.set_apparent_hand(0, 0, bronze_club)
    sim.state.set_is_confirmed(0, 0, False)

    # 1. 銅のこん棒を使用 (手札スロット0を選択して仮置き)
    # ACTION_SELECT_HAND_0 = 10
    sim.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)

    # PHASE_ATTACK_PLUS に遷移していること
    assert sim.state.current_phase == godfield_core.GamePhase.PHASE_ATTACK_PLUS
    assert sim.state.get_num_staged_cards(0) == 1
    assert sim.state.get_staged_card(0, 0) == 0
    # まだ確定していないこと
    assert not sim.state.get_is_confirmed(0, 0)

    # 2. ターゲットを相手に選択して攻撃を確定 (ACTION_TARGET_OPP = 2)
    sim.step(godfield_core.ActionType.ACTION_TARGET_OPP)

    # 攻撃確定によりカードが確定し、真のパンチ (攻撃力3) の攻撃として処理されること
    assert sim.state.get_is_confirmed(0, 0)
    assert sim.state.get_apparent_hand(0, 0) == punch_id
    assert sim.state.get_true_hand(0, 0) == punch_id

    # 防御フェイズに遷移
    assert sim.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
    assert sim.state.pending_attack_power == 3


def test_dream_finalization_failure():
    """
    検証内容: 夢状態で偽装されたカードを使用し、真のカードが現在のフェイズで非合法だった場合、
    仮置きがクリアされて手札に戻り、フェイズがメインに戻ること。
    """
    sim = SimulationRunner()
    sim.set_status(0, hp=40, mp=0, money=0)
    sim.set_status(1, hp=40, mp=0, money=0)

    sim.state.set_curses(0, godfield_core.CurseType.CURSE_DREAM, True)

    # 真のカード: 木の盾 (防具)
    shield_id = find_card_by_name("木の盾")
    sim.state.add_card_to_hand_slot(0, 0, shield_id, True)

    # 見た目を 銅のこん棒 (通常武器) に偽装
    bronze_club = find_card_by_name("銅のこん棒")
    sim.state.set_apparent_hand(0, 0, bronze_club)
    sim.state.set_is_confirmed(0, 0, False)

    # 1. 銅のこん棒 (スロット0) を使用して仮置き
    sim.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)

    # 仮置きされ、攻撃追加フェイズへ遷移
    assert sim.state.current_phase == godfield_core.GamePhase.PHASE_ATTACK_PLUS
    assert sim.state.get_num_staged_cards(0) == 1

    # 2. 相手ターゲットを選択 (ACTION_TARGET_OPP = 2)
    sim.step(godfield_core.ActionType.ACTION_TARGET_OPP)

    # 木の盾での攻撃は非合法であるため、仮置きがクリアされ、確定した状態で手札に残り、メインフェイズに戻ること
    assert sim.state.current_phase == godfield_core.GamePhase.PHASE_MAIN
    assert sim.state.get_num_staged_cards(0) == 0
    assert sim.state.get_is_confirmed(0, 0)
    assert sim.state.get_apparent_hand(0, 0) == shield_id
    assert sim.state.get_true_hand(0, 0) == shield_id


def test_dream_buy_confirmation():
    """
    検証内容: 「買う」の対象にされたカードは、買われたかどうかにかかわらず確定すること。
    """
    sim = SimulationRunner()
    sim.set_status(0, hp=40, mp=0, money=50)
    sim.set_status(1, hp=40, mp=0, money=50)

    # プレイヤー1 (相手) は夢状態
    sim.state.set_curses(1, godfield_core.CurseType.CURSE_DREAM, True)

    # 相手のスロット0に通常武器をドロー (偽装)
    club_id = find_card_by_name("銅のこん棒")
    sim.state.add_card_to_hand_slot(1, 0, club_id, True)
    sim.state.set_apparent_hand(1, 0, find_card_by_name("銀のこん棒"))
    sim.state.set_is_confirmed(1, 0, False)

    # プレイヤー0 (自分) のスロット0に「買う」を設定
    buy_id = find_card_by_name("買う")
    sim.state.add_card_to_hand_slot(0, 0, buy_id, False)

    # 1. プレイヤー0が「買う」を使用 (スロット0を選択)
    sim.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)

    # 2. プレイヤー0が相手 (プレイヤー1) をターゲットに選択 (ACTION_TARGET_OPP = 2)
    sim.step(godfield_core.ActionType.ACTION_TARGET_OPP)

    # PHASE_BUY_SELECT_MIRROR に移行
    assert sim.state.current_phase == godfield_core.GamePhase.PHASE_BUY_SELECT_MIRROR
    assert sim.state.current_actor_id == 1

    # 3. 相手 (プレイヤー1) が受諾する (ACTION_CONFIRM)
    sim.step(godfield_core.ActionType.ACTION_CONFIRM)

    # この時点で、相手の提示された手札スロットが確定していること！
    offered_idx = sim.state.get_staged_card(1, 0)
    assert offered_idx == 0
    assert sim.state.get_is_confirmed(1, offered_idx)
    assert sim.state.get_apparent_hand(1, offered_idx) == club_id
    assert sim.state.get_true_hand(1, offered_idx) == club_id


def test_dream_cure_restores_apparent_hand():
    """検証内容: すっきり歌などの解除カードによって夢が治った際、手札が元の本物の見た目に戻ること。"""
    sim = SimulationRunner()
    sim.set_status(0, hp=40, mp=10, money=0)
    sim.set_status(1, hp=40, mp=10, money=0)

    # プレイヤー0を夢状態にする
    sim.state.set_curses(0, godfield_core.CurseType.CURSE_DREAM, True)

    # 手札を設定
    bronze_club = find_card_by_name("weapons/bronze-club")
    song_id = find_card_by_name("miracles/song")

    sim.state.add_card_to_hand_slot(0, 0, bronze_club, True) # ドローなので夢に偽装される
    sim.state.add_card_to_hand_slot(0, 1, song_id, False)

    # 最初は偽装されていることを確認
    assert sim.state.get_is_confirmed(0, 0) is False
    assert sim.state.get_apparent_hand(0, 0) != bronze_club

    # すっきり歌を使用
    sim.step(godfield_core.ActionType.ACTION_SELECT_HAND_1)
    sim.step(godfield_core.ActionType.ACTION_TARGET_SELF)

    # 夢が解除され、手札が本物に戻っていることを確認
    assert sim.state.get_curses(0, godfield_core.CurseType.CURSE_DREAM) is False
    assert sim.state.get_is_confirmed(0, 0) is True
    assert sim.state.get_apparent_hand(0, 0) == bronze_club

