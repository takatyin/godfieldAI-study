# -*- coding: utf-8 -*-
import pytest
import godfield_core
import visualize_server
from tests.core.test_utils import SimulationRunner, find_card_by_name
from visualize_server import serialize_observation, compute_staged_total_badge, compute_smart_action_label


def test_visualize_card_power_label_sell_mode():
    """
    検証内容: 売却モード中において、全カードタイプ（武器・防具・雑貨・奇跡等）の
    power_label に価格（例: '¥4'）が正しく付与されることをテスト。
    """
    runner = SimulationRunner()
    visualize_server.state = runner.state

    wood_shield_id = find_card_by_name("armor/wood-shield") # price=4
    ogre_gauntlet_id = find_card_by_name("armor/ogre-s-gauntlet") # price=15

    runner.set_status(0, hp=40, mp=20)
    runner.set_status(1, hp=40, mp=20)

    runner.state.set_true_hand(0, 0, wood_shield_id)
    runner.state.set_true_hand(0, 1, ogre_gauntlet_id)

    # 売却フェイズ PHASE_SELL_SELECT に遷移させる
    runner.state.current_phase = godfield_core.GamePhase.PHASE_SELL_SELECT
    runner.state.current_actor_id = 0

    obs = godfield_core.get_observation(runner.state, 0)
    data = serialize_observation(obs, player_id=0)

    hand = data["hand"]
    # 木の盾 (price=4) -> '¥4'
    assert hand[0]["power_label"] == "¥4"
    # 鬼の小手 (price=15) -> '¥15'
    assert hand[1]["power_label"] == "¥15"


def test_visualize_reaction_shields_1st_vs_2nd_card():
    """
    検証内容: 奇跡防御フェイズにおいて、
    - 1枚目のリアクション防具（スカイガントレット）は '弾く' と表示されること。
    - 2枚目に重ね出し、または他防具の後に出すと '守3' (防御力) にフォールバックされること。
    """
    runner = SimulationRunner()
    visualize_server.state = runner.state

    fire_miracle_id = find_card_by_name("miracles/flame")
    sky_gauntlet_id = find_card_by_name("armor/sky-gauntlet") # reaction: bounce, def: 3
    sky_boots_id = find_card_by_name("armor/sky-boots") # reaction: bounce, def: 1

    runner.set_status(0, hp=40, mp=20)
    runner.set_status(1, hp=40, mp=20)

    runner.state.set_true_hand(0, 0, fire_miracle_id)
    runner.state.set_true_hand(1, 0, sky_gauntlet_id)
    runner.state.set_true_hand(1, 1, sky_boots_id)

    # P0が＜炎＞でP1に奇跡攻撃
    runner.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
    runner.step(godfield_core.ActionType.ACTION_TARGET_OPP)

    # 1. まだ何も仮置きしていない状態：スカイガントレット(手札0)は '弾く'
    obs1 = godfield_core.get_observation(runner.state, 1)
    data1 = serialize_observation(obs1, player_id=1)
    assert data1["hand"][0]["power_label"] == "弾く"

    # P1が先にスカイガントレット(スロット0)を選択・仮置き
    runner.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)

    # 2. スカイガントレットが1枚目に置かれた状態：2枚目となるスカイブーツ(手札に残るスロット1)は '守1'
    obs2 = godfield_core.get_observation(runner.state, 1)
    data2 = serialize_observation(obs2, player_id=1)

    sky_boots_in_hand = next(c for c in data2["hand"] if c["id"] == sky_boots_id)
    assert sky_boots_in_hand["power_label"] == "守1"


def test_visualize_reaction_shield_physical_vs_miracle_defense():
    """
    検証内容:
    - 物理防御フェイズ (PHASE_DEFENSE) ではスカイガントレットは物理を弾けないため '守3' と表示されること。
    - 奇跡防御フェイズ (PHASE_MIRACLE_DEFENSE) でのみ '弾く' と表示されること。
    """
    runner = SimulationRunner()
    visualize_server.state = runner.state

    sword_id = find_card_by_name("weapons/plate-of-strike") # 物理攻撃
    sky_gauntlet_id = find_card_by_name("armor/sky-gauntlet") # reaction: bounce, def: 3

    runner.set_status(0, hp=40, mp=20)
    runner.set_status(1, hp=40, mp=20)

    runner.state.set_true_hand(0, 0, sword_id)
    runner.state.set_true_hand(1, 0, sky_gauntlet_id)

    # P0が物理攻撃
    runner.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
    runner.step(godfield_core.ActionType.ACTION_TARGET_OPP)

    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE

    # 物理防御フェイズ：スカイガントレットは物理を弾けないため '守3' と表示！
    obs = godfield_core.get_observation(runner.state, 1)
    data = serialize_observation(obs, player_id=1)
    assert data["hand"][0]["power_label"] == "守3"


def test_visualize_spiritual_zero_mp_label():
    """
    検証内容: 精霊系カード（精霊の杖等）は:
    - 仮置き場に何も置かれていない時や奇跡以外が置かれている時は標準ラベル（例: '攻12'）が表示されること。
    - 仮置き場の最後のカードが奇跡（＜炎＞等）である時（奇跡プラスフェイズ）にのみ '消費0' のラベルが表示されること。
    """
    runner = SimulationRunner()
    visualize_server.state = runner.state

    fire_miracle_id = find_card_by_name("miracles/flame")
    spirit_staff_id = find_card_by_name("weapons/spiritual-staff")

    runner.set_status(0, hp=40, mp=20)
    runner.set_status(1, hp=40, mp=20)

    runner.state.set_true_hand(0, 0, fire_miracle_id)
    runner.state.set_true_hand(0, 1, spirit_staff_id)

    # 1. 仮置き場が空の状態（PHASE_MAIN）：精霊の杖は '攻12' と表示！
    obs1 = godfield_core.get_observation(runner.state, 0)
    data1 = serialize_observation(obs1, player_id=0)
    staff_card_main = next(c for c in data1["hand"] if c["id"] == spirit_staff_id)
    assert staff_card_main["power_label"] == "攻12"

    # 2. P0が＜炎＞(スロット0)を仮置きして奇跡プラスフェイズに遷移
    runner.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)

    # 3. 仮置き場の最後が奇跡＜炎＞となった状態：精霊の杖が '消費0' に変化！
    obs2 = godfield_core.get_observation(runner.state, 0)
    data2 = serialize_observation(obs2, player_id=0)
    staff_card_plus = next(c for c in data2["hand"] if c["id"] == spirit_staff_id)
    assert staff_card_plus["power_label"] == "消費0"


def test_visualize_attack_plus_labels():
    """
    検証内容: 攻撃プラスフェイズ (PHASE_ATTACK_PLUS) において、
    ちからの粉 (+攻10) や 鬼の小手 (+攻10/防御兼) や ＜オーラ＞ (2倍)、＜蜃気楼＞ (全体) の
    power_label が正確に算出されるかをテスト。
    """
    runner = SimulationRunner()
    visualize_server.state = runner.state

    sword_id = find_card_by_name("weapons/plate-of-strike") # 物理攻撃
    powder_id = find_card_by_name("sundries/strength-powder") # +攻10
    aura_id = find_card_by_name("miracles/aura") # 2倍
    mirage_id = find_card_by_name("miracles/mirage") # 全体

    runner.set_status(0, hp=40, mp=20)
    runner.set_status(1, hp=40, mp=20)

    runner.state.set_true_hand(0, 0, sword_id)
    runner.state.set_true_hand(0, 1, powder_id)
    runner.state.set_true_hand(0, 2, aura_id)
    runner.state.set_true_hand(0, 3, mirage_id)

    # P0が打撃の鉄板を出して攻撃プラスフェイズへ移行
    runner.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_ATTACK_PLUS

    obs = godfield_core.get_observation(runner.state, 0)
    data = serialize_observation(obs, player_id=0)

    # 手札の各プラスアイテムの表示ラベルを確認
    powder_card = next(c for c in data["hand"] if c["id"] == powder_id)
    aura_card = next(c for c in data["hand"] if c["id"] == aura_id)
    mirage_card = next(c for c in data["hand"] if c["id"] == mirage_id)

    assert powder_card["power_label"] == "+攻10"
    assert aura_card["power_label"] == "2倍"
    assert mirage_card["power_label"] == "全体"


def test_visualize_dual_use_cards_defense_badge():
    """
    検証内容: ソードシールドや打撃の鉄板などの攻撃・防御両用カードを
    防御フェイズで仮置きした際、合計バッジ (compute_staged_total_badge) に
    防御力が正しく合算されて表示されるかをテスト。
    """
    runner = SimulationRunner()
    visualize_server.state = runner.state

    sword_id = find_card_by_name("weapons/plate-of-strike") # ATK 5
    sword_shield_id = find_card_by_name("weapons/sword-shield") # Def 10, Atk 5

    runner.set_status(0, hp=40, mp=20)
    runner.set_status(1, hp=40, mp=20)

    runner.state.set_true_hand(0, 0, sword_id)
    runner.state.set_true_hand(1, 0, sword_shield_id)

    # P0が攻撃
    runner.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
    runner.step(godfield_core.ActionType.ACTION_TARGET_OPP)

    # P1がソードシールド(スロット0)を仮置き
    runner.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)

    # 仮置き合計バッジの算出結果を確認
    obs = godfield_core.get_observation(runner.state, 1)
    staged_cids = [cid for cid in obs.get_staged_cards() if cid != -1]
    staged_info = [visualize_server.cards_by_id.get(cid) for cid in staged_cids]

    badge = compute_staged_total_badge(staged_info, player_id=1, game_state=runner.state)
    assert badge is not None
    assert badge["label"] == "守10"


def test_visualize_smart_action_labels():
    """
    検証内容: アクションID（ターゲット選択、購入、確定、売却等）における
    コンテキスト対応スマートラベル (compute_smart_action_label) をテスト。
    """
    runner = SimulationRunner()
    visualize_server.state = runner.state

    # 1. 買戻しフェイズ PHASE_BUY
    runner.state.current_phase = godfield_core.GamePhase.PHASE_BUY
    label = compute_smart_action_label(18, [], runner.state)
    assert label == "買う"

    # 2. 売却選択フェイズ PHASE_SELL_SELECT
    runner.state.current_phase = godfield_core.GamePhase.PHASE_SELL_SELECT
    label = compute_smart_action_label(18, [], runner.state)
    assert label == "承諾"

    # 3. 捨てるアクション
    label = compute_smart_action_label(21, [], runner.state)
    assert label == "捨てる"


def test_visualize_ogre_helm_phase_labels():
    """
    検証内容: 防具タイプ兼攻撃プラスカードである「鬼のかぶと」(Def 7, Atk 10, timing: atk_defence_phase, atk_plus_phase) が:
    - PHASE_MAIN（メインフェイズ・最初の手番）では '守7' と表示されること。
    - PHASE_ATTACK_PLUS（攻撃プラスフェイズ）に遷移したタイミングで初めて '+攻10' に切り替わること。
    """
    runner = SimulationRunner()
    visualize_server.state = runner.state

    sword_id = find_card_by_name("weapons/plate-of-strike") # 物理攻撃
    ogre_helm_id = find_card_by_name("armor/ogre-s-helm") # Def 7, Atk 10 (+攻10)

    runner.set_status(0, hp=40, mp=20)
    runner.set_status(1, hp=40, mp=20)

    runner.state.set_true_hand(0, 0, sword_id)
    runner.state.set_true_hand(0, 1, ogre_helm_id)

    # 1. PHASE_MAIN フェイズ（手番開始時）：鬼のかぶとは単体攻撃としては使えないため '守7' と表示！
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_MAIN
    obs1 = godfield_core.get_observation(runner.state, 0)
    data1 = serialize_observation(obs1, player_id=0)

    ogre_card_main = next(c for c in data1["hand"] if c["id"] == ogre_helm_id)
    assert ogre_card_main["power_label"] == "守7"

    # 2. P0が打撃の鉄板を出して PHASE_ATTACK_PLUS へ遷移
    runner.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_ATTACK_PLUS

    # PHASE_ATTACK_PLUS フェイズ：鬼のかぶとが '+攻10' に表示変化！
    obs2 = godfield_core.get_observation(runner.state, 0)
    data2 = serialize_observation(obs2, player_id=0)

    ogre_card_plus = next(c for c in data2["hand"] if c["id"] == ogre_helm_id)
    assert ogre_card_plus["power_label"] == "+攻10"
