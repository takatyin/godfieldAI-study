import pytest
import godfield_core
from godfield_core import GamePhase, Element, ActionType
from tests.core.test_utils import SimulationRunner, find_card_by_name

def create_game_with_hand(card_ids):
    """P0の手札を指定したカードID群で固定し、十分なリソース(MP/Money)を持たせたテスト環境を作成"""
    sim = SimulationRunner()
    sim.set_status(player=0, hp=40, mp=50, money=99)
    sim.set_status(player=1, hp=40, mp=50, money=99)
    sim.set_hand(0, card_ids)
    return sim, sim.state

def test_staging_naginata_and_wand_of_ignition():
    """無属性武器（なぎなたクラシック ID 23, 攻7）＋発火のワンド (ID 63, 攻2) の仮置き即時計算テスト"""
    sim, state = create_game_with_hand([23, 63])
    
    # 1. なぎなたクラシックを仮置き
    sim.step(ActionType.ACTION_SELECT_HAND_0)
    assert state.pending_attack_power == 7
    assert state.pending_attack_element == Element.ELEM_NONE
    
    # 2. 発火のワンドを重ねて仮置き ➔ 即座に火属性(ELEM_FIRE)へ染まることをアサート！
    sim.step(ActionType.ACTION_SELECT_HAND_1)
    assert state.pending_attack_power == 9
    assert state.pending_attack_element == Element.ELEM_FIRE

def test_staging_naginata_and_normal_fire_sword():
    """無属性武器（なぎなたクラシック ID 23, 攻7）＋弓 (ID 6, 攻1) の仮置き即時計算テスト"""
    sim, state = create_game_with_hand([23, 6])
    
    # 1. なぎなたクラシックを仮置き
    sim.step(ActionType.ACTION_SELECT_HAND_0)
    assert state.pending_attack_power == 7
    assert state.pending_attack_element == Element.ELEM_NONE
    
    # 2. 弓を重ねて仮置き ➔ 攻撃力が合算されて 8 になることをアサート！
    sim.step(ActionType.ACTION_SELECT_HAND_1)
    assert state.pending_attack_power == 8
    assert state.pending_attack_element == Element.ELEM_NONE

def test_staging_magical_stick():
    """マジカルステッキ (ID 55) 仮置き時に後続のMP消費カード追加でリアルタイム再計算されるかのテスト"""
    sim, state = create_game_with_hand([55, 214])  # マジカルステッキ (ID 55), 流星 (ID 214, MP 7, 攻10)
    sim.set_status(0, hp=40, mp=10)  # 初期 MP=10
    
    # 1. マジカルステッキを仮置き ➔ 他のMP消費0。残存 MP10 * 2 = 20 の攻撃力！
    sim.step(ActionType.ACTION_SELECT_HAND_0)
    assert state.pending_attack_power == 20
    assert state.pending_attack_element == Element.ELEM_NONE
    
    # 2. <流星> (ID 214, MP 7, 攻10) を重ねて仮置き
    # ➔ 流星の MP 7 消費により、マジカルステッキで使える残存 MP が (10 - 7) = 3 に減少！
    # ➔ マジカルステッキ (3 * 2 = 6) + 流星 (10) = 合計攻撃力 16 に即座に再計算されることを確認！
    sim.step(ActionType.ACTION_SELECT_HAND_1)
    assert state.pending_attack_power == 16

def test_staging_armor_defense_power():
    """防具重ねがけ仮置き時の合計防御力計算テスト (ID 115: 革の服 守2, ID 120: アイアンガントレット 守3)"""
    sim, state = create_game_with_hand([115, 120])
    
    # 防御フェーズ設定
    state.current_phase = GamePhase.PHASE_DEFENSE
    state.defender_id = 0
    state.attacker_id = 1
    state.current_actor_id = 0
    state.pending_attack_power = 20  # 飛んできている攻撃
    state.pending_attack_element = Element.ELEM_NONE  # 無属性物理攻撃
    state.pending_attack_source_id = 23  # なぎなたクラシックからの物理攻撃
    
    # 1. 防具1 (ID 115, 守2) を仮置き
    sim.step(ActionType.ACTION_SELECT_HAND_0)
    assert state.pending_defense_power == 2
    
    # 2. 防具2 (ID 120, 守3) を重ねて仮置き ➔ 合計防御力 5 になることをアサート！
    sim.step(ActionType.ACTION_SELECT_HAND_1)
    assert state.pending_defense_power == 5

def test_staging_sell_price_zero_yen_item():
    """0円アイテム（昇天の弓 ID 109）売却仮置き時の ¥0 表示保証テスト (ID 1: 売る)"""
    sim, state = create_game_with_hand([1, 109])
    
    # 1. 「売る」を仮置き
    sim.step(ActionType.ACTION_SELECT_HAND_0)
    assert state.pending_sell_price == 0
    
    # 2. 昇天の弓を売却対象として仮置き ➔ pending_sell_price が 0 として提示されることをアサート！
    sim.step(ActionType.ACTION_SELECT_HAND_1)
    assert state.pending_sell_price == 0

def test_staging_blaze_blade_meteor_fireball():
    """ブレイズブレイド(攻5, 火) ＋ 流星(攻10, 火) ＋ 火の玉(攻2, 火) の都度計算アサート"""
    sim, state = create_game_with_hand([79, 214, 207])
    
    # 1. ブレイズブレイド (ID 79, 攻5, 火)
    sim.step(ActionType.ACTION_SELECT_HAND_0)
    assert state.pending_attack_power == 5
    assert state.pending_attack_element == Element.ELEM_FIRE
    
    # 2. <流星> (ID 214, 攻10, 火)
    sim.step(ActionType.ACTION_SELECT_HAND_1)
    assert state.pending_attack_power == 15
    assert state.pending_attack_element == Element.ELEM_FIRE
    
    # 3. <火の玉> (ID 207, 攻2, 火)
    sim.step(ActionType.ACTION_SELECT_HAND_2)
    assert state.pending_attack_power == 17
    assert state.pending_attack_element == Element.ELEM_FIRE

def test_staging_complex_javelin_wand_mirage_combination():
    """
    ユーザー提示の超複雑コンボ検証 (蜃気楼による全体攻撃化および後置き発火のワンド属性上書きを含む):
    旧石器ジャベリン (土5) ➔ 魔水のワンド (水5) ➔ <流星> (光10) ➔ <蜃気楼> (全体化) ➔ 発火のワンド (火2) ➔ <オーラ> (倍率2)
    """
    sim, state = create_game_with_hand([81, 80, 214, 229, 63, 228])
    
    # 1. 旧石器ジャベリン (ID 81, 攻5, 土) ➔ 攻5, 土, 単体攻撃
    sim.step(ActionType.ACTION_SELECT_HAND_0)
    assert state.pending_attack_power == 5
    assert state.pending_attack_element == Element.ELEM_STONE
    assert state.pending_is_group_attack is False
    
    # 2. 魔水のワンド (ID 80, 攻5, 水) ➔ 水に染まり 攻10, 単体攻撃
    sim.step(ActionType.ACTION_SELECT_HAND_1)
    assert state.pending_attack_power == 10
    assert state.pending_attack_element == Element.ELEM_WATER
    assert state.pending_is_group_attack is False
    
    # 3. <流星> (ID 214, 攻10, 光) ➔ 魔水のワンドにより後置きの流星(光)も水に染まり 攻20, 単体攻撃
    sim.step(ActionType.ACTION_SELECT_HAND_2)
    assert state.pending_attack_power == 20
    assert state.pending_attack_element == Element.ELEM_WATER
    assert state.pending_is_group_attack is False
    
    # 4. <蜃気楼> (ID 229, 全体攻撃化, 無属性) ➔ 攻20 ＆ 無属性カード(<蜃気楼>)混入により無属性(ELEM_NONE)化 ＆ 【全体攻撃(pending_is_group_attack = True)に変化！】
    sim.step(ActionType.ACTION_SELECT_HAND_3)
    assert state.pending_attack_power == 20
    assert state.pending_attack_element == Element.ELEM_NONE
    assert state.pending_is_group_attack is True
    
    # 5. 発火のワンド (ID 63, 攻2, 火) ➔ 20 + 2 = 攻22 ＆ 【火属性(ELEM_FIRE)に染まり上書き！】 ＆ 【全体攻撃継続！】
    sim.step(ActionType.ACTION_SELECT_HAND_4)
    assert state.pending_attack_power == 22
    assert state.pending_attack_element == Element.ELEM_FIRE
    assert state.pending_is_group_attack is True
    
    # 6. <オーラ> (ID 228, 倍率2, 無属性) ➔ 22 * 2 = 攻44 ＆ 無属性カード(<オーラ>)混入により再度無属性(ELEM_NONE)化！ ＆ 【全体攻撃継続！】
    sim.step(ActionType.ACTION_SELECT_HAND_5)
    assert state.pending_attack_power == 44
    assert state.pending_attack_element == Element.ELEM_NONE
    assert state.pending_is_group_attack is True
