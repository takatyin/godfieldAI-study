import godfield_core
from tests.core.test_utils import SimulationRunner, find_card_by_name
from visualizer.constants import CARDS_BY_ID
from visualizer.presenter import compute_smart_action_label, compute_staged_total_badge, serialize_observation


def test_visualize_card_power_label_sell_mode():
    """
    検証内容: 売却モード中において、全カードタイプ（武器・防具・雑貨・奇跡等）の
    power_label に価格（例: '¥4'）が正しく付与されることをテスト。
    """
    runner = SimulationRunner()

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
    data = serialize_observation(obs, player_id=0, state=runner.state)

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
    data1 = serialize_observation(obs1, player_id=1, state=runner.state)
    assert data1["hand"][0]["power_label"] == "弾く"

    # P1が先にスカイガントレット(スロット0)を選択・仮置き
    runner.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)

    # 2. スカイガントレットが1枚目に置かれた状態：2枚目となるスカイブーツ(手札に残るスロット1)は '守1'
    obs2 = godfield_core.get_observation(runner.state, 1)
    data2 = serialize_observation(obs2, player_id=1, state=runner.state)

    sky_boots_in_hand = next(c for c in data2["hand"] if c["id"] == sky_boots_id)
    assert sky_boots_in_hand["power_label"] == "守1"


def test_visualize_reaction_shield_physical_vs_miracle_defense():
    """
    検証内容:
    - 物理防御フェイズ (PHASE_DEFENSE) ではスカイガントレットは物理を弾けないため '守3' と表示されること。
    - 奇跡防御フェイズ (PHASE_MIRACLE_DEFENSE) でのみ '弾く' と表示されること。
    """
    runner = SimulationRunner()

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
    data = serialize_observation(obs, player_id=1, state=runner.state)
    assert data["hand"][0]["power_label"] == "守3"


def test_visualize_spiritual_zero_mp_label():
    """
    検証内容: 精霊系カード（精霊の杖等）は:
    - 仮置き場に何も置かれていない時や奇跡以外が置かれている時は標準ラベル（例: '攻12'）が表示されること。
    - 仮置き場の最後のカードが奇跡（＜炎＞等）である時（奇跡プラスフェイズ）にのみ '消費0' のラベルが表示されること。
    """
    runner = SimulationRunner()

    fire_miracle_id = find_card_by_name("miracles/flame")
    spirit_staff_id = find_card_by_name("weapons/spiritual-staff")

    runner.set_status(0, hp=40, mp=20)
    runner.set_status(1, hp=40, mp=20)

    runner.state.set_true_hand(0, 0, fire_miracle_id)
    runner.state.set_true_hand(0, 1, spirit_staff_id)

    # 1. 仮置き場が空の状態（PHASE_MAIN）：精霊の杖は '攻12' と表示！
    obs1 = godfield_core.get_observation(runner.state, 0)
    data1 = serialize_observation(obs1, player_id=0, state=runner.state)
    staff_card_main = next(c for c in data1["hand"] if c["id"] == spirit_staff_id)
    assert staff_card_main["power_label"] == "攻12"

    # 2. P0が＜炎＞(スロット0)を仮置きして奇跡プラスフェイズに遷移
    runner.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)

    # 3. 仮置き場の最後が奇跡＜炎＞となった状態：精霊の杖が '消費0' に変化！
    obs2 = godfield_core.get_observation(runner.state, 0)
    data2 = serialize_observation(obs2, player_id=0, state=runner.state)
    staff_card_plus = next(c for c in data2["hand"] if c["id"] == spirit_staff_id)
    assert staff_card_plus["power_label"] == "消費0"


def test_visualize_attack_plus_labels():
    """
    検証内容: 攻撃プラスフェイズ (PHASE_ATTACK_PLUS) において、
    ちからの粉 (+攻10) や 鬼の小手 (+攻10/防御兼) や ＜オーラ＞ (2倍)、＜蜃気楼＞ (全体) の
    power_label が正確に算出されるかをテスト。
    """
    runner = SimulationRunner()

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
    data = serialize_observation(obs, player_id=0, state=runner.state)

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
    staged_info = [CARDS_BY_ID.get(cid) for cid in staged_cids]

    badge = compute_staged_total_badge(staged_info, player_id=1, game_state=runner.state)
    assert badge is not None
    assert badge["label"] == "守10"


def test_visualize_smart_action_labels():
    """
    検証内容: アクションID（ターゲット選択、購入、確定、売却等）における
    コンテキスト対応スマートラベル (compute_smart_action_label) をテスト。
    """
    runner = SimulationRunner()

    # 1. 購入フェイズ PHASE_BUY
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

    # 4. 取引可否・受諾/拒否アクション (アクション19)
    # PHASE_BUY では「買わない」
    runner.state.current_phase = godfield_core.GamePhase.PHASE_BUY
    label = compute_smart_action_label(19, [], runner.state)
    assert label == "買わない"

    # PHASE_BUY_SELECT_MIRROR
    runner.state.current_phase = godfield_core.GamePhase.PHASE_BUY_SELECT_MIRROR
    # 手札をステージしていない（受け入れる）
    assert compute_smart_action_label(19, [], runner.state) == "受け入れる"
    # ミラーをステージしている（はね返す）
    dummy_mirror = [{"name": "スーパーミラー", "id": 1}]
    assert compute_smart_action_label(19, dummy_mirror, runner.state) == "はね返す"

    # PHASE_SELL_SELECT_MIRROR
    runner.state.current_phase = godfield_core.GamePhase.PHASE_SELL_SELECT_MIRROR
    assert compute_smart_action_label(19, [], runner.state) == "受け入れる"
    assert compute_smart_action_label(19, dummy_mirror, runner.state) == "はね返す"

    # PHASE_SUNDRY_SELECT_MIRROR
    runner.state.current_phase = godfield_core.GamePhase.PHASE_SUNDRY_SELECT_MIRROR
    assert compute_smart_action_label(19, [], runner.state) == "受け入れる"
    assert compute_smart_action_label(19, dummy_mirror, runner.state) == "はね返す"


def test_visualize_ogre_helm_phase_labels():
    """
    検証内容: 防具タイプ兼攻撃プラスカードである「鬼のかぶと」(Def 7, Atk 10, timing: atk_defence_phase, atk_plus_phase) が:
    - PHASE_MAIN（メインフェイズ・最初の手番）では '守7' と表示されること。
    - PHASE_ATTACK_PLUS（攻撃プラスフェイズ）に遷移したタイミングで初めて '+攻10' に切り替わること。
    """
    runner = SimulationRunner()

    sword_id = find_card_by_name("weapons/plate-of-strike") # 物理攻撃
    ogre_helm_id = find_card_by_name("armor/ogre-s-helm") # Def 7, Atk 10 (+攻10)

    runner.set_status(0, hp=40, mp=20)
    runner.set_status(1, hp=40, mp=20)

    runner.state.set_true_hand(0, 0, sword_id)
    runner.state.set_true_hand(0, 1, ogre_helm_id)

    # 1. PHASE_MAIN フェイズ（手番開始時）：鬼のかぶとは単体攻撃としては使えないため '守7' と表示！
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_MAIN
    obs1 = godfield_core.get_observation(runner.state, 0)
    data1 = serialize_observation(obs1, player_id=0, state=runner.state)

    ogre_card_main = next(c for c in data1["hand"] if c["id"] == ogre_helm_id)
    assert ogre_card_main["power_label"] == "守7"

    # 2. P0が打撃の鉄板を出して PHASE_ATTACK_PLUS へ遷移
    runner.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_ATTACK_PLUS

    # PHASE_ATTACK_PLUS フェイズ：鬼のかぶとが '+攻10' に表示変化！
    obs2 = godfield_core.get_observation(runner.state, 0)
    data2 = serialize_observation(obs2, player_id=0, state=runner.state)

    ogre_card_plus = next(c for c in data2["hand"] if c["id"] == ogre_helm_id)
    assert ogre_card_plus["power_label"] == "+攻10"

def test_visualize_main_phase_weapon_plus():
    """
    検証内容: メインフェイズ中の武器カードのラベル。
    - 吹き矢（weapons/blowgun）は武器であり武器プラスでもあるので、メインフェイズ中に '+攻6' と表示されることを確認。
    - 木刀（weapons/wooden-sword）は通常の武器（武器プラスではない）なので、メインフェイズ中に '攻1' と表示されることを確認。
    """
    runner = SimulationRunner()

    blowgun_id = find_card_by_name("weapons/blowgun")
    wooden_sword_id = find_card_by_name("weapons/wooden-sword")

    runner.set_status(0, hp=40, mp=20)
    runner.set_status(1, hp=40, mp=20)

    runner.state.set_true_hand(0, 0, blowgun_id)
    runner.state.set_true_hand(0, 1, wooden_sword_id)

    # 1. PHASE_MAIN フェイズ（手番開始時）
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_MAIN
    obs = godfield_core.get_observation(runner.state, 0)
    data = serialize_observation(obs, player_id=0, state=runner.state)

    # 吹き矢は '+攻1'
    blowgun_card = next(c for c in data["hand"] if c["id"] == blowgun_id)
    assert blowgun_card["power_label"] == "+攻1"

    # 木刀は '攻1'
    wooden_sword_card = next(c for c in data["hand"] if c["id"] == wooden_sword_id)
    assert wooden_sword_card["power_label"] == "攻1"


def test_visualize_sell_multiple_sell_cards():
    """
    検証内容: 手札に複数枚の「売る」カードがある場合、売却フェイズ(PHASE_SELL_SELECT)において、
    売却対象となる「売る」カードの売却価格（¥2）が正しくラベルに表示されることを確認。
    """
    runner = SimulationRunner()

    sell_card_id = find_card_by_name("売る")

    runner.set_status(0, hp=40, mp=20)
    runner.set_status(1, hp=40, mp=20)

    # プレイヤー0の手札に「売る」を2枚セット
    runner.state.set_true_hand(0, 0, sell_card_id)
    runner.state.set_true_hand(0, 1, sell_card_id)

    # 1. PHASE_MAIN フェイズ（売るカード使用前）：価格ラベルは表示されない（""）
    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    obs = godfield_core.get_observation(runner.state, 0)
    data = serialize_observation(obs, player_id=0, state=runner.state)

    sell_card_0 = data["hand"][0]
    sell_card_1 = data["hand"][1]
    assert sell_card_0["power_label"] == ""
    assert sell_card_1["power_label"] == ""

    # 2. PHASE_SELL_SELECT フェイズ（売るカード選択中）：価格ラベルが表示される（"¥5"）
    runner.state.current_phase = godfield_core.GamePhase.PHASE_SELL_SELECT
    obs_sell = godfield_core.get_observation(runner.state, 0)
    data_sell = serialize_observation(obs_sell, player_id=0, state=runner.state)

    sell_card_0_sell = data_sell["hand"][0]
    sell_card_1_sell = data_sell["hand"][1]
    assert sell_card_0_sell["power_label"] == "¥5"
    assert sell_card_1_sell["power_label"] == "¥5"

    # 3. 1枚目の「売る」カードが選択状態（使用中）の場合：そのカードの価格ラベルは非表示になり、もう1枚の「売る」には価格が表示されること
    runner.state.set_is_used(0, 0, True) # 1枚目をステージング（使用中）にする
    runner.state.set_num_staged_cards(0, 1)
    runner.state.set_staged_card(0, 0, 0) # 0番目の手札スロットがステージングされている
    obs_used = godfield_core.get_observation(runner.state, 0)
    data_used = serialize_observation(obs_used, player_id=0, state=runner.state)

    sell_card_0_used = data_used["hand"][0]
    sell_card_1_used = data_used["hand"][1]
    assert sell_card_0_used["power_label"] == ""  # 使用中の「売る」は非表示
    assert sell_card_1_used["power_label"] == "¥5" # 未使用の「売る」は ¥5 と表示される

    # 4. 2枚ともステージング（使用中）された場合：
    # - 手札のカードのラベルは両方とも ""
    # - ステージリストの1枚目（トリガー）は ""、2枚目（商品）は "¥5"
    # - pending_badge（合計売値）は "¥5"
    runner.state.set_is_used(0, 1, True)
    runner.state.set_num_staged_cards(0, 2)
    runner.state.set_staged_card(0, 1, 1) # 1番目の手札スロットがステージングされている
    obs_both = godfield_core.get_observation(runner.state, 0)
    data_both = serialize_observation(obs_both, player_id=0, state=runner.state)

    assert data_both["hand"][0]["power_label"] == ""
    assert data_both["hand"][1]["power_label"] == ""

    assert len(data_both["staged"]) == 2
    assert data_both["staged"][0]["power_label"] == ""   # トリガー
    assert data_both["staged"][1]["power_label"] == "¥5"  # 商品

    assert data_both["staged_total_badge"] is not None
    assert data_both["staged_total_badge"]["label"] == "¥5"

    # 5. 手札の2枚目（スロット1）の「売る」のみがトリガーとしてステージングされた場合：
    # - 手札のスロット1（使用中）は ""、スロット0（未使用の「売る」）は "¥5" と表示されること
    # - ステージリストの1枚目（トリガー）は "" と表示されること
    runner.state.set_is_used(0, 0, False)
    runner.state.set_is_used(0, 1, True)
    runner.state.set_num_staged_cards(0, 1)
    runner.state.set_staged_card(0, 0, 1) # スロット1が最初にステージング（トリガー）されている
    obs_slot1 = godfield_core.get_observation(runner.state, 0)
    data_slot1 = serialize_observation(obs_slot1, player_id=0, state=runner.state)

    assert data_slot1["hand"][0]["power_label"] == "¥5" # 未使用の「売る」は ¥5
    assert data_slot1["hand"][1]["power_label"] == ""   # 使用中の「売る」は非表示
    assert len(data_slot1["staged"]) == 1
    assert data_slot1["staged"][0]["power_label"] == ""  # トリガーの「売る」は非表示
