import godfield_core
from tests.core.test_utils import SimulationRunner, find_card_by_name


def find_seed_for_phenomenon(target_phenomenon: int) -> int:
    """
    運命のひもを使用した際に、目的の超常現象 (0~9) が発生するシード値を探索します。
    """
    string_of_fate_id = find_card_by_name("sundries/string-of-fate")
    for seed in range(5000):
        sim = SimulationRunner()
        sim.state.seed_rng(seed)
        sim.set_status(player=0, hp=99, mp=10, money=10)
        sim.set_status(player=1, hp=99, mp=10, money=10)
        
        # 手札に「運命のひも」だけを持たせる
        sim.state.set_true_hand(0, 0, string_of_fate_id)
        sim.state.set_true_hand(0, 1, -1)
        sim.state.set_true_hand(1, 0, -1)
        
        # Confirm -> Target Self
        sim.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
        sim.step(godfield_core.ActionType.ACTION_TARGET_SELF)
        
        # 各現象特有の状態変化で検出
        if target_phenomenon == 0: # 夕焼け (全員熱病)
            if int(sim.state.get_sickness(0)) == 2 and int(sim.state.get_sickness(1)) == 2:
                return seed
        elif target_phenomenon == 1: # 濃霧 (全員霧)
            if sim.state.get_curses(0, godfield_core.CurseType.CURSE_FOG) and sim.state.get_curses(1, godfield_core.CurseType.CURSE_FOG):
                return seed
        elif target_phenomenon == 3: # 竜巻 (全員 HP 1)
            if sim.state.get_hp(0) == 1 and sim.state.get_hp(1) == 1:
                return seed
        elif target_phenomenon == 4: # 巨大なタライ (自分被弾 50ダメ)
            # 自分に被弾したシード（HPが減った）
            if sim.state.get_hp(0) == 49:
                return seed
        elif target_phenomenon == 400: # 相手に巨大なタライ (相手に防御フェイズ)
            if sim.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE and sim.state.pending_attack_source_id == find_card_by_name("phenomena/gigantic-tub"):
                return seed
        elif target_phenomenon == 5: # ブラックホール (相手全体攻撃防御フェイズ)
            if sim.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE and sim.state.pending_attack_source_id == find_card_by_name("phenomena/black-hole"):
                return seed
        elif target_phenomenon == 6: # 暖流 (自身 HP+50)
            pass
        elif target_phenomenon == 7: # 金山 (お金集約)
            if (sim.state.get_money(0) == 20 and sim.state.get_money(1) == 0) or (sim.state.get_money(0) == 0 and sim.state.get_money(1) == 20):
                return seed
        elif target_phenomenon == 8: # 磁気嵐 (手札相互シャッフル交換)
            pass
        elif target_phenomenon == 9: # 日食 (守護神割り当て)
            if sim.state.get_guardian(0) > 0 and sim.state.get_guardian(1) > 0:
                return seed
                
    # 暖流用の探索 (初期HPを40にする)
    for seed in range(5000):
        sim = SimulationRunner()
        sim.state.seed_rng(seed)
        sim.set_status(player=0, hp=40, mp=10, money=10)
        sim.set_status(player=1, hp=40, mp=10, money=10)
        sim.state.set_true_hand(0, 0, string_of_fate_id)
        sim.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
        sim.step(godfield_core.ActionType.ACTION_TARGET_SELF)
        if target_phenomenon == 6: # 暖流
            if sim.state.get_hp(0) == 90:
                return seed

    # 磁気嵐用の探索 (手札がある状態)
    for seed in range(5000):
        sim = SimulationRunner()
        sim.state.seed_rng(seed)
        sim.set_status(player=0, hp=99, mp=10, money=10)
        sim.set_status(player=1, hp=99, mp=10, money=10)
        sim.state.set_true_hand(0, 0, string_of_fate_id)
        sim.state.set_true_hand(0, 1, 10) # 適当なカードA
        sim.state.set_true_hand(0, 2, 11) # 適当なカードB
        sim.state.set_true_hand(1, 0, 12) # 適当なカードC
        sim.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
        sim.step(godfield_core.ActionType.ACTION_TARGET_SELF)
        if target_phenomenon == 8: # 磁気嵐
            h0 = [sim.state.get_true_hand(0, idx) for idx in range(18) if sim.state.get_true_hand(0, idx) != -1]
            h1 = [sim.state.get_true_hand(1, idx) for idx in range(18) if sim.state.get_true_hand(1, idx) != -1]
            if len(h1) > 0 and h1[0] in [10, 11] and int(sim.state.get_sickness(0)) == 0:
                if sim.state.get_hp(0) == 99 and sim.state.get_guardian(0) == 0:
                    return seed

    raise ValueError(f"Could not find seed for phenomenon {target_phenomenon}")


def test_afterglow():
    """夕焼け: 全員熱病"""
    seed = find_seed_for_phenomenon(0)
    sim = SimulationRunner()
    sim.state.seed_rng(seed)
    sim.set_hand(0, ["sundries/string-of-fate"])
    sim.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
    sim.step(godfield_core.ActionType.ACTION_TARGET_SELF)
    
    assert int(sim.state.get_sickness(0)) == 2 # 熱病
    assert int(sim.state.get_sickness(1)) == 2 # 熱病


def test_dense_fog():
    """濃霧: 全員霧"""
    seed = find_seed_for_phenomenon(1)
    sim = SimulationRunner()
    sim.state.seed_rng(seed)
    sim.set_hand(0, ["sundries/string-of-fate"])
    sim.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
    sim.step(godfield_core.ActionType.ACTION_TARGET_SELF)
    
    assert sim.state.get_curses(0, godfield_core.CurseType.CURSE_FOG)
    assert sim.state.get_curses(1, godfield_core.CurseType.CURSE_FOG)


def test_tornado():
    """竜巻: 全員HP 1"""
    seed = find_seed_for_phenomenon(3)
    sim = SimulationRunner()
    sim.state.seed_rng(seed)
    sim.set_hand(0, ["sundries/string-of-fate"])
    sim.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
    sim.step(godfield_core.ActionType.ACTION_TARGET_SELF)
    
    assert sim.state.get_hp(0) == 1
    assert sim.state.get_hp(1) == 1


def test_gigantic_tub_self():
    """巨大なタライ (自分に当たる): 防御不可、即50ダメージ"""
    seed = find_seed_for_phenomenon(4)
    sim = SimulationRunner()
    sim.state.seed_rng(seed)
    sim.set_hand(0, ["sundries/string-of-fate"])
    sim.set_status(player=0, hp=80)
    sim.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
    sim.step(godfield_core.ActionType.ACTION_TARGET_SELF)
    
    assert sim.state.get_hp(0) == 30 # 80 - 50 = 30


def test_gigantic_tub_opp():
    """巨大なタライ (相手に当たる): 光属性50の防御フェイズ起動"""
    seed = find_seed_for_phenomenon(400)
    sim = SimulationRunner()
    sim.state.seed_rng(seed)
    sim.set_hand(0, ["sundries/string-of-fate"])
    sim.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
    sim.step(godfield_core.ActionType.ACTION_TARGET_SELF)
    
    assert sim.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
    assert sim.state.defender_id == 1
    assert sim.state.attacker_id == 0
    assert sim.state.pending_attack_source_id == find_card_by_name("phenomena/gigantic-tub")
    assert sim.state.pending_attack_power == 50
    assert sim.state.pending_attack_element == godfield_core.Element.ELEM_LIGHT


def test_black_hole():
    """ブラックホール: 相手に対して全体攻撃闇属性30防御フェイズ起動"""
    seed = find_seed_for_phenomenon(5)
    sim = SimulationRunner()
    sim.state.seed_rng(seed)
    sim.set_hand(0, ["sundries/string-of-fate"])
    sim.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
    sim.step(godfield_core.ActionType.ACTION_TARGET_SELF)
    
    assert sim.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
    assert sim.state.defender_id == 1
    assert sim.state.attacker_id == 0
    assert sim.state.pending_attack_source_id == find_card_by_name("phenomena/black-hole")
    assert sim.state.pending_attack_power == 30
    assert sim.state.pending_attack_element == godfield_core.Element.ELEM_DARKNESS
    assert sim.state.pending_is_group_attack == True


def test_warm_current():
    """暖流: 自身HP+50"""
    seed = find_seed_for_phenomenon(6)
    sim = SimulationRunner()
    sim.state.seed_rng(seed)
    sim.set_hand(0, ["sundries/string-of-fate"])
    sim.set_status(player=0, hp=40)
    sim.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
    sim.step(godfield_core.ActionType.ACTION_TARGET_SELF)
    
    assert sim.state.get_hp(0) == 90 # 40 + 50 = 90


def test_gold_mountain():
    """金山: お互いのお金合計が集約"""
    seed = find_seed_for_phenomenon(7)
    sim = SimulationRunner()
    sim.state.seed_rng(seed)
    sim.set_hand(0, ["sundries/string-of-fate"])
    sim.set_status(player=0, money=10)
    sim.set_status(player=1, money=20)
    sim.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
    sim.step(godfield_core.ActionType.ACTION_TARGET_SELF)
    
    m0 = sim.state.get_money(0)
    m1 = sim.state.get_money(1)
    # 合計 30 がどちらか一方に集約し、もう一方は 0 になる
    assert (m0 == 30 and m1 == 0) or (m0 == 0 and m1 == 30)


def test_solar_eclipse():
    """日食: 重複しない守護神が両者にセット"""
    seed = find_seed_for_phenomenon(9)
    sim = SimulationRunner()
    sim.state.seed_rng(seed)
    sim.set_hand(0, ["sundries/string-of-fate"])
    sim.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
    sim.step(godfield_core.ActionType.ACTION_TARGET_SELF)
    
    g0 = sim.state.get_guardian(0)
    g1 = sim.state.get_guardian(1)
    
    assert g0 in range(1, 11)
    assert g1 in range(1, 11)
    assert g0 != g1 # 重複しない！


def test_magnetic_storm():
    """磁気嵐: 手札相互交換 & known_to_opp 追跡"""
    seed = find_seed_for_phenomenon(8)
    sim = SimulationRunner()
    sim.state.seed_rng(seed)
    
    # プレイヤー 0: ひも + 銅のこん棒 (ID 5) + 天空のよろい (確実にある)
    # プレイヤー 1: 神の盾 (確実にある)
    fate_id = find_card_by_name("sundries/string-of-fate")
    card_a = find_card_by_name("weapons/bronze-club")
    card_b = find_card_by_name("armor/sky-armor")
    card_c = find_card_by_name("armor/god-shield")
    
    sim.state.set_true_hand(0, 0, fate_id)
    sim.state.set_true_hand(0, 1, card_a)
    sim.state.set_true_hand(0, 2, card_b)
    sim.state.set_is_known_to_opp(0, 1, True)  # 銅のこん棒は相手に知られている
    sim.state.set_is_known_to_opp(0, 2, False) # 天空のよろいは相手に知られていない
    
    sim.state.set_true_hand(1, 0, card_c)
    sim.state.set_is_known_to_opp(1, 0, False) # 神の盾は相手に知られていない
    
    # ひもを使用
    sim.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)
    sim.step(godfield_core.ActionType.ACTION_TARGET_SELF)
    
    # 分配後は：
    # プールは [card_a, card_b, card_c]。
    # 元の有効枚数は P0: 2枚, P1: 1枚。
    # 分配された結果、P0 の true_hand の 0, 1 スロットに 2枚、 P1 の 0 スロットに 1枚が配置される。
    # (ひも使用による通常ドローが最後に入って P0 に 1枚新規追加されるため、 P0 は計 3枚になる。)
    # 磁気嵐でシャッフルされて配られたカードについて、 known_to_opp が正しく設定されているか。
    
    # 元々 P0 の持ち物: card_a (known), card_b (unknown)
    # 元々 P1 の持ち物: card_c (unknown)
    
    # シャッフル後の手札スロット（ドローカード除く元のスロット）を調査
    # ひも分のドローは sim.step() で解決されて引かれているため、
    # P0 の 2枚のスロットと P1 の 1枚のスロットを確認。
    for p in [0, 1]:
        slots = 2 if p == 0 else 1
        for i in range(slots):
            cid = sim.state.get_true_hand(p, i)
            known = sim.state.get_is_known_to_opp(p, i)
            
            # 元の持ち主と配られた先を判定
            if p == 0:
                if cid == card_c:
                    # 元々 P1 の持ち物だった card_c が P0 に来た ➡ P1 は知っている
                    assert known == True
                elif cid == card_a:
                    # 自分に戻ってきた card_a ➡ 元々 known だったので known を維持
                    assert known == True
                elif cid == card_b:
                    # 自分に戻ってきた card_b ➡ 元々 unknown だったので unknown を維持
                    assert known == False
            else: # p == 1
                if cid in [card_a, card_b]:
                    # 元々 P0 の持ち物だったカードが P1 に来た ➡ P0 は知っている
                    assert known == True
                elif cid == card_c:
                    # 自分に戻ってきた card_c ➡ 元々 unknown だったので維持
                    assert known == False
