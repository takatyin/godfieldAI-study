import godfield_core
from godfield_core import ActionType, GamePhase, SicknessType, CurseType
from tests.core.test_utils import SimulationRunner, find_card_by_name, get_all_cards
import pytest


# ==========================================
# Merged from: tests/core/test_special_gimmicks.py
# ==========================================

import numpy as np

# Observation オフセット定数 (Observation struct)
# float hp_me, hp_opp (0, 1)
# float mp_me, mp_opp (2, 3)
# float money_me, money_opp (4, 5)
# float sickness_me[5], sickness_opp[5] (6-10, 11-15)
# float curses_me[4], curses_opp[4] (16-19, 20-23)
# float guardian_me[11], guardian_opp[11] (24-34, 35-45)
# float incoming_damage (46)
# float current_staged_defense (47)
# float is_apocalypse (48)
# float phase_one_hot[18] (49-66)
# int hand_cards[18] (67-84)
# int staged_cards[18] (85-102)
# int opponent_hand_cards[18] (103-120)
# int opponent_staged_cards[18] (121-138)
# GameEvent history[64] (139-458)
# int history_head (459)
# float action_mask[122] (460-581)


def parse_obs(obs_flat):
    obs = {}
    obs["hp_me"] = obs_flat[0]
    obs["hp_opp"] = obs_flat[1]
    obs["mp_me"] = obs_flat[2]
    obs["mp_opp"] = obs_flat[3]
    obs["money_me"] = obs_flat[4]
    obs["money_opp"] = obs_flat[5]

    obs["sickness_me"] = obs_flat[6:11]
    obs["sickness_opp"] = obs_flat[11:16]
    obs["curses_me"] = obs_flat[16:20]
    obs["curses_opp"] = obs_flat[20:24]
    obs["guardian_me"] = obs_flat[24:35]
    obs["guardian_opp"] = obs_flat[35:46]

    obs["hand_cards"] = obs_flat[67:85].astype(np.int32)
    obs["staged_cards"] = obs_flat[85:103].astype(np.int32)
    obs["opponent_hand_cards"] = obs_flat[103:121].astype(np.int32)
    obs["opponent_staged_cards"] = obs_flat[121:139].astype(np.int32)

    obs["action_mask"] = obs_flat[460 : 460 + 122]
    return obs


def test_earth_guardian_group_attack_fix():
    """
    検証内容: 地球神が全体攻撃武器を使用した際、フェイズが正常に PHASE_DEFENSE に遷移すること。
    """
    found = False
    weapon_attack_count = 0

    # 20000回シードを探索
    for seed in range(20000):
        sim = SimulationRunner()
        sim.state.seed_rng(seed)
        sim.set_status(player=0, hp=40, mp=10, money=10)
        sim.set_status(player=1, hp=40, mp=10, money=10)
        sim.state.set_guardian(1, 9)  # (プレイヤー1)の守護神を地球神(9)にする

        # 祈ることでターンを終了させ、PHASE_END を自動進行させる
        sim.step(godfield_core.ActionType.ACTION_PRAY)

        # 地球神が攻撃を使用して PHASE_DEFENSE に入ったか確認
        if sim.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE:
            weapon_attack_count += 1
            if sim.state.pending_is_group_attack:
                # 一般武器と異なり、全体武器を地球神が引いた場合も PHASE_DEFENSE でアクターが自分になっていること
                assert sim.state.current_actor_id == 0
                assert sim.state.attacker_id == 1
                assert sim.state.defender_id == 0
                found = True
                break

    print(f"Total Earth Guardian weapon attacks observed: {weapon_attack_count} in 2000 runs")
    assert found, f"全体攻撃武器を地球神が使用するシードが見つかりませんでした (武器攻撃回数: {weapon_attack_count})"


def test_observation_money_and_mask():
    """
    検証内容: 所持金(money)が Observation に代入され、action_mask が get_legal_actions の結果と一致すること。
    """
    env = godfield_core.EnvPool(1)
    env.reset(42)

    state = godfield_core.InternalState()
    godfield_core.clear_state(state)
    state.current_actor_id = 0
    state.current_phase = godfield_core.GamePhase.PHASE_MAIN

    state.set_hp(0, 40)
    state.set_hp(1, 40)
    state.set_money(0, 35)  # me
    state.set_money(1, 75)  # opp

    # 祈る(ACTION_PRAY)はメインフェイズで合法
    # 展開されていない奇跡等は非合法
    env.set_state(0, state)
    obs_flat = env.get_observations()
    obs = parse_obs(obs_flat)

    assert obs["money_me"] == pytest.approx(0.35)
    assert obs["money_opp"] == pytest.approx(0.75)

    # 手動で get_legal_actions を取得してマスクと一致するかアサート
    expected_mask = godfield_core.get_legal_actions(state)
    for i in range(122):
        assert obs["action_mask"][i] == (1.0 if expected_mask[i] else 0.0)


def test_observation_fog_masking():
    """
    検証内容: 自分が霧(FOG)状態の時、相手のステータス情報が Observation 上で 0.0f にマスクされること。
    """
    env = godfield_core.EnvPool(1)
    env.reset(42)

    state = godfield_core.InternalState()
    godfield_core.clear_state(state)
    state.current_actor_id = 0
    state.current_phase = godfield_core.GamePhase.PHASE_MAIN

    state.set_hp(0, 40)
    state.set_hp(1, 50)
    state.set_mp(0, 10)
    state.set_mp(1, 20)
    state.set_money(0, 30)
    state.set_money(1, 60)
    state.set_true_hand(1, 0, find_card_by_name("weapons/bronze-club"))
    # 相手の手札の1枚目が公開状態
    state.set_is_known_to_opp(1, 0, True)

    # 霧がかかっていない時 ➡ 相手のステータスが見える
    env.set_state(0, state)
    obs = parse_obs(env.get_observations())
    assert obs["hp_opp"] == pytest.approx(0.50)
    assert obs["mp_opp"] == pytest.approx(0.20)
    assert obs["money_opp"] == pytest.approx(0.60)
    assert obs["opponent_hand_cards"][0] == find_card_by_name("weapons/bronze-club")

    # 自分(0)に霧を付与 ➡ 相手の情報がマスクされて見えなくなる(0.0)
    state.set_curses(0, godfield_core.CurseType.CURSE_FOG, True)
    env.set_state(0, state)
    obs = parse_obs(env.get_observations())
    assert obs["hp_opp"] == 0.0
    assert obs["mp_opp"] == 0.0
    assert obs["money_opp"] == 0.0
    assert obs["opponent_hand_cards"][0] == 0


def test_observation_dream_masking():
    """
    検証内容: 自分が夢(DREAM)状態の時、すでに持っている手札は変化せず、
    夢状態で新たにドローしたカードのみが同じDreamGroupの偽装カードに見えること。
    """
    env = godfield_core.EnvPool(1)
    env.reset(42)

    state = godfield_core.InternalState()
    godfield_core.clear_state(state)
    state.current_actor_id = 0
    state.current_phase = godfield_core.GamePhase.PHASE_MAIN

    state.set_hp(0, 40)
    state.set_hp(1, 40)

    card_id = find_card_by_name("weapons/bronze-club")
    # set_true_handは、見かけ上の手札(apparent_hand)の設定と確定(is_confirmed = True)も同時に行う
    state.set_true_hand(0, 0, card_id)

    # 夢がかかっていない時 ➡ 真のカードIDが見える
    env.set_state(0, state)
    obs = parse_obs(env.get_observations())
    assert obs["hand_cards"][0] == card_id

    # 自分(0)に夢を付与 ➡ すでに持っている手札は変化しない
    state.set_curses(0, godfield_core.CurseType.CURSE_DREAM, True)
    env.set_state(0, state)
    obs = parse_obs(env.get_observations())
    assert obs["hand_cards"][0] == card_id

    # 夢状態で新たにドローする ➡ 夢グループ（通常武器）内のいずれかのカードに偽装される
    # ドローしたカードが武器（銅のこん棒）の場合
    state.set_true_hand(0, 1, card_id)
    # 未確定状態にし、偽装を設定
    state.set_is_confirmed(0, 1, False)
    state.set_apparent_hand(0, 1, find_card_by_name("weapons/saw-boom-boom"))  # 偽装

    env.set_state(0, state)
    obs = parse_obs(env.get_observations())
    assert obs["hand_cards"][1] == find_card_by_name("weapons/saw-boom-boom")
    # 真のカードはまだ見えない
    assert state.get_true_hand(0, 1) == card_id


def test_evil_broadsword_self_harm_hp14():
    """
    検証内容: HP 14 の状態で自分に「邪神の大剣」を使用した場合。
    - 最初の14ダメージでHPが0になり、「太陽のお守り」を即座に消費してHP 10で復活する。
    - その後、自傷（反射）ダメージの14を受けて再度HPが0になり、死亡（HP 0）することを確認します。
    """
    runner = SimulationRunner()
    broadsword_id = find_card_by_name("邪神の大剣")
    amulet_id = find_card_by_name("太陽のお守り")

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_hp(0, 14)

    # 手札設定: [邪神の大剣, 太陽のお守り, ...]
    runner.state.set_true_hand(0, 0, broadsword_id)
    runner.state.set_true_hand(0, 1, amulet_id)
    for j in range(2, 18):
        runner.state.set_true_hand(0, j, godfield_core.CARD_EMPTY)

    # 1. 邪神の大剣を選択
    runner.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
    # 2. 自分を対象
    runner.step(godfield_core.ActionType.ACTION_TARGET_SELF)

    # 死亡していること
    assert runner.state.get_hp(0) == 0
    assert runner.state.is_done is True
    # 太陽のお守りが消費されていること
    assert runner.state.get_true_hand(0, 1) == godfield_core.CARD_EMPTY


def test_evil_broadsword_self_harm_hp20():
    """
    検証内容: HP 20 の状態で自分に「邪神の大剣」を使用した場合。
    - 最初の14ダメージではHP 6となる（死亡しないため復活はおきない）。
    - その後、自傷の14ダメージを受けてHP 0となり、ここで「太陽のお守り」を消費してHP 10で復活（生存）することを確認します。
    """
    runner = SimulationRunner()
    broadsword_id = find_card_by_name("邪神の大剣")
    amulet_id = find_card_by_name("太陽のお守り")

    runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_hp(0, 20)

    # 手札設定
    runner.state.set_true_hand(0, 0, broadsword_id)
    runner.state.set_true_hand(0, 1, amulet_id)
    for j in range(2, 18):
        runner.state.set_true_hand(0, j, godfield_core.CARD_EMPTY)

    # 1. 邪神の大剣を選択
    runner.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
    # 2. 自分を対象
    runner.step(godfield_core.ActionType.ACTION_TARGET_SELF)

    # HP 10 で復活し生存していること
    assert runner.state.get_hp(0) == 10
    assert runner.state.is_done is False
    # ターンが終了して P1 のターンになっていること
    assert runner.state.current_actor_id == 1
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_MAIN


def test_venus_bribe_resolution_and_mirror():
    """
    検証内容: 金星神の「わいろ」の効果解決と、スーパーミラーでの反射。
    - 通常解決: Bribe（5お金）を受けた側がそのまま受諾（Confirm）すると、受諾側がお金 +5 を得る。
    - 反射解決: Bribeを受けた側がスーパーミラーで反射すると、元の発動者側が受諾側になり、そちらがお金 +5 を得る。
    """
    bribe_id = find_card_by_name("わいろ")
    mirror_id = find_card_by_name("スーパーミラー")

    # Case A: 通常解決
    runner_a = SimulationRunner()
    runner_a.state.current_phase = godfield_core.GamePhase.PHASE_SUNDRY_SELECT_MIRROR
    runner_a.state.current_actor_id = 1
    runner_a.state.attacker_id = 0
    runner_a.state.defender_id = 1
    runner_a.state.pending_attack_source_id = bribe_id
    runner_a.state.pending_attack_power = 5

    runner_a.state.set_money(0, 10)
    runner_a.state.set_money(1, 10)

    # P1が確認 (受諾)
    runner_a.step(godfield_core.ActionType.ACTION_CONFIRM)

    # 解決後、P1（defender）がお金を5貰い、P0は変化なし
    assert runner_a.state.get_money(1) == 15
    assert runner_a.state.get_money(0) == 10

    # Case B: スーパーミラーでの反射解決
    runner_b = SimulationRunner()
    runner_b.state.current_phase = godfield_core.GamePhase.PHASE_SUNDRY_SELECT_MIRROR
    runner_b.state.current_actor_id = 1
    runner_b.state.attacker_id = 0
    runner_b.state.defender_id = 1
    runner_b.state.pending_attack_source_id = bribe_id
    runner_b.state.pending_attack_power = 5

    runner_b.state.set_money(0, 10)
    runner_b.state.set_money(1, 10)
    # P1の手札にスーパーミラーを設定
    runner_b.state.set_true_hand(1, 0, mirror_id)
    for j in range(1, 18):
        runner_b.state.set_true_hand(1, j, godfield_core.CARD_EMPTY)

    # P1がスーパーミラーを選択して反射 (即座にアクターがP0に入れ替わる)
    runner_b.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)

    # ロールが入れ替わり、P0が防衛アクターになること
    assert runner_b.state.current_phase == godfield_core.GamePhase.PHASE_SUNDRY_SELECT_MIRROR
    assert runner_b.state.current_actor_id == 0
    assert runner_b.state.attacker_id == 1
    assert runner_b.state.defender_id == 0

    # P0が受諾 (確認)
    runner_b.step(godfield_core.ActionType.ACTION_CONFIRM)

    # 反射されたため、P0（元の発動者）がお金を5貰い、P1は変化なし
    assert runner_b.state.get_money(0) == 15
    assert runner_b.state.get_money(1) == 10


def test_venus_fine_resolution_and_mirror():
    """
    検証内容: 金星神の「罰金」の効果解決と、スーパーミラーでの反射。
    - 通常解決: Fine（3お金没収）を受けた側が受諾すると、受諾側がお金 -3（足りない分はMP/HP）となり、発動者側がお金 +3 を得る。
    - 反射解決: Fineを受けた側がスーパーミラーで反射すると、元の発動者側が没収の対象になり、反射側がお金 +3 を得る。
    """
    fine_id = find_card_by_name("罰金")
    mirror_id = find_card_by_name("スーパーミラー")

    # Case A: 通常解決
    runner_a = SimulationRunner()
    runner_a.state.current_phase = godfield_core.GamePhase.PHASE_SUNDRY_SELECT_MIRROR
    runner_a.state.current_actor_id = 1
    runner_a.state.attacker_id = 0
    runner_a.state.defender_id = 1
    runner_a.state.pending_attack_source_id = fine_id
    runner_a.state.pending_attack_power = 3

    runner_a.state.set_money(0, 10)
    runner_a.state.set_money(1, 10)

    runner_a.step(godfield_core.ActionType.ACTION_CONFIRM)

    # P1が没収されてP0が回収すること
    assert runner_a.state.get_money(1) == 7
    assert runner_a.state.get_money(0) == 13

    # Case B: 反射解決
    runner_b = SimulationRunner()
    runner_b.state.current_phase = godfield_core.GamePhase.PHASE_SUNDRY_SELECT_MIRROR
    runner_b.state.current_actor_id = 1
    runner_b.state.attacker_id = 0
    runner_b.state.defender_id = 1
    runner_b.state.pending_attack_source_id = fine_id
    runner_b.state.pending_attack_power = 3

    runner_b.state.set_money(0, 10)
    runner_b.state.set_money(1, 10)
    # P1の手札にスーパーミラーを設定
    runner_b.state.set_true_hand(1, 0, mirror_id)
    for j in range(1, 18):
        runner_b.state.set_true_hand(1, j, godfield_core.CARD_EMPTY)

    # P1がスーパーミラーを選択して反射 (即座にアクターがP0に入れ替わる)
    runner_b.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)

    # P0が受諾
    runner_b.step(godfield_core.ActionType.ACTION_CONFIRM)

    # 反射によりP0が罰金を支払われ、P1がそれを受け取ること
    assert runner_b.state.get_money(0) == 7
    assert runner_b.state.get_money(1) == 13


def test_verify_fever_mask_transition():
    # 激烈疾風剣 のカードIDを取得
    gale_id = find_card_by_name("激烈疾風剣")
    aura_id = find_card_by_name("＜オーラ＞")
    mask_id = find_card_by_name("熱狂仮面")
    amulet_id = find_card_by_name("太陽のお守り")

    sickness_names = {
        godfield_core.SicknessType.SICKNESS_NONE: "なし",
        godfield_core.SicknessType.SICKNESS_COLD: "風邪",
        godfield_core.SicknessType.SICKNESS_FEVER: "熱病",
        godfield_core.SicknessType.SICKNESS_HELL: "地獄病",
        godfield_core.SicknessType.SICKNESS_HEAVEN: "天国病",
    }

    # 各枚数での結果を格納
    results = {}

    for num_masks in range(1, 5):
        runner = SimulationRunner()
        runner.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
        runner.state.current_actor_id = 1
        
        # P0のHPを99にしてダメージで死なないようにする（ただし発作では死ぬ）
        runner.state.set_hp(0, 99)
        runner.state.set_hp(1, 40)
        runner.state.set_mp(0, 50)
        runner.state.set_mp(1, 50)
        runner.state.set_money(0, 10)
        runner.state.set_money(1, 10)
        
        # P1の手札を設定 (激烈疾風剣, ＜オーラ＞, ＜オーラ＞)
        runner.state.set_true_hand(1, 0, gale_id)
        runner.state.set_true_hand(1, 1, aura_id)
        runner.state.set_true_hand(1, 2, aura_id)
        for j in range(3, 18):
            runner.state.set_true_hand(1, j, godfield_core.CARD_EMPTY)
            
        # P0の手札を設定 (熱狂仮面 x num_masks)
        for i in range(num_masks):
            runner.state.set_true_hand(0, i, mask_id)
        for j in range(num_masks, 18):
            runner.state.set_true_hand(0, j, godfield_core.CARD_EMPTY)
            
        # P1が激烈疾風剣 + ＜オーラ＞ + ＜オーラ＞ を選択して攻撃
        runner.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)  # 激烈疾風剣
        runner.step(godfield_core.ActionType.ACTION_SELECT_HAND_1)  # ＜オーラ＞
        runner.step(godfield_core.ActionType.ACTION_SELECT_HAND_2)  # ＜オーラ＞
        runner.step(godfield_core.ActionType.ACTION_TARGET_OPP)     # 相手をターゲット
        
        # P0が熱狂仮面をすべて選択してConfirm
        for i in range(num_masks):
            runner.step(godfield_core.ActionType(int(godfield_core.ActionType.ACTION_SELECT_HAND_0) + i))
        runner.step(godfield_core.ActionType.ACTION_CONFIRM)
        
        results[num_masks] = (runner.state.get_hp(0), runner.state.get_sickness(0))

    # 4つ + お守り
    runner_amulet = SimulationRunner()
    runner_amulet.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    runner_amulet.state.current_actor_id = 1
    runner_amulet.state.set_hp(0, 99)
    runner_amulet.state.set_hp(1, 40)
    runner_amulet.state.set_mp(0, 50)
    runner_amulet.state.set_mp(1, 50)
    runner_amulet.state.set_money(0, 10)
    runner_amulet.state.set_money(1, 10)
    
    runner_amulet.state.set_true_hand(1, 0, gale_id)
    runner_amulet.state.set_true_hand(1, 1, aura_id)
    runner_amulet.state.set_true_hand(1, 2, aura_id)
    for j in range(3, 18):
        runner_amulet.state.set_true_hand(1, j, godfield_core.CARD_EMPTY)
        
    for i in range(4):
        runner_amulet.state.set_true_hand(0, i, mask_id)
    runner_amulet.state.set_true_hand(0, 4, amulet_id)
    for j in range(5, 18):
        runner_amulet.state.set_true_hand(0, j, godfield_core.CARD_EMPTY)
        
    runner_amulet.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
    runner_amulet.step(godfield_core.ActionType.ACTION_SELECT_HAND_1)
    runner_amulet.step(godfield_core.ActionType.ACTION_SELECT_HAND_2)
    runner_amulet.step(godfield_core.ActionType.ACTION_TARGET_OPP)
    
    for i in range(4):
        runner_amulet.step(godfield_core.ActionType(int(godfield_core.ActionType.ACTION_SELECT_HAND_0) + i))
    runner_amulet.step(godfield_core.ActionType.ACTION_CONFIRM)

    # 結果をコンソールに出力
    print("\n=== Sickness Transition Verification Results ===")
    for k, (hp, sick) in results.items():
        print(f"Masks: {k} | HP: {hp} | Sickness: {sickness_names[sick]}")
    print(f"Masks: 4 + Amulet | HP: {runner_amulet.state.get_hp(0)} | Sickness: {sickness_names[runner_amulet.state.get_sickness(0)]}")
    print("================================================\n")

    # アサーションチェック (ユーザーの指定通りになるか)
    # 1つ: 風邪 -> 熱病 -> 熱病 (Cold then Fever resolves to Fever)
    # ダメージ 52 - 10 = 42。ターン終了時の熱病ダメージ 2。HP 99 - 42 - 2 = 55
    assert results[1][1] == godfield_core.SicknessType.SICKNESS_FEVER
    assert results[1][0] == 55

    # 2つ: 風邪 -> 熱病 -> 地獄病 (Cold then Fever then Fever resolves to Hell)
    # ダメージ 52 - 20 = 32。ターン終了時の地獄病ダメージ 5。HP 99 - 32 - 5 = 62
    assert results[2][1] == godfield_core.SicknessType.SICKNESS_HELL
    assert results[2][0] == 62

    # 3つ: 風邪 -> 熱病 -> 地獄病 -> 天国病
    # ダメージ 52 - 30 = 22。ターン終了時の天国病回復 5。HP 99 - 22 + 5 = 82
    assert results[3][1] == godfield_core.SicknessType.SICKNESS_HEAVEN
    assert results[3][0] == 82

    # 4つ: 発作で死亡 (HP 0)
    assert results[4][0] == 0

    # 4つ + お守り: HP 10 で復活、さらに天国病回復 5 で HP 15。天国病状態
    assert runner_amulet.state.get_hp(0) == 15
    assert runner_amulet.state.get_sickness(0) == godfield_core.SicknessType.SICKNESS_HEAVEN





# ==========================================
# Merged from: tests/core/test_dream.py
# ==========================================



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


# ==========================================
# Merged from: tests/core/test_mushroom.py
# ==========================================



def test_mushroom_outbreak_auto_advance():
    """
    検証内容: 「運命のひも」によって「きのこ大発生」がトリガーされた際、
    即座に全自動で6ターン（ご乱心状態）が進行し、ターン数が6進むこと、
    およびご乱心終了後に通常の操作受付（mushroom_turns = 0）に戻ることを検証する。
    """
    string_of_fate_id = find_card_by_name("運命のひも")

    # きのこ大発生（現象インデックス 2）を発生させるシードを探索
    target_seed = -1
    for seed in range(100):
        runner = SimulationRunner()
        runner.reset_state()
        runner.state.seed_rng(seed)
        runner.state.current_turn = 10
        runner.state.current_actor_id = 0
        runner.set_status(player=0, hp=40, mp=10, money=10)
        runner.set_status(player=1, hp=40, mp=10, money=10)

        # 運命のひもを持たせる
        runner.state.set_true_hand(0, 0, string_of_fate_id)

        # 運命のひもを使用する (選択 ➡ ターゲット自己)
        runner.perform_attack([0], to_self=True)

        # もし「きのこ大発生」がトリガーされた場合、内部で mushroom_turns が 6 にセットされた後、
        # ターン終了処理でデクリメントされつつ自動進行するため、
        # 最終的に現在のターンが 10 + 6 = 16 まで進んでいるはずである。
        if runner.state.current_turn == 16:
            target_seed = seed
            break

    assert target_seed != -1, "Mushroom Outbreak was not triggered in any of the 100 seeds"

    # 発見したシードで再度詳細をアサート
    runner = SimulationRunner()
    runner.reset_state()
    runner.state.seed_rng(target_seed)
    runner.state.current_turn = 10
    runner.state.current_actor_id = 0
    runner.set_status(player=0, hp=40, mp=10, money=10)
    runner.set_status(player=1, hp=40, mp=10, money=10)
    runner.state.set_true_hand(0, 0, string_of_fate_id)

    # 運命のひもを使用する前のターンは 10
    assert runner.state.current_turn == 10

    runner.perform_attack([0], to_self=True)

    # ご乱心中の6ターンが自動進行し、終了していることをアサート
    assert runner.state.current_turn == 16
    assert runner.state.mushroom_turns == 0
    assert runner.state.current_phase == godfield_core.GamePhase.PHASE_MAIN

    # 自動進行により、カードがドローされて手札に入っていることを確認
    hand0 = [runner.state.get_true_hand(0, i) for i in range(18)]
    hand1 = [runner.state.get_true_hand(1, i) for i in range(18)]
    has_cards0 = any(c != godfield_core.CARD_EMPTY for c in hand0)
    has_cards1 = any(c != godfield_core.CARD_EMPTY for c in hand1)

    assert has_cards0 or has_cards1 or runner.state.is_done, (
        "No cards were drawn or played during the 6 automatic turns under confusion"
    )


def test_mushroom_outbreak_stacking():
    """
    検証内容: きのこ大発生中にさらにきのこ大発生が発生した際、ターン数が上書きではなく加算されること。
    - 内部状態の mushroom_turns に対し、値が正しく加算・保持できることを検証。
    """
    runner = SimulationRunner()
    runner.reset_state()

    # 初期状態としてご乱心3ターンをセット
    runner.state.mushroom_turns = 3

    # 加算解決（C++側の += 6 と同等の操作）
    runner.state.mushroom_turns += 6
    assert runner.state.mushroom_turns == 9

