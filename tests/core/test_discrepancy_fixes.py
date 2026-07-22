import pytest
import godfield_core
from tests.core.test_utils import SimulationRunner, find_card_by_name

def test_dark_cloud_accuracy():
    # 暗雲状態なら命中率100%未満の攻撃も100%必中になることをテスト
    sim = SimulationRunner()
    
    # 命中率75%の「つるシュート」を探す
    vine_shoot = find_card_by_name("つるシュート")
    
    # 1. 相手が暗雲状態の場合
    hit_count = 0
    total_trials = 100
    for _ in range(total_trials):
        sim.reset_state()
        sim.set_hand(0, [vine_shoot])
        sim.state.set_curses(1, godfield_core.CURSE_DARK_CLOUD, True)
        
        sim.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
        sim.step(godfield_core.ActionType.ACTION_TARGET_OPP)
        
        # 命中した場合のみ相手の防御フェイズに遷移する
        if sim.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE:
            hit_count += 1
            
    # 暗雲なら100%必中
    assert hit_count == total_trials

    # 2. 相手が暗雲状態でない場合（通常確率）
    hit_count_normal = 0
    for _ in range(total_trials):
        sim.reset_state()
        sim.set_hand(0, [vine_shoot])
        
        sim.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
        sim.step(godfield_core.ActionType.ACTION_TARGET_OPP)
        
        if sim.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE:
            hit_count_normal += 1
            
    # 通常なら75%程度 (100回中50〜95回程度)
    assert 50 < hit_count_normal < 100


def test_dark_cloud_bounce_is_unaffected():
    # 暗雲状態であっても「弾く」の確率（50%）には影響しないことをテスト
    sim = SimulationRunner()
    
    # 奇跡を弾く「＜乱気流＞」と、攻撃する「＜火の玉＞」
    turbulence = find_card_by_name("＜乱気流＞")
    fireball = find_card_by_name("＜火の玉＞")
    
    bounce_success_count = 0
    total_trials = 100
    for _ in range(total_trials):
        sim.reset_state()
        # プレイヤー0に＜火の玉＞、プレイヤー1に＜乱気流＞
        sim.set_hand(0, [fireball])
        sim.set_hand(1, [turbulence])
        sim.set_status(0, mp=10)
        sim.set_status(1, mp=10)
        
        # 防御側を暗雲状態にする
        sim.state.set_curses(1, godfield_core.CURSE_DARK_CLOUD, True)
        
        # プレイヤー0が＜火の玉＞で攻撃
        sim.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
        sim.step(godfield_core.ActionType.ACTION_TARGET_OPP)
        
        # プレイヤー1が＜乱気流＞で防御（弾き試行）
        sim.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
        sim.step(godfield_core.ActionType.ACTION_CONFIRM)
        
        # 弾きに成功した場合、攻守交代してプレイヤー1が攻撃側になり、プレイヤー0（me=0）の奇跡防御フェイズになる
        if sim.state.current_phase == godfield_core.GamePhase.PHASE_MIRACLE_DEFENSE and sim.state.current_actor_id == 0:
            bounce_success_count += 1
            
    # 50%確率なので、100回中25〜75回程度成功するはず（暗雲の影響を受けない）
    assert 25 < bounce_success_count < 75


def test_guardian_leaves_on_combat_damage():
    # プレイヤーが戦闘ダメージを受けた際に10%の確率で守護神が去ることをテスト
    sim = SimulationRunner()
    
    # 攻撃力1の「銅のこん棒」と「アイアンシールド」
    bronze_club = find_card_by_name("銅のこん棒")
    iron_shield = find_card_by_name("アイアンシールド")
    
    # 1. ダメージを受けた場合
    dismiss_count = 0
    total_trials = 200
    for _ in range(total_trials):
        sim.reset_state()
        sim.state.seed_rng(_)
        sim.set_hand(0, [bronze_club])
        # プレイヤー1に守護神（火星神）を憑ける
        sim.state.set_guardian(1, godfield_core.MARS)
        
        # プレイヤー0が攻撃
        sim.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
        sim.step(godfield_core.ActionType.ACTION_TARGET_OPP)
        
        # プレイヤー1はスルー（無防備）
        sim.step(godfield_core.ActionType.ACTION_CONFIRM)
        
        # 守護神が去った（GuardianType.NONEになった）か確認
        if sim.state.get_guardian(1) == godfield_core.GuardianType.NONE:
            dismiss_count += 1
            
    # 10%確率なので、200回中10〜40回程度去るはず
    assert 10 < dismiss_count < 40

    # 2. ダメージを受けなかった（防具で完全に防いだ）場合
    dismiss_count_prevented = 0
    for _ in range(50):
        sim.reset_state()
        sim.set_hand(0, [bronze_club])
        # プレイヤー1に防御力4の「アイアンシールド」を持たせる（攻撃力1を防げる）
        sim.set_hand(1, [iron_shield])
        sim.state.set_guardian(1, godfield_core.MARS)
        
        # プレイヤー0が攻撃
        sim.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
        sim.step(godfield_core.ActionType.ACTION_TARGET_OPP)
        
        # プレイヤー1がアイアンシールドで防御
        sim.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
        sim.step(godfield_core.ActionType.ACTION_CONFIRM)
        
        if sim.state.get_guardian(1) == godfield_core.GuardianType.NONE:
            dismiss_count_prevented += 1
            
    # 被ダメージ0なので、絶対に去らない
    assert dismiss_count_prevented == 0


def test_guardian_leaves_on_sickness_damage():
    # プレイヤーが病気ダメージを受けた際に10%の確率で守護神が去ることをテスト
    sim = SimulationRunner()
    
    # 1. 風邪ダメージ（1ダメージ）を受ける場合
    dismiss_count = 0
    total_trials = 200
    for _ in range(total_trials):
        sim.reset_state()
        sim.state.seed_rng(_)
        # プレイヤー0に風邪と火星神
        sim.state.set_sickness(0, godfield_core.SICKNESS_COLD)
        sim.state.set_guardian(0, godfield_core.MARS)
        
        # プレイヤー0が祈る（ターン終了を進めるため）
        sim.step(godfield_core.ActionType.ACTION_PRAY)
        
        if sim.state.get_guardian(0) == godfield_core.GuardianType.NONE:
            dismiss_count += 1
            
    # 10%確率なので、200回中10〜40回程度去るはず
    assert 10 < dismiss_count < 40

    # 2. 天国病による回復の場合
    dismiss_count_heaven = 0
    for _ in range(50):
        sim.reset_state()
        # HP減少を抑えるため初期HPを30にする
        sim.set_status(0, hp=30)
        sim.state.set_sickness(0, godfield_core.SICKNESS_HEAVEN)
        sim.state.set_guardian(0, godfield_core.MARS)
        
        sim.step(godfield_core.ActionType.ACTION_PRAY)
        
        if sim.state.get_guardian(0) == godfield_core.NONE:
            dismiss_count_heaven += 1
            
    # 天国病は回復なので、絶対に去らない
    assert dismiss_count_heaven == 0


def test_guardian_does_not_leave_on_exchange():
    # 両替によるHP減少では守護神が去らないことをテスト
    sim = SimulationRunner()
    
    # プレイヤー0に「両替」カードと火星神
    exchange = find_card_by_name("両替")
    sim.set_hand(0, [exchange])
    sim.state.set_guardian(0, godfield_core.MARS)
    sim.set_status(0, hp=40, mp=10, money=20) # 合計70
    
    # 両替を使用
    sim.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
    # HPを20に変更する（HP40から20へ減少）
    sim.step(godfield_core.ActionType.ACTION_NUM_20)
    # MPを10に変更
    sim.step(godfield_core.ActionType.ACTION_NUM_10)
    
    # 両替後のHPが20に減っていることを確認
    assert sim.state.get_hp(0) == 20
    # 守護神が去っていないことをアサート
    assert sim.state.get_guardian(0) == godfield_core.MARS


def test_guardian_does_not_leave_on_fine():
    # 金星神の「罰金」によるHP引き落とし（減少）では守護神が去らないことをテスト
    sim = SimulationRunner()
    
    fine_card = find_card_by_name("罰金")
    
    sim.reset_state()
    # プレイヤー0に守護神Mars、HP 40, MP 0, お金 0 （罰金はHPから引かれる）
    sim.state.set_guardian(0, godfield_core.MARS)
    sim.set_status(0, hp=40, mp=0, money=0)
    
    # プレイヤー1（金星神側）からの罰金攻撃の防御フェイズを直接セットアップ
    sim.state.current_actor_id = 0
    sim.state.current_phase = godfield_core.GamePhase.PHASE_DEFENSE
    sim.state.attacker_id = 1
    sim.state.defender_id = 0
    sim.state.pending_attack_power = 3
    sim.state.pending_attack_source_id = fine_card
    
    # プレイヤー0がスルー
    sim.step(godfield_core.ActionType.ACTION_CONFIRM)
    
    # 罰金で3HP引かれるため、プレイヤー0のHPは37に減少
    assert sim.state.get_hp(0) == 37
    # 守護神 Mars は去っていないことをアサート
    assert sim.state.get_guardian(0) == godfield_core.MARS


def test_reaction_card_strict_weapon_check():
    # 虹のカーテンの無属性化後、武器攻撃に対しては重ねがけ防御が可能であり、
    # タライ、守護神攻撃、指輪反撃などの非武器攻撃に対しては重ねがけ防御が不可能であることをテスト
    sim = SimulationRunner()
    
    rainbow = find_card_by_name("虹のカーテン")
    wall = find_card_by_name("＜壁＞")
    fire_sword = find_card_by_name("ブレイズブレイド")
    gigantic_tub = find_card_by_name("巨大なタライ")
    
    # 1. 武器攻撃（ブレイズブレイド）に対して虹のカーテン＋壁が有効であること
    sim.reset_state()
    # プレイヤー0がブレイズブレイドで攻撃、プレイヤー1が虹のカーテン＋壁で受ける
    sim.set_hand(0, [fire_sword])
    sim.set_hand(1, [rainbow, wall])
    sim.set_status(0, mp=10)
    sim.set_status(1, mp=10)
    
    # 攻撃
    sim.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
    sim.step(godfield_core.ActionType.ACTION_TARGET_OPP)
    
    # 防御フェイズ
    assert sim.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
    # 虹のカーテンを選択 (スロット0)
    sim.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
    
    # 壁 (スロット1) が合法手マスクに含まれていることをアサート
    actions = godfield_core.get_legal_actions(sim.state)
    assert actions[int(godfield_core.ActionType.ACTION_SELECT_HAND_1)] == 1.0
    
    # 2. 超常現象（巨大なタライ）に対して虹のカーテンを使用した後、壁が「合法」であること
    sim.reset_state()
    sim.set_hand(1, [rainbow, wall])
    sim.set_status(1, mp=10)
    
    # 直接巨大なタライの防御フェイズをセットアップする
    sim.state.current_actor_id = 1
    sim.state.current_phase = godfield_core.GamePhase.PHASE_DEFENSE
    sim.state.attacker_id = 0
    sim.state.defender_id = 1
    sim.state.pending_attack_power = 50
    sim.state.pending_attack_element = godfield_core.Element.ELEM_LIGHT
    sim.state.pending_attack_source_id = gigantic_tub
    
    # 虹のカーテンを選択 (スロット0)
    sim.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
    
    # 巨大なタライは物理武器攻撃として扱われるため、壁 (スロット1) は合法手
    actions = godfield_core.get_legal_actions(sim.state)
    assert actions[int(godfield_core.ActionType.ACTION_SELECT_HAND_1)] == 1.0

    # 3. 守護神の固有攻撃（点滅）に対して壁が「非合法」であること
    twinkle = find_card_by_name("点滅")
    sim.reset_state()
    sim.set_hand(1, [rainbow, wall])
    sim.set_status(1, mp=10)
    
    # 点滅の防御フェイズをセットアップ
    sim.state.current_actor_id = 1
    sim.state.current_phase = godfield_core.GamePhase.PHASE_DEFENSE
    sim.state.attacker_id = 0
    sim.state.defender_id = 1
    sim.state.pending_attack_power = 2
    sim.state.pending_attack_element = godfield_core.Element.ELEM_LIGHT
    sim.state.pending_attack_source_id = twinkle
    
    # 虹のカーテンを選択 (スロット0)
    sim.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
    
    # 点滅は type: guardian で非武器扱いのため、壁は非合法手
    actions = godfield_core.get_legal_actions(sim.state)
    assert actions[int(godfield_core.ActionType.ACTION_SELECT_HAND_1)] == 0.0

    # 3.5. 守護神の固有攻撃（ダイヤモンドアクス）に対して壁が「合法」であること
    diamond_axe = find_card_by_name("gurdians/diamond-axe")
    sim.reset_state()
    sim.set_hand(1, [rainbow, wall])
    sim.set_status(1, mp=10)
    
    # ダイヤモンドアクスの防御フェイズをセットアップ
    sim.state.current_actor_id = 1
    sim.state.current_phase = godfield_core.GamePhase.PHASE_DEFENSE
    sim.state.attacker_id = 0
    sim.state.defender_id = 1
    sim.state.pending_attack_power = 15
    sim.state.pending_attack_element = godfield_core.Element.ELEM_STONE
    sim.state.pending_attack_source_id = diamond_axe
    
    # 虹のカーテンを選択 (スロット0)
    sim.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
    
    # ダイヤモンドアクスは物理武器攻撃として扱われるため、壁は合法手
    actions = godfield_core.get_legal_actions(sim.state)
    assert actions[int(godfield_core.ActionType.ACTION_SELECT_HAND_1)] == 1.0

    # 4. 月神の満月刀（武器扱い）に対して壁が「合法」であること
    full_moon_blade = find_card_by_name("満月刀")
    sim.reset_state()
    sim.set_hand(1, [rainbow, wall])
    sim.set_status(1, mp=10)
    
    # 満月刀（無属性、元々壁が有効なはず）の防御フェイズをセットアップ
    sim.state.current_actor_id = 1
    sim.state.current_phase = godfield_core.GamePhase.PHASE_DEFENSE
    sim.state.attacker_id = 0
    sim.state.defender_id = 1
    sim.state.pending_attack_power = 10
    sim.state.pending_attack_element = godfield_core.Element.ELEM_NONE
    sim.state.pending_attack_source_id = full_moon_blade
    
    # 満月刀は最初から無属性なので、虹のカーテンなしでいきなり壁を出せる
    actions = godfield_core.get_legal_actions(sim.state)
    assert actions[int(godfield_core.ActionType.ACTION_SELECT_HAND_1)] == 1.0


def test_zero_power_defense_validation():
    # 攻撃力0の攻撃に対する防具の合法・非合法判定をテスト
    sim = SimulationRunner()
    
    magical_stick = find_card_by_name("マジカルステッキ")
    iron_shield = find_card_by_name("アイアンシールド")
    twinkle = find_card_by_name("点滅")
    
    # 1. 相手が攻撃力0の武器（マジカルステッキ）で攻撃してきた場合
    # 通常の防具（アイアンシールド）が出せる（合法手となる）こと
    sim.reset_state()
    sim.set_hand(1, [iron_shield])
    
    # 直接マジカルステッキMP0の防御フェイズをセットアップする
    sim.state.current_actor_id = 1
    sim.state.current_phase = godfield_core.GamePhase.PHASE_DEFENSE
    sim.state.attacker_id = 0
    sim.state.defender_id = 1
    sim.state.pending_attack_power = 0  # MP0なので攻撃力0
    sim.state.pending_attack_element = godfield_core.Element.ELEM_NONE
    sim.state.pending_attack_source_id = magical_stick
    
    actions = godfield_core.get_legal_actions(sim.state)
    # アイアンシールド（スロット0）が合法であること
    assert actions[int(godfield_core.ActionType.ACTION_SELECT_HAND_0)] == 1.0
    
    # 2. 相手が攻撃力0の守護神固有アクション（点滅）で攻撃してきた場合
    # 通常の防具（アイアンシールド）は出せない（非合法手となる）こと
    sim.reset_state()
    sim.set_hand(1, [iron_shield])
    
    # 直接点滅の防御フェイズをセットアップする
    sim.state.current_actor_id = 1
    sim.state.current_phase = godfield_core.GamePhase.PHASE_DEFENSE
    sim.state.attacker_id = 0
    sim.state.defender_id = 1
    sim.state.pending_attack_power = 0
    sim.state.pending_attack_element = godfield_core.Element.ELEM_LIGHT
    sim.state.pending_attack_source_id = twinkle
    
    actions = godfield_core.get_legal_actions(sim.state)
    # アイアンシールド（スロット0）が非合法であること
    assert actions[int(godfield_core.ActionType.ACTION_SELECT_HAND_0)] == 0.0


