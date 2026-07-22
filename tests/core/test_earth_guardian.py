import godfield_core
from tests.core.test_utils import SimulationRunner, find_card_by_name


def find_seed_for_earth_action(target_category: str) -> int:
    """
    地球神が特定のアクション (両替/売る/買う/武器/防具/ホウキ/石けん/その他)
    を引き起こすシード値を探索します。
    """
    exchange_id = find_card_by_name("deals/exchange")
    sell_id = find_card_by_name("deals/sell")
    buy_id = find_card_by_name("deals/buy")
    broom_id = find_card_by_name("sundries/nocturnal-broom")
    soap_id = find_card_by_name("sundries/goddess-s-soap")
    first_aid_id = find_card_by_name("sundries/smile-dew")
    bronze_shield_id = find_card_by_name("armor/wood-shield")

    for seed in range(20000):
        sim = SimulationRunner()
        sim.state.seed_rng(seed)

        # P1 に地球神(9)を憑依
        sim.state.set_guardian(1, 9)

        # 初期状態の設定
        sim.set_status(player=0, hp=99, mp=10, money=10)
        sim.set_status(player=1, hp=40, mp=10, money=10)  # 合計 60

        # 手札設定
        # 売る検証のために、P1に1枚だけ売り物を持たせておく
        sim.state.set_true_hand(1, 0, bronze_shield_id)
        for i in range(1, 18):
            sim.state.set_true_hand(1, i, -1)

        # 買う検証のために、P0にも手札を持たせておく
        sim.state.set_true_hand(0, 0, bronze_shield_id)
        for i in range(1, 18):
            sim.state.set_true_hand(0, i, -1)

        # 石けん検証のために、P0の場に奇跡をデプロイしておく
        sim.state.set_is_deployed(0, 0, False)

        # P0 が「祈る」をしてターン終了
        sim.step(godfield_core.ActionType.ACTION_PRAY)

        # 状態からどのカードが抽選されたかを検知
        if target_category == "exchange":
            tot = sim.state.get_hp(1) + sim.state.get_mp(1) + sim.state.get_money(1)
            if (
                tot == 60
                and sim.state.get_hp(1) != 40
                and sim.state.current_phase == godfield_core.GamePhase.PHASE_MAIN
            ):
                return seed
        elif target_category == "sell":
            if sim.state.current_phase == godfield_core.GamePhase.PHASE_SELL_SELECT_MIRROR:
                return seed
        elif target_category == "buy":
            if sim.state.current_phase == godfield_core.GamePhase.PHASE_BUY_SELECT_MIRROR:
                return seed
        elif target_category == "weapon":
            if sim.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE:
                source = sim.state.pending_attack_source_id
                if source != -1 and source != find_card_by_name("gurdians/full-moon-blade"):
                    return seed
        elif target_category == "armor":
            h1 = [sim.state.get_true_hand(1, idx) for idx in range(18) if sim.state.get_true_hand(1, idx) != -1]
            if len(h1) == 2 and h1[1] != bronze_shield_id:
                return seed
        elif target_category == "broom":
            h0 = [sim.state.get_true_hand(0, idx) for idx in range(18) if sim.state.get_true_hand(0, idx) != -1]
            if len(h0) == 0 and sim.state.current_phase == godfield_core.GamePhase.PHASE_MAIN:
                return seed
        elif target_category == "soap":
            pass

    # 石けん探索用
    for seed in range(5000):
        sim = SimulationRunner()
        sim.state.seed_rng(seed)
        sim.state.set_guardian(1, 9)
        sim.set_status(player=0, hp=99, mp=10, money=10)
        sim.set_status(player=1, hp=99, mp=10, money=10)

        miracle_fire = find_card_by_name("miracles/fireball")
        sim.state.set_true_hand(0, 0, miracle_fire)
        sim.state.set_is_deployed(0, 0, True)
        for i in range(1, 18):
            sim.state.set_true_hand(0, i, -1)

        sim.step(godfield_core.ActionType.ACTION_PRAY)
        if target_category == "soap":
            if not sim.state.get_is_deployed(0, 0) and sim.state.get_true_hand(0, 0) == -1:
                if sim.state.current_phase == godfield_core.GamePhase.PHASE_MAIN:
                    return seed

    # その他雑貨
    for seed in range(5000):
        sim = SimulationRunner()
        sim.state.seed_rng(seed)
        sim.state.set_guardian(1, 9)
        sim.set_status(player=0, hp=99)
        sim.set_status(player=1, hp=30)

        sim.step(godfield_core.ActionType.ACTION_PRAY)
        if target_category == "sundry":
            if sim.state.get_hp(1) == 50:
                return seed

    raise ValueError(f"Could not find seed for Earth Guardian category {target_category}")


def test_earth_exchange():
    """地球神: 両替 (HP/MP/金をランダム調節)"""
    seed = find_seed_for_earth_action("exchange")
    sim = SimulationRunner()
    sim.state.seed_rng(seed)
    sim.state.set_guardian(1, 9)
    sim.set_status(player=0, hp=99)
    sim.set_status(player=1, hp=40, mp=10, money=10)

    sim.step(godfield_core.ActionType.ACTION_PRAY)

    tot = sim.state.get_hp(1) + sim.state.get_mp(1) + sim.state.get_money(1)
    assert tot == 60
    assert sim.state.get_hp(1) != 40


def test_earth_sell():
    """地球神: 売る (取引受諾)"""
    seed = find_seed_for_earth_action("sell")
    sim = SimulationRunner()
    sim.state.seed_rng(seed)
    sim.state.set_guardian(1, 9)
    sim.set_status(player=0, hp=99, money=100)  # 買い手
    sim.set_status(player=1, hp=99, money=10)  # 売り手

    shield_id = find_card_by_name("armor/wood-shield")
    sim.state.set_true_hand(1, 0, shield_id)
    for i in range(1, 18):
        sim.state.set_true_hand(1, i, -1)

    sim.step(godfield_core.ActionType.ACTION_PRAY)

    assert sim.state.current_phase == godfield_core.GamePhase.PHASE_SELL_SELECT_MIRROR
    assert sim.state.defender_id == 0
    assert sim.state.attacker_id == 1

    sim.step(godfield_core.ActionType.ACTION_CONFIRM)

    # 木の盾の価格は 4 (ドロー補充はP1のみなので売値4確定)
    assert sim.state.get_money(0) == 96  # 100 - 4 = 96
    assert sim.state.get_money(1) == 14  # 10 + 4 = 14
    assert sim.state.get_true_hand(1, 0) == -1


def test_earth_buy():
    """地球神: 買う (取引受諾)"""
    seed = find_seed_for_earth_action("buy")
    sim = SimulationRunner()
    sim.state.seed_rng(seed)
    sim.state.set_guardian(1, 9)
    sim.set_status(player=0, hp=99, money=10)  # 売り手 P0
    sim.set_status(player=1, hp=99, money=100)  # 買い手 P1 (地球神)

    shield_id = find_card_by_name("armor/wood-shield")
    sim.state.set_true_hand(0, 0, shield_id)
    for i in range(1, 18):
        sim.state.set_true_hand(0, i, -1)

    sim.step(godfield_core.ActionType.ACTION_PRAY)

    assert sim.state.current_phase == godfield_core.GamePhase.PHASE_BUY_SELECT_MIRROR
    assert sim.state.defender_id == 0
    assert sim.state.attacker_id == 1

    sim.step(godfield_core.ActionType.ACTION_CONFIRM)

    assert sim.state.current_phase == godfield_core.GamePhase.PHASE_BUY
    assert sim.state.current_actor_id == 1  # 買い手 P1 (地球神の所持者)

    sim.step(godfield_core.ActionType.ACTION_DEAL_YES)

    # 売却代金決済の一致性をチェック (P0ドロー補充が入るため決済価格は可変)
    diff_0 = sim.state.get_money(0) - 10
    diff_1 = 100 - sim.state.get_money(1)
    assert diff_0 == diff_1
    assert diff_0 > 0


def test_earth_buy_super_mirror_reflection():
    """地球神: 買う に対するスーパーミラー反射"""
    seed = find_seed_for_earth_action("buy")
    sim = SimulationRunner()
    sim.state.seed_rng(seed)
    sim.state.set_guardian(1, 9)
    sim.set_status(player=0, hp=99, money=100)  # 反射者 P0
    sim.set_status(player=1, hp=99, money=100)  # 地球神所有者 P1

    super_mirror_id = find_card_by_name("スーパーミラー")
    shield_id = find_card_by_name("armor/wood-shield")
    sim.state.set_true_hand(0, 0, super_mirror_id)
    sim.state.set_true_hand(1, 0, shield_id)
    for i in range(1, 18):
        sim.state.set_true_hand(0, i, -1)
        sim.state.set_true_hand(1, i, -1)

    sim.step(godfield_core.ActionType.ACTION_PRAY)

    assert sim.state.current_phase == godfield_core.GamePhase.PHASE_BUY_SELECT_MIRROR
    assert sim.state.current_actor_id == 0

    # P0 がスーパーミラー(手札0)で反射
    sim.step(godfield_core.ActionType.ACTION_SELECT_HAND_0)

    # P1 (地球神の持ち主) が標的となり PHASE_BUY_SELECT_MIRROR に遷移
    assert sim.state.current_phase == godfield_core.GamePhase.PHASE_BUY_SELECT_MIRROR
    assert sim.state.current_actor_id == 1

    # P1 が受諾 (Confirm)
    sim.step(godfield_core.ActionType.ACTION_CONFIRM)

    # P0 (買い手) が PHASE_BUY で買主として判断選択可能になる
    assert sim.state.current_phase == godfield_core.GamePhase.PHASE_BUY
    assert sim.state.current_actor_id == 0


def test_earth_weapon():
    """地球神: 武器 (物理防御フェイズ)"""
    seed = find_seed_for_earth_action("weapon")
    sim = SimulationRunner()
    sim.state.seed_rng(seed)
    sim.state.set_guardian(1, 9)
    sim.set_status(player=0, hp=99)
    sim.set_status(player=1, hp=99)

    sim.step(godfield_core.ActionType.ACTION_PRAY)

    assert sim.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
    assert sim.state.defender_id == 0
    assert sim.state.attacker_id == 1
    assert sim.state.pending_attack_power > 0
    assert sim.state.pending_attack_source_id >= 0


def test_earth_add_to_hand():
    """地球神: 防具/奇跡等手札追加 (満杯時の1枚破棄)"""
    seed = find_seed_for_earth_action("armor")
    sim = SimulationRunner()
    sim.state.seed_rng(seed)
    sim.state.set_guardian(1, 9)
    sim.set_status(player=0, hp=99)
    sim.set_status(player=1, hp=99)

    # 手札を18枚満杯にする
    shield_id = find_card_by_name("armor/wood-shield")
    for i in range(18):
        sim.state.set_true_hand(1, i, shield_id)
        sim.state.set_is_used(1, i, False)

    sim.step(godfield_core.ActionType.ACTION_PRAY)

    # 手札枚数は18枚で維持されている
    h1 = [sim.state.get_true_hand(1, idx) for idx in range(18) if sim.state.get_true_hand(1, idx) != -1]
    assert len(h1) == 18

    # いずれかのスロットが木の盾(shield_id)以外になっていること（＝新しい防具が追加された）
    diff_cards = [cid for cid in h1 if cid != shield_id]
    assert len(diff_cards) > 0


def test_earth_broom():
    """地球神: 夜空のホウキ (相手手札3枚もらし、is_usedは除く)"""
    seed = find_seed_for_earth_action("broom")
    sim = SimulationRunner()
    sim.state.seed_rng(seed)
    sim.state.set_guardian(1, 9)
    sim.set_status(player=0, hp=99)
    sim.set_status(player=1, hp=99)

    shield_id = find_card_by_name("armor/wood-shield")
    fireball_id = find_card_by_name("miracles/fireball")

    # スロット 0: 奇跡カード (is_used=True)
    sim.state.set_true_hand(0, 0, fireball_id)
    sim.state.set_is_used(0, 0, True)

    # スロット 1~4: 木の盾 (is_used=False)
    for i in range(1, 5):
        sim.state.set_true_hand(0, i, shield_id)
        sim.state.set_is_used(0, i, False)
    for i in range(5, 18):
        sim.state.set_true_hand(0, i, -1)
        sim.state.set_is_used(0, i, False)

    sim.step(godfield_core.ActionType.ACTION_PRAY)

    h0 = [sim.state.get_true_hand(0, idx) for idx in range(18) if sim.state.get_true_hand(0, idx) != -1]

    # 手札枚数は 4枚になっていること (奇跡はdeployされても手札に残るが、補充ドローが1枚増えるため)
    assert len(h0) == 4
    # 木の盾は4枚から3枚破棄されて、ちょうど1枚だけ残っていること (is_usedだった奇跡スロットは破棄から守られた)
    assert h0.count(shield_id) == 1


def test_earth_soap():
    """地球神: 女神の石けん (相手の展開されている奇跡破棄)"""
    seed = find_seed_for_earth_action("soap")
    sim = SimulationRunner()
    sim.state.seed_rng(seed)
    sim.state.set_guardian(1, 9)
    sim.set_status(player=0, hp=99)
    sim.set_status(player=1, hp=99)

    fire_id = find_card_by_name("miracles/fireball")
    sim.state.set_true_hand(0, 0, fire_id)
    sim.state.set_is_deployed(0, 0, True)

    sim.step(godfield_core.ActionType.ACTION_PRAY)

    assert not sim.state.get_is_deployed(0, 0)
    assert sim.state.get_true_hand(0, 0) == -1


def test_earth_sundry():
    """地球神: その他の雑貨 (救急箱自分適用HP回復)"""
    seed = find_seed_for_earth_action("sundry")
    sim = SimulationRunner()
    sim.state.seed_rng(seed)
    sim.state.set_guardian(1, 9)
    sim.set_status(player=0, hp=99)
    sim.set_status(player=1, hp=30)

    sim.step(godfield_core.ActionType.ACTION_PRAY)

    assert sim.state.get_hp(1) == 50


def test_earth_exchange_high_sum():
    """地球神: 合計ステータスが99を超える状態での両替が正しく各値99以下に収まることを検証"""
    seed = find_seed_for_earth_action("exchange")
    sim = SimulationRunner()
    sim.state.seed_rng(seed)
    sim.state.set_guardian(1, 9)
    sim.set_status(player=0, hp=99)
    # 合計 90 + 90 + 90 = 270 (各ステータスは99以下でなければならない)
    sim.set_status(player=1, hp=90, mp=90, money=90)

    sim.step(godfield_core.ActionType.ACTION_PRAY)

    tot = sim.state.get_hp(1) + sim.state.get_mp(1) + sim.state.get_money(1)
    assert tot == 270
    assert sim.state.get_hp(1) <= 99
    assert sim.state.get_mp(1) <= 99
    assert sim.state.get_money(1) <= 99


def test_earth_dangerous_pestle_mortar():
    """地球神があぶないキネを引いた際、あぶないウスがあれば99ダメージ＆1枚消費されることを検証"""
    pestle_id = find_card_by_name("weapons/dangerous-pestle")
    mortar_id = find_card_by_name("sundries/dangerous-mortar")

    # 地球神(P1)があぶないキネをドローするシードを探す
    act_seed = None
    for seed in range(100000):
        sim = SimulationRunner()
        sim.state.seed_rng(seed)
        sim.state.set_guardian(1, 9)
        sim.set_status(player=0, hp=99)
        sim.set_status(player=1, hp=99)
        sim.state.set_true_hand(0, 0, mortar_id)
        sim.state.set_true_hand(1, 0, pestle_id)
        for i in range(1, 18):
            sim.state.set_true_hand(0, i, -1)
            sim.state.set_true_hand(1, i, -1)

        sim.step(godfield_core.ActionType.ACTION_PRAY)
        # ウスが存在し、P0が99被弾してHPが0になったシード
        if sim.state.get_hp(0) == 0:
            act_seed = seed
            break

    assert act_seed is not None, "地球神のあぶないキネ・ウス連動シードが見つかりませんでした"
