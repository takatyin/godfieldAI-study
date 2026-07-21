import numpy as np
import pytest
import godfield_core
from tests.core.test_utils import SimulationRunner, find_card_by_name

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
# float phase_one_hot[7] (49-55)
# int hand_cards[18] (56-73)
# int staged_cards[18] (74-91)
# int opponent_hand_cards[18] (92-109)
# int opponent_staged_cards[18] (110-127)
# int pending_card (128)
# GameEvent history[64] (129-448)
# int history_head (449)
# float action_mask[122] (450-571)


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

    int_view = obs_flat.view(np.int32)
    obs["hand_cards"] = int_view[56:74]
    obs["staged_cards"] = int_view[74:92]
    obs["opponent_hand_cards"] = int_view[92:110]
    obs["opponent_staged_cards"] = int_view[110:128]
    obs["pending_card"] = int_view[128]

    obs["action_mask"] = obs_flat[450 : 450 + 122]
    return obs


def test_earth_guardian_group_attack_fix():
    """
    検証内容: 地球神が全体攻撃武器を使用した際、フェイズが正常に PHASE_DEFENSE に遷移すること。
    """
    found = False
    weapon_attack_count = 0

    # 2000回シードを探索
    for seed in range(2000):
        sim = SimulationRunner()
        sim.state.seed_rng(seed)
        sim.set_status(player=0, hp=40, mp=10, money=10)
        sim.set_status(player=1, hp=40, mp=10, money=10)
        sim.state.set_guardian(1, 9)  # 相手（プレイヤー1）の守護神を地球神(9)にする

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
