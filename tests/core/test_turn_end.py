import godfield_core
from godfield_core import ActionType, GamePhase, SicknessType
from tests.core.test_utils import SimulationRunner, find_card_by_name


def test_sun_amulet_revive():
    """
    検証内容: 太陽のお守り（Sun Amulet）による死亡時自動復活。
    - プレイヤー0がHP 0で死亡した際、手札にある太陽のお守りが自動消費され、HP 10で復活することを確認。
    - 太陽のお守りが消費されたスロットは CARD_EMPTY になり、ターン終了時に新規カードがドローされることを確認。
    """
    runner = SimulationRunner()
    amulet_id = find_card_by_name("太陽のお守り")
    shield_id = find_card_by_name("革の服")

    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_hp(0, 0)  # 即死状態にする
    runner.state.set_true_hand(0, 0, amulet_id)
    runner.state.set_true_hand(0, 1, shield_id)

    # 「捨てる」フェイズを経由してターンを終了させることで自動終了解決（PHASE_END）を起動
    runner.step(ActionType.ACTION_DISCARD)
    runner.perform_defense([1])

    # HPが10に復活し、ターンは相手(1)のMAINになっていること
    assert runner.state.get_hp(0) == 10
    assert runner.state.current_phase == GamePhase.PHASE_MAIN
    assert runner.state.current_actor_id == 1

    # 太陽のお守りが消費され、スロット0には別の新規カードが補充されていること
    assert runner.state.get_true_hand(0, 0) != godfield_core.CARD_EMPTY
    assert runner.state.get_true_hand(0, 0) != amulet_id


def test_ascension_bow_trigger_and_defense():
    """
    検証内容: 昇天弓（Ascension Bow）による死亡時自動反撃。
    - 太陽のお守りが無い状態でHP 0になった際、手札の「昇天弓」が起動し、相手(P1)に対して「光属性・ATK30・75%命中」の攻撃を行うこと。
    - 反撃時に命中（RNGシードで調整）した場合、相手が防御するフェイズ（PHASE_DEFENSE）に移行することを確認。
    - 相手が防御を完了した後、攻撃を行った本人は死亡したままゲーム終了になることを確認。
    """
    bow_id = find_card_by_name("昇天弓")
    shield_id = find_card_by_name("革の服")

    # 75%の命中率で必ず命中するシード（例: seed=0）を使用する
    runner = SimulationRunner()
    runner.state.seed_rng(0)
    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_hp(0, 0)
    runner.state.set_hp(1, 40)
    runner.state.set_true_hand(0, 0, bow_id)
    runner.state.set_true_hand(0, 1, shield_id)

    # 「捨てる」フェイズを経由してターン終了処理を起動
    runner.step(ActionType.ACTION_DISCARD)
    runner.perform_defense([1])

    # 相手(1)の防御フェイズに移行していることを確認（一時中断状態）
    assert runner.state.current_phase == GamePhase.PHASE_DEFENSE
    assert runner.state.current_actor_id == 1
    assert runner.state.attacker_id == 0
    assert runner.state.defender_id == 1
    assert runner.state.pending_attack_power == 30
    assert runner.state.pending_attack_element == godfield_core.ELEM_LIGHT

    # 相手が防御を確定
    runner.step(ActionType.ACTION_CONFIRM)

    # 攻撃を行ったプレイヤー0は死亡しているため、ゲーム終了になること
    assert runner.state.is_done is True
    assert runner.state.p0_reward == -1.0
    assert runner.state.p1_reward == 1.0


def test_sickness_escalation_heaven_instant_death():
    """
    検証内容: 天国病悪化による即死と復活/反撃の連動フロー。
    - プレイヤー0が「天国病」の状態で、悪化判定が成功（確率5%）した際、即座に死亡（HP=0）することを確認。
    - 死亡時に「太陽のお守り」を持っていれば、そのままHP10で復活して生き残ることを確認。
    """
    shield_id = find_card_by_name("革の服")
    amulet_id = find_card_by_name("太陽のお守り")

    # 5%の悪化判定を確実に引くシードを探索
    escalate_seed = None
    for seed in range(500):
        test_run = SimulationRunner()
        test_run.state.seed_rng(seed)
        test_run.state.current_phase = GamePhase.PHASE_MAIN
        test_run.state.current_actor_id = 0
        test_run.state.set_hp(0, 40)
        test_run.state.set_sickness(0, SicknessType.SICKNESS_HEAVEN)
        test_run.state.set_true_hand(0, 0, shield_id)

        test_run.step(ActionType.ACTION_DISCARD)
        test_run.perform_defense([0])

        # 天国病悪化による死亡によって、ゲーム終了（is_done=True）しているシードを探す
        if test_run.state.is_done:
            escalate_seed = seed
            break

    assert escalate_seed is not None, "天国病悪化用シードが見つかりませんでした"

    # 発症・お守り復活確認
    runner = SimulationRunner()
    runner.state.seed_rng(escalate_seed)
    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_hp(0, 40)
    runner.state.set_sickness(0, SicknessType.SICKNESS_HEAVEN)
    runner.state.set_true_hand(0, 0, amulet_id)
    runner.state.set_true_hand(0, 1, shield_id)

    runner.step(ActionType.ACTION_DISCARD)
    runner.perform_defense([1])

    # 悪化即死したが、お守りで復活。
    # 発作による死亡時は天国病の回復（+5）はスキップされるため、最終HPは10になること
    assert runner.state.get_hp(0) == 10
    assert runner.state.is_done is False


def test_sickness_escalation_hell_to_heaven():
    """
    検証内容: 地獄病から天国病への悪化判定。
    - 地獄病のプレイヤー0が、5%の悪化確率を引き当てた際、病気が天国病（Heaven）へと悪化することを確認します。
    """
    shield_id = find_card_by_name("革の服")

    # 5%の悪化判定を確実に引くシードを探索
    hell_escalate_seed = None
    for seed in range(500):
        test_run = SimulationRunner()
        test_run.state.seed_rng(seed)
        test_run.state.current_phase = GamePhase.PHASE_MAIN
        test_run.state.current_actor_id = 0
        test_run.state.set_hp(0, 40)
        test_run.state.set_sickness(0, SicknessType.SICKNESS_HELL)
        test_run.state.set_true_hand(0, 0, shield_id)

        test_run.step(ActionType.ACTION_DISCARD)
        test_run.perform_defense([0])

        # 悪化して天国病になっているシードを探す
        if test_run.state.get_sickness(0) == SicknessType.SICKNESS_HEAVEN:
            hell_escalate_seed = seed
            break

    assert hell_escalate_seed is not None, "地獄病悪化用シードが見つかりませんでした"

    runner = SimulationRunner()
    runner.state.seed_rng(hell_escalate_seed)
    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_hp(0, 40)
    runner.state.set_sickness(0, SicknessType.SICKNESS_HELL)
    runner.state.set_true_hand(0, 0, shield_id)

    runner.step(ActionType.ACTION_DISCARD)
    runner.perform_defense([0])

    # 天国病に悪化していること
    assert runner.state.get_sickness(0) == SicknessType.SICKNESS_HEAVEN


def test_sickness_damage_and_healing_turn_end():
    """
    検証内容: 各種病気によるターン終了時ダメージ/回復処理。
    - 地獄病 (Hell) = 5 ダメージ
    - 天国病 (Heaven) = 5 回復 (上限99クランプ)
    """
    shield_id = find_card_by_name("革の服")

    # 1. 地獄病でのダメージ (悪化しないシードを適当に使うか、ダメージ解決を確認)
    runner = SimulationRunner()
    runner.state.seed_rng(0)  # 悪化が起こらないシード
    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_hp(0, 10)
    runner.state.set_sickness(0, SicknessType.SICKNESS_HELL)
    runner.state.set_true_hand(0, 0, shield_id)

    runner.step(ActionType.ACTION_DISCARD)
    runner.perform_defense([0])

    # 地獄病の5ダメを受けてHPが5になっていること
    assert runner.state.get_hp(0) == 5

    # 2. 天国病での回復と上限クランプ
    runner2 = SimulationRunner()
    runner2.state.seed_rng(0)
    runner2.state.current_phase = GamePhase.PHASE_MAIN
    runner2.state.current_actor_id = 0
    runner2.state.set_hp(0, 97)
    runner2.state.set_sickness(0, SicknessType.SICKNESS_HEAVEN)
    runner2.state.set_true_hand(0, 0, shield_id)

    runner2.step(ActionType.ACTION_DISCARD)
    runner2.perform_defense([0])

    # 天国病で回復するが99にクランプされること
    assert runner2.state.get_hp(0) == 99


def test_guardian_action_mars_fire_attack():
    """
    検証内容: ターン終了時における相手の守護神「火星神」の確率的攻撃解決。
    - 25%の確率で「火星神（Mars）」が行動するシードにおいて、相手(P1)の火星神がプレイヤー0に対して火属性攻撃を放ち、P0の防御フェイズへと移行することを確認。
    """
    shield_id = find_card_by_name("革の服")

    # 25%の守護神行動を引くシードを探索
    act_seed = None
    for seed in range(500):
        test_run = SimulationRunner()
        test_run.state.seed_rng(seed)
        test_run.state.current_phase = GamePhase.PHASE_MAIN
        test_run.state.current_actor_id = 0
        test_run.state.set_hp(0, 40)
        test_run.state.set_hp(1, 40)
        test_run.state.set_guardian(1, 1)  # P1に火星神(1)を設定
        test_run.state.set_true_hand(0, 0, shield_id)

        test_run.step(ActionType.ACTION_DISCARD)
        test_run.perform_defense([0])

        if test_run.state.current_phase == GamePhase.PHASE_DEFENSE:
            act_seed = seed
            break

    assert act_seed is not None, "守護神行動用シードが見つかりませんでした"

    runner = SimulationRunner()
    runner.state.seed_rng(act_seed)
    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_hp(0, 40)
    runner.state.set_hp(1, 40)
    runner.state.set_guardian(1, 1)
    runner.state.set_true_hand(0, 0, shield_id)

    runner.step(ActionType.ACTION_DISCARD)
    runner.perform_defense([0])

    # P0が被弾・防御状態になっていること
    assert runner.state.current_phase == GamePhase.PHASE_DEFENSE
    assert runner.state.current_actor_id == 0
    assert runner.state.attacker_id == 1
    assert runner.state.defender_id == 0
    assert runner.state.pending_attack_element == godfield_core.ELEM_FIRE


def test_guardian_action_venus_golden_drain():
    """
    検証内容: 金星神の「罰金」ドレイン攻撃。
    - 相手(P1)の金星神が行動した際、プレイヤー0のお金を直接ドレイン（お金 -> MP -> HP）し、奪ったお金がP1へ加算されることを確認。
    """
    shield_id = find_card_by_name("革の服")

    # 罰金（防御フェイズ PHASE_DEFENSE 起動）となるシードを探す
    act_seed = None
    for seed in range(500):
        test_run = SimulationRunner()
        test_run.state.seed_rng(seed)
        test_run.state.current_phase = GamePhase.PHASE_MAIN
        test_run.state.current_actor_id = 0
        test_run.state.set_hp(0, 40)
        test_run.state.set_hp(1, 40)
        test_run.state.set_money(0, 10)
        test_run.state.set_money(1, 10)
        test_run.state.set_guardian(1, 8)  # 金星神(8)
        test_run.state.set_true_hand(0, 0, shield_id)

        test_run.step(ActionType.ACTION_DISCARD)
        test_run.perform_defense([0])

        if test_run.state.current_phase == GamePhase.PHASE_SUNDRY_SELECT_MIRROR and test_run.state.pending_attack_source_id == find_card_by_name("罰金"):
            act_seed = seed
            break

    assert act_seed is not None, "金星神行動用シードが見つかりませんでした"

    runner = SimulationRunner()
    runner.state.seed_rng(act_seed)
    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_hp(0, 40)
    runner.state.set_hp(1, 40)
    runner.state.set_money(0, 10)
    runner.state.set_money(1, 10)
    runner.state.set_guardian(1, 8)
    runner.state.set_true_hand(0, 0, shield_id)

    runner.step(ActionType.ACTION_DISCARD)
    runner.perform_defense([0])

    # 雑貨反射選択フェイズになっていることを確認
    assert runner.state.current_phase == GamePhase.PHASE_SUNDRY_SELECT_MIRROR

    # 防御側(P0)が無防備CONFIRMで被弾
    runner.step(ActionType.ACTION_CONFIRM)

    # P0からお金がドレインされ(10 -> 7)、P1のお金が増えていること(10 -> 13)
    assert runner.state.get_money(0) == 7
    assert runner.state.get_money(1) == 13


def test_guardian_action_neptune_support_healing():
    """
    検証内容: 海王神の回復支援。
    - 相手(P1)の海王神が行動した際、P1自身がHPまたはMP回復、あるいは状態異常治療を受けることを確認。
    """
    shield_id = find_card_by_name("革の服")

    act_seed = None
    for seed in range(500):
        test_run = SimulationRunner()
        test_run.state.seed_rng(seed)
        test_run.state.current_phase = GamePhase.PHASE_MAIN
        test_run.state.current_actor_id = 0
        test_run.state.set_hp(0, 40)
        test_run.state.set_hp(1, 20)
        test_run.state.set_mp(1, 10)
        test_run.state.set_guardian(1, 7)  # 海王神(7)
        test_run.state.set_true_hand(0, 0, shield_id)

        test_run.step(ActionType.ACTION_DISCARD)
        test_run.perform_defense([0])

        if test_run.state.get_hp(1) > 20 or test_run.state.get_mp(1) > 10:
            act_seed = seed
            break

    assert act_seed is not None, "海王神行動用シードが見つかりませんでした"

    runner = SimulationRunner()
    runner.state.seed_rng(act_seed)
    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_hp(0, 40)
    runner.state.set_hp(1, 20)
    runner.state.set_mp(1, 10)
    runner.state.set_guardian(1, 7)
    runner.state.set_true_hand(0, 0, shield_id)

    runner.step(ActionType.ACTION_DISCARD)
    runner.perform_defense([0])

    # P1のHPまたはMPが回復していること
    assert (runner.state.get_hp(1) > 20) or (runner.state.get_mp(1) > 10)


def test_simultaneous_death_draw():
    """
    検証内容: 両プレイヤーが同時にHP 0になった場合の引き分け判定。
    - ターン終了の死亡判定において両者のHPが 0 であるとき、ゲームが終了（is_done=True）し、両者の報酬が 0.0f（引き分け）になることを確認。
    """
    shield_id = find_card_by_name("革の服")

    runner = SimulationRunner()
    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_hp(0, 0)
    runner.state.set_hp(1, 0)
    runner.state.set_true_hand(0, 0, shield_id)

    runner.step(ActionType.ACTION_DISCARD)
    runner.perform_defense([0])

    # 引き分け終了
    assert runner.state.is_done is True
    assert runner.state.p0_reward == 0.0
    assert runner.state.p1_reward == 0.0


def test_sickness_only_applies_to_active_player():
    """
    検証内容: 病気ダメージ・悪化判定がターン手番プレイヤー（Active Player）にのみ適用され、待機プレイヤー（Passive Player）には適用されないことの検証。
    - プレイヤー0を手番（Active）とし、手番ではないプレイヤー1（Passive）に「地獄病」を設定します。
    - プレイヤー0がターンを終了した際、プレイヤー1のHPが減少せず、プレイヤー0のみがターン終了処理を通ることを確認します。
    """
    shield_id = find_card_by_name("革の服")

    runner = SimulationRunner()
    runner.state.seed_rng(0)
    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_hp(0, 40)
    runner.state.set_hp(1, 40)
    runner.state.set_sickness(1, SicknessType.SICKNESS_HELL)  # P1 (Passive) が地獄病
    runner.state.set_true_hand(0, 0, shield_id)

    runner.step(ActionType.ACTION_DISCARD)
    runner.perform_defense([0])

    # ターンを終えたP0は無傷、かつ待機側のP1もターン終了の病気ダメージを受けずHP 40を維持していること
    assert runner.state.get_hp(0) == 40
    assert runner.state.get_hp(1) == 40


def test_normal_attack_kill_and_amulet_revive():
    """
    シナリオ1: 通常の攻撃で相手が死亡し、お守りで復活する。
    - P0がP1に対して威力10の攻撃を行う。
    - P1は初期HP 5で、手札に太陽のお守りを持つ。
    - 攻撃を素通しして被弾した際、P1のHPが0になり、お守りによりHP 10で復活することを確認。
    """
    runner = SimulationRunner()
    punch_id = find_card_by_name("パンチ")
    amulet_id = find_card_by_name("太陽のお守り")
    shield_id = find_card_by_name("革の服")

    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_hp(0, 40)
    runner.state.set_hp(1, 2)  # P1のHPは2 (パンチの攻撃力3で即死)
    runner.state.set_true_hand(0, 0, punch_id)
    runner.state.set_true_hand(1, 0, amulet_id)
    runner.state.set_true_hand(1, 1, shield_id)

    # P0が攻撃を選択
    runner.step(ActionType.ACTION_SELECT_HAND_0)
    # P0がP1をターゲットに攻撃確定
    runner.step(ActionType.ACTION_TARGET_OPP)

    # P1の防御フェイズに移行
    assert runner.state.current_phase == GamePhase.PHASE_DEFENSE
    assert runner.state.current_actor_id == 1

    # P1が防御カードを出さずに素通し（Confirm）を選択して被弾
    runner.step(ActionType.ACTION_CONFIRM)

    # 被弾後にHP 0となり、お守りが自動消費されてHP 10で復活することを確認
    # そして手番はP1のMAINフェイズへ移っていること
    assert runner.state.get_hp(1) == 10
    assert runner.state.current_phase == GamePhase.PHASE_MAIN
    assert runner.state.current_actor_id == 1
    assert runner.state.is_done is False


def test_heaven_escalation_death_amulet_revive_sickness_persists():
    """
    シナリオ2: 自分がターン終了時に天国病が悪化（発作）して死亡し、お守りで復活する。
    - 発作による死亡時は天国病のターン終了時回復（+5）は適用されず、HP 10で復活・生存することを確認。
    - 天国病自体は継続（自然治癒せず）していることを確認。
    """
    # 5%の悪化判定を引くシードを探索
    escalate_seed = None
    shield_id = find_card_by_name("革の服")
    for seed in range(500):
        test_run = SimulationRunner()
        test_run.state.seed_rng(seed)
        test_run.state.current_phase = GamePhase.PHASE_MAIN
        test_run.state.current_actor_id = 0
        test_run.state.set_hp(0, 40)
        test_run.state.set_sickness(0, SicknessType.SICKNESS_HEAVEN)
        test_run.state.set_true_hand(0, 0, shield_id)

        test_run.step(ActionType.ACTION_DISCARD)
        test_run.perform_defense([0])

        if test_run.state.is_done:  # 天国病悪化死で終了したシード
            escalate_seed = seed
            break

    assert escalate_seed is not None

    runner = SimulationRunner()
    runner.state.seed_rng(escalate_seed)
    amulet_id = find_card_by_name("太陽のお守り")
    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_hp(0, 40)
    runner.state.set_sickness(0, SicknessType.SICKNESS_HEAVEN)
    runner.state.set_true_hand(0, 0, amulet_id)
    runner.state.set_true_hand(0, 1, shield_id)

    runner.step(ActionType.ACTION_DISCARD)
    runner.perform_defense([1])

    # 悪化即死後、お守り復活(10 HP)のみで、+5回復はスキップされるため最終HPは10になること
    assert runner.state.get_hp(0) == 10
    # 天国病が継続している（0:なし ではなく 4:天国病 であること）
    assert runner.state.get_sickness(0) == SicknessType.SICKNESS_HEAVEN
    assert runner.state.is_done is False


def test_kill_opp_bow_counter_sickness_death_amulet_revive():
    """
    シナリオ3: 相手を倒し昇天弓が起動。
    - P0がP1を撃破する。
    - P1の昇天弓が起動し、P0が被弾して HPが0になる（20 HP -> 0 HP）。
    - P0の手札にある「太陽のお守り」が起動し、HP 10 で復活する。
    - この際、相手（P1）は既に死亡しているため、P1の守護神行動は発生せず、P0の勝利（ゲーム終了）が確定することを確認。
    """
    runner = SimulationRunner()
    # 昇天弓が確実に命中する乱数シード 0 を使用
    runner.state.seed_rng(0)

    punch_id = find_card_by_name("パンチ")
    bow_id = find_card_by_name("昇天弓")
    amulet_id = find_card_by_name("太陽のお守り")
    shield_id = find_card_by_name("革の服")

    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0

    runner.state.set_hp(0, 20)  # 自分(P0)のHPは20
    runner.state.set_hp(1, 3)  # 相手(P1)のHPは3 (パンチで即死)
    runner.state.set_guardian(1, 1)  # 相手に火星神を設定

    runner.state.set_true_hand(0, 0, punch_id)
    runner.state.set_true_hand(0, 1, amulet_id)
    runner.state.set_true_hand(1, 0, bow_id)
    runner.state.set_true_hand(1, 1, shield_id)

    # 1. P0がP1を攻撃
    runner.perform_attack([0])

    # P1の防御フェイズ（Confirmで被弾して死亡させる）
    assert runner.state.current_phase == GamePhase.PHASE_DEFENSE
    assert runner.state.current_actor_id == 1
    runner.step(ActionType.ACTION_CONFIRM)

    # 2. P1死亡に伴い、P1の昇天弓反撃フェイズ（PHASE_DEFENSE, アクターP0）へ移行
    assert runner.state.current_phase == GamePhase.PHASE_DEFENSE
    assert runner.state.current_actor_id == 0
    assert runner.state.attacker_id == 1
    assert runner.state.defender_id == 0

    # 3. P0が反撃を被弾（Confirm）
    runner.step(ActionType.ACTION_CONFIRM)

    # 被弾: 20 - 30 = 0 HP（死亡）。
    # その後、太陽のお守りが起動: HP 10 で復活。
    # 相手P1はすでに死亡しているため、P1の守護神行動は発生せず、ゲームが即時終了してP0の勝利が確定していること。
    assert runner.state.get_hp(0) == 10
    assert runner.state.get_hp(1) == 0
    assert runner.state.is_done is True
    assert runner.state.p0_reward == 1.0  # P0の勝利
    assert runner.state.p1_reward == -1.0


def test_guardian_attack_kills_player_defeat():
    """
    シナリオ4: 相手守護神の攻撃で自分が死亡し、敗北（ゲーム終了）になることの検証。
    - ターン終了時（P0のターンエンド）、相手(P1)の火星神が25%の確率で行動。
    - 火星神の攻撃により、P0が被弾してHPが0になり、お守り等もないためそのまま敗北（is_done=True, p0_reward=-1.0）となることを確認。
    """
    # 守護神行動を引くシードを探索
    act_seed = None
    shield_id = find_card_by_name("革の服")
    for seed in range(500):
        test_run = SimulationRunner()
        test_run.state.seed_rng(seed)
        test_run.state.current_phase = GamePhase.PHASE_MAIN
        test_run.state.current_actor_id = 0
        test_run.state.set_hp(0, 5)  # 自分のHPは5（火星神の最低威力5でも死亡する値）
        test_run.state.set_hp(1, 40)
        test_run.state.set_guardian(1, 1)  # 相手に火星神を設定
        test_run.state.set_true_hand(0, 0, shield_id)

        test_run.step(ActionType.ACTION_DISCARD)
        test_run.perform_defense([0])

        if test_run.state.current_phase == GamePhase.PHASE_DEFENSE:
            act_seed = seed
            break

    assert act_seed is not None

    runner = SimulationRunner()
    runner.state.seed_rng(act_seed)
    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_hp(0, 5)
    runner.state.set_hp(1, 40)
    runner.state.set_guardian(1, 1)
    runner.state.set_true_hand(0, 0, shield_id)

    # ターン終了
    runner.step(ActionType.ACTION_DISCARD)
    runner.perform_defense([0])

    # 相手の守護神による攻撃フェイズへ移行していること
    assert runner.state.current_phase == GamePhase.PHASE_DEFENSE
    assert runner.state.current_actor_id == 0

    # 防御を素通し（Confirm）して被弾
    runner.step(ActionType.ACTION_CONFIRM)

    # 死亡し、ゲームが終了してP0の敗北となっていること
    assert runner.state.get_hp(0) == 0
    assert runner.state.is_done is True
    assert runner.state.p0_reward == -1.0
    assert runner.state.p1_reward == 1.0


def test_kill_opp_bow_counter_kills_player_draw():
    """
    シナリオA: 相手撃破 → 相手の昇天弓起動 → 自分が被弾により死亡して引き分けになる検証。
    - P0がP1を撃破する（P1のHP = 0）。
    - P1の昇天弓が起動し、P0（HP 15、お守りなし）が30の光ダメージを被弾してHP 0になる。
    - 双方が死亡した状態になり、ゲームが終了（is_done=True）し、引き分け（p0_reward = p1_reward = 0.0）となることを検証。
    """
    runner = SimulationRunner()
    runner.state.seed_rng(0)  # 昇天弓が確実に命中するシード

    punch_id = find_card_by_name("パンチ")
    bow_id = find_card_by_name("昇天弓")
    shield_id = find_card_by_name("革の服")

    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0

    runner.state.set_hp(0, 15)  # 自分のHPは15 (昇天弓の威力30で即死)
    runner.state.set_hp(1, 3)  # 相手のHPは3

    runner.state.set_true_hand(0, 0, punch_id)
    runner.state.set_true_hand(1, 0, bow_id)
    runner.state.set_true_hand(1, 1, shield_id)

    # 1. P0がP1を攻撃
    runner.perform_attack([0])

    # P1の防御フェイズ（Confirmで被弾して死亡させる）
    assert runner.state.current_phase == GamePhase.PHASE_DEFENSE
    assert runner.state.current_actor_id == 1
    runner.step(ActionType.ACTION_CONFIRM)

    # 2. P1死亡に伴い、昇天弓反撃フェイズ（PHASE_DEFENSE, アクターP0）へ移行
    assert runner.state.current_phase == GamePhase.PHASE_DEFENSE
    assert runner.state.current_actor_id == 0

    # 3. P0が反撃を被弾（Confirm）
    runner.step(ActionType.ACTION_CONFIRM)

    # P0も死亡し、ゲームが終了して引き分け（報酬 0.0）になっていること
    assert runner.state.get_hp(0) == 0
    assert runner.state.get_hp(1) == 0
    assert runner.state.is_done is True
    assert runner.state.p0_reward == 0.0
    assert runner.state.p1_reward == 0.0


def test_kill_opp_bow_counter_hp1_sickness_death_draw():
    """
    シナリオB: 相手撃破 → 昇天弓起動 → 自分がHP 1で耐えるがその後の風邪ダメージで死亡し引き分けになる検証。
    - P0（風邪、お守りなし）がP1を撃破する。
    - P1の昇天弓が起動し、P0（HP 31）が30の光ダメージを被弾してHP 1になる。
    - その後、P0の風邪（Cold）による1ダメージが適用され、P0が死亡（HP = 0）する。
    - お守りがないためそのまま双方が死亡した状態になり、ゲーム終了（is_done=True）、引き分け（報酬 0.0）となることを検証。
    """
    runner = SimulationRunner()
    runner.state.seed_rng(0)  # 昇天弓が確実に命中するシード

    punch_id = find_card_by_name("パンチ")
    bow_id = find_card_by_name("昇天弓")
    shield_id = find_card_by_name("革の服")

    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0

    runner.state.set_hp(0, 31)  # 自分のHPは31
    runner.state.set_hp(1, 3)  # 相手のHPは3
    runner.state.set_sickness(0, SicknessType.SICKNESS_COLD)  # 自分は風邪

    runner.state.set_true_hand(0, 0, punch_id)
    runner.state.set_true_hand(1, 0, bow_id)
    runner.state.set_true_hand(1, 1, shield_id)

    # 1. P0がP1を攻撃
    runner.perform_attack([0])

    # P1の防御フェイズ（Confirmで被弾して死亡させる）
    assert runner.state.current_phase == GamePhase.PHASE_DEFENSE
    assert runner.state.current_actor_id == 1
    runner.step(ActionType.ACTION_CONFIRM)

    # 2. P1死亡に伴い、昇天弓反撃フェイズ（PHASE_DEFENSE, アクターP0）へ移行
    assert runner.state.current_phase == GamePhase.PHASE_DEFENSE
    assert runner.state.current_actor_id == 0

    # 3. P0が反撃を被弾（Confirm）
    runner.step(ActionType.ACTION_CONFIRM)

    # 被弾でHP 1になり、その後の風邪で死亡。
    # 双方が死亡しているため、ゲーム終了（is_done=True）し、引き分け（報酬 0.0）になっていること。
    assert runner.state.get_hp(0) == 0
    assert runner.state.get_hp(1) == 0
    assert runner.state.is_done is True
    assert runner.state.p0_reward == 0.0
    assert runner.state.p1_reward == 0.0


def test_heaven_wind_mutual_seizure_draw():
    """
    検証内容: お互い天国病の状態で、＜天国風＞による発作撃破 → 昇天弓反撃を耐える → 自分の天国病発作で死亡して引き分け。
    - P0 (HP 31、天国病、お守りなし) と P1 (HP 40、天国病) がともに天国病。
    - P0が奇跡「＜天国風＞」をP1に使用。P1はすでに天国病であるため、天国病の重ねがけにより発作が発生し即死（HP = 0）する。
    - P1の死亡に伴い、P1の昇天弓が起動。P0が被弾して31 -> 1 HPになる。
    - P0のターン終了解決において、P0も天国病が悪化（発作）して死亡（HP = 0）する。
    - 双方が死亡したため、引き分け（報酬 0.0）で終了することを確認。
    """
    # 昇天弓が命中し、かつP0の天国病が悪化死するシードを探索
    draw_seed = None
    wind_id = find_card_by_name("＜天国風＞")
    bow_id = find_card_by_name("昇天弓")
    shield_id = find_card_by_name("革の服")

    for seed in range(1000):
        test_run = SimulationRunner()
        test_run.state.seed_rng(seed)
        test_run.state.current_phase = GamePhase.PHASE_MAIN
        test_run.state.current_actor_id = 0
        test_run.state.set_mp(0, 20)
        test_run.state.set_hp(0, 31)
        test_run.state.set_hp(1, 40)
        test_run.state.set_sickness(0, SicknessType.SICKNESS_HEAVEN)
        test_run.state.set_sickness(1, SicknessType.SICKNESS_HEAVEN)

        test_run.state.set_true_hand(0, 0, wind_id)
        test_run.state.set_true_hand(1, 0, bow_id)
        test_run.state.set_true_hand(1, 1, shield_id)

        # 1. P0が＜天国風＞をP1に使用
        test_run.perform_attack([0])

        # P1の防御フェイズ（Confirmで被弾させて発作即死させる）
        if test_run.state.current_phase != GamePhase.PHASE_MIRACLE_DEFENSE:
            continue
        test_run.step(ActionType.ACTION_CONFIRM)

        # P1は天国病の重ねがけで死亡していること
        if test_run.state.get_hp(1) != 0:
            continue

        # 2. P1死亡に伴い、昇天弓反撃フェイズ（PHASE_DEFENSE, アクターP0）へ移行
        if test_run.state.current_phase != GamePhase.PHASE_DEFENSE:
            continue

        # 3. P0が反撃を被弾（Confirm）
        test_run.step(ActionType.ACTION_CONFIRM)

        # 双方が死亡して引き分け終了となったシードを採用
        if test_run.state.is_done and test_run.state.get_hp(0) == 0 and test_run.state.get_hp(1) == 0:
            draw_seed = seed
            break

    assert draw_seed is not None, "引き分け条件を満たすシードが見つかりませんでした"

    # 確定したシードでアサーションを実行
    runner = SimulationRunner()
    runner.state.seed_rng(draw_seed)
    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_mp(0, 20)

    runner.state.set_hp(0, 31)  # 自分のHPは31
    runner.state.set_hp(1, 40)  # 相手のHPは40
    runner.state.set_sickness(0, SicknessType.SICKNESS_HEAVEN)  # 自分も天国病
    runner.state.set_sickness(1, SicknessType.SICKNESS_HEAVEN)  # 相手も天国病

    runner.state.set_true_hand(0, 0, wind_id)
    runner.state.set_true_hand(1, 0, bow_id)
    runner.state.set_true_hand(1, 1, shield_id)

    # 1. P0が＜天国風＞をP1に使用
    runner.perform_attack([0])

    # P1の防御フェイズ（Confirmで被弾させて発作即死させる）
    assert runner.state.current_phase == GamePhase.PHASE_MIRACLE_DEFENSE
    assert runner.state.current_actor_id == 1
    runner.step(ActionType.ACTION_CONFIRM)

    # P1は天国病の重ねがけで死亡していること
    assert runner.state.get_hp(1) == 0

    # 2. P1死亡に伴い、昇天弓反撃フェイズ（PHASE_DEFENSE, アクターP0）へ移行
    assert runner.state.current_phase == GamePhase.PHASE_DEFENSE
    assert runner.state.current_actor_id == 0

    # 3. P0が反撃を被弾（Confirm）して 31 -> 1 HPになる
    runner.step(ActionType.ACTION_CONFIRM)

    # P0は昇天弓でHP 1になった後、ターン終了の悪化判定で発作を起こしHP 0（死亡）となる。
    # 双方が死亡しているため、ゲーム終了（is_done=True）し、引き分け（報酬 0.0）になっていること。
    assert runner.state.get_hp(0) == 0
    assert runner.state.get_hp(1) == 0
    assert runner.state.is_done is True
    assert runner.state.p0_reward == 0.0
    assert runner.state.p1_reward == 0.0


def test_heaven_wind_on_self_revive_heals():
    """
    検証内容: 自分が天国病のときに＜天国風＞を自分に撃って発作で死に、お守りで復活した場合、
    ターン終了時の天国病のHP+5は適用されて最終的にHP 15になること。
    - P0 (HP 40、天国病、太陽のお守り所持) が自分自身を対象に「＜天国風＞」を使用。
    - 重ねがけによりメインフェイズ中に発作で即死し、お守りで復活してHP 10になる。
    - その後ターン終了時、発作はこのターン終了時には起きていないため、通常の天国病の+5回復が適用されて最終HPが15になる。
    """
    runner = SimulationRunner()
    runner.state.seed_rng(0)  # ターン終了時に悪化（5%）しないシード

    wind_id = find_card_by_name("＜天国風＞")
    amulet_id = find_card_by_name("太陽のお守り")
    shield_id = find_card_by_name("革の服")

    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_mp(0, 20)

    runner.state.set_hp(0, 40)
    runner.state.set_sickness(0, SicknessType.SICKNESS_HEAVEN)

    runner.state.set_true_hand(0, 0, wind_id)
    runner.state.set_true_hand(0, 1, amulet_id)
    runner.state.set_true_hand(0, 2, shield_id)

    # 1. P0が自分に＜天国風＞を使用
    runner.perform_attack([0], to_self=True)

    # 自分への状態異常奇跡はメインフェイズ中に即時解決され、発作死亡→お守り自動復活がワンステップで行われる。
    # 復活直後のHP=10から、このターン終了時処理（PHASE_END）も同ステップ内で自動解決される。
    # メインフェイズでの発作だったため、ターン終了時の悪化は起きておらず、天国病の回復(+5)が適用されて最終HPが15になる。
    assert runner.state.get_hp(0) == 15
    assert runner.state.get_sickness(0) == SicknessType.SICKNESS_HEAVEN
    assert runner.state.is_done is False

    # ターンがすでに移行して相手（P1）の手番メインフェイズになっていること
    assert runner.state.current_actor_id == 1
    assert runner.state.current_phase == GamePhase.PHASE_MAIN


def test_simultaneous_death_ascension_bow_no_trigger_draw():
    """
    検証内容: 両者が同時に死亡し、どちらもお守りを持っていない場合、一方（または両方）が昇天弓を所持していても
    反撃フェイズに進まずに即時引き分け（Draw）となること。
    """
    runner = SimulationRunner()
    runner.state.seed_rng(0)

    bow_id = find_card_by_name("昇天弓")
    shield_id = find_card_by_name("革の服")

    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0

    # 両者のHPを0（同時死亡状態）に設定
    runner.state.set_hp(0, 0)
    runner.state.set_hp(1, 0)

    # 手札をすべてクリアしてから、必要なカードのみを設定（太陽のお守りがない状態を作る）
    for i in range(9):
        runner.state.set_true_hand(0, i, godfield_core.CARD_EMPTY)
        runner.state.set_true_hand(1, i, godfield_core.CARD_EMPTY)

    # P0は手札0に革の服（捨てる用）、手札1に昇天弓を所持。P1は手札0に革の服を所持。
    runner.state.set_true_hand(0, 0, shield_id)
    runner.state.set_true_hand(0, 1, bow_id)
    runner.state.set_true_hand(1, 0, shield_id)

    # 「捨てる」フェイズを経由してターンを終了させ、PHASE_END を起動
    runner.step(ActionType.ACTION_DISCARD)
    runner.perform_defense([0])

    # 即座に引き分け終了し、昇天弓による反撃フェイズ（PHASE_DEFENSE）に遷移しないこと
    assert runner.state.is_done is True
    assert runner.state.current_phase == GamePhase.PHASE_END
    assert runner.state.p0_reward == 0.0
    assert runner.state.p1_reward == 0.0


def test_venus_drain_kills_active_bow_counter_resumes_state5():
    """
    検証内容: 金星神（Venus）の罰金により手番プレイヤーが死亡して昇天弓反撃が発生した際、
    ゲームが正常に終了することを確認。
    """
    # 金星神の行動を引くシードを探索
    act_seed = None
    shield_id = find_card_by_name("革の服")
    bow_id = find_card_by_name("昇天弓")

    for seed in range(500):
        test_run = SimulationRunner()
        test_run.state.seed_rng(seed)
        test_run.state.current_phase = GamePhase.PHASE_MAIN
        test_run.state.current_actor_id = 0
        test_run.state.set_hp(0, 2)
        test_run.state.set_hp(1, 40)
        # お金 0 にすることで、没収3が直接 HP にいき死亡するようにする
        test_run.state.set_money(0, 0)
        test_run.state.set_guardian(1, 8)  # 相手(P1)に金星神を設定
        test_run.state.set_true_hand(0, 0, shield_id)
        test_run.state.set_true_hand(0, 1, bow_id)

        test_run.step(ActionType.ACTION_DISCARD)
        test_run.perform_defense([0])

        # 罰金は雑貨反射選択フェイズ（PHASE_SUNDRY_SELECT_MIRROR, アクターP0）へ遷移する
        if test_run.state.current_phase == GamePhase.PHASE_SUNDRY_SELECT_MIRROR and test_run.state.current_actor_id == 0 and test_run.state.pending_attack_source_id == find_card_by_name("罰金"):
            act_seed = seed
            break

    assert act_seed is not None, "金星神の罰金攻撃シードが見つかりませんでした"

    runner = SimulationRunner()
    runner.state.seed_rng(act_seed)
    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_hp(0, 2)
    runner.state.set_hp(1, 40)
    runner.state.set_money(0, 0)
    runner.state.set_guardian(1, 8)
    runner.state.set_true_hand(0, 0, shield_id)
    runner.state.set_true_hand(0, 1, bow_id)

    # 1. ターン終了
    runner.step(ActionType.ACTION_DISCARD)
    runner.perform_defense([0])

    # 金星神の罰金による雑貨反射選択フェイズ(P0)になっていること
    assert runner.state.current_phase == GamePhase.PHASE_SUNDRY_SELECT_MIRROR
    assert runner.state.current_actor_id == 0

    # 2. P0が被弾する(CONFIRM) -> 没収3が直接HPにきて死亡 -> 昇天弓が起動
    runner.step(ActionType.ACTION_CONFIRM)

    # 昇天弓が起動してP1の防御フェイズへ遷移していること
    assert runner.state.current_phase == GamePhase.PHASE_DEFENSE
    assert runner.state.current_actor_id == 1
    assert runner.state.get_hp(0) == 0

    # 3. P1が反撃を防御せずに素通し（Confirm）
    runner.step(ActionType.ACTION_CONFIRM)

    # P0はすでに死亡しており、P1は生き残っている。
    # ゲームが終了し、P1の勝利となっていること。
    assert runner.state.is_done is True
    assert runner.state.p0_reward == -1.0
    assert runner.state.p1_reward == 1.0


def test_ascension_bow_multiple_first_miss_second_hit():
    """
    検証内容: 複数枚の昇天弓を持っている場合、1発目がミス（25%の確率）しても、
    2発目が自動的に処理される（命中すれば相手の防御フェイズに移行する）こと。
    """
    bow_id = find_card_by_name("昇天弓")
    shield_id = find_card_by_name("革の服")

    # 1発目がミス（roll >= 75）、2発目がヒット（roll < 75）となるシードを探索
    target_seed = None
    for seed in range(1000):
        runner = SimulationRunner()
        runner.state.seed_rng(seed)
        runner.state.current_phase = GamePhase.PHASE_MAIN
        runner.state.current_actor_id = 0
        runner.state.set_hp(0, 0)
        runner.state.set_hp(1, 40)
        runner.state.set_true_hand(0, 0, bow_id)
        runner.state.set_true_hand(0, 1, bow_id)
        runner.state.set_true_hand(0, 2, shield_id)

        runner.step(ActionType.ACTION_DISCARD)
        runner.perform_defense([2])

        if runner.state.current_phase == GamePhase.PHASE_DEFENSE:
            if runner.state.get_pending_ascension_bows(0) == 0:
                target_seed = seed
                break

    assert target_seed is not None, "1発目ミス・2発目命中するシードが見つかりませんでした"

    runner = SimulationRunner()
    runner.state.seed_rng(target_seed)
    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_hp(0, 0)
    runner.state.set_hp(1, 40)
    runner.state.set_true_hand(0, 0, bow_id)
    runner.state.set_true_hand(0, 1, bow_id)
    runner.state.set_true_hand(0, 2, shield_id)

    runner.step(ActionType.ACTION_DISCARD)
    runner.perform_defense([2])

    # 2発目の処理により、相手(P1)の防御フェイズへ移行していること
    assert runner.state.current_phase == GamePhase.PHASE_DEFENSE
    assert runner.state.current_actor_id == 1
    assert runner.state.attacker_id == 0
    assert runner.state.defender_id == 1
    assert runner.state.pending_attack_power == 30
    assert runner.state.pending_attack_element == godfield_core.ELEM_LIGHT
    assert runner.state.get_pending_ascension_bows(0) == 0


def test_colored_leaves_reflection():
    """
    検証内容: 木星神の「紅葉」(夢付与、攻撃力0)が反射可能であることの検証。
    - 相手(P1)の木星神が「紅葉」を使い、P0がスーパーミラーで反射。
    - 反射された結果、P1自身が夢状態になり、P0は無事であることを確認。
    """
    super_mirror_id = find_card_by_name("スーパーミラー")
    shield_id = find_card_by_name("革の服")

    act_seed = None
    for seed in range(500):
        test_run = SimulationRunner()
        test_run.state.seed_rng(seed)
        test_run.state.current_phase = GamePhase.PHASE_MAIN
        test_run.state.current_actor_id = 0
        test_run.state.set_hp(0, 40)
        test_run.state.set_hp(1, 40)
        test_run.state.set_mp(0, 40)
        test_run.state.set_mp(1, 40)
        test_run.state.set_guardian(1, 3)  # 木星神(3)
        test_run.state.set_true_hand(0, 0, super_mirror_id)
        test_run.state.set_true_hand(0, 1, shield_id)

        # メインフェイズで手札1を捨てる
        test_run.step(ActionType.ACTION_DISCARD)
        test_run.perform_defense([1])

        # 紅葉(COLORED_LEAVES)の雑貨反射フェイズに移行したシードを探す
        if (
            test_run.state.current_phase == GamePhase.PHASE_SUNDRY_SELECT_MIRROR
            and test_run.state.pending_attack_source_id == find_card_by_name("gurdians/colored-leaves")
        ):
            act_seed = seed
            break

    assert act_seed is not None, "木星神の紅葉シードが見つかりませんでした"

    runner = SimulationRunner()
    runner.state.seed_rng(act_seed)
    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_hp(0, 40)
    runner.state.set_hp(1, 40)
    runner.state.set_mp(0, 40)
    runner.state.set_mp(1, 40)
    runner.state.set_guardian(1, 3)
    runner.state.set_true_hand(0, 0, super_mirror_id)
    runner.state.set_true_hand(0, 1, shield_id)

    # 1. ターン終了 Confirm (手札1を捨てる)
    runner.step(ActionType.ACTION_DISCARD)
    runner.perform_defense([1])

    # 雑貨反射フェイズ(P0)へ
    assert runner.state.current_phase == GamePhase.PHASE_SUNDRY_SELECT_MIRROR
    assert runner.state.current_actor_id == 0

    # 2. スーパーミラーを選択して反射（即座に相手番へ移行）
    runner.step(ActionType.ACTION_SELECT_HAND_0)

    # 反射されて相手(P1)の雑貨反射フェイズになること
    assert runner.state.current_phase == GamePhase.PHASE_SUNDRY_SELECT_MIRROR
    assert runner.state.current_actor_id == 1

    # 3. 相手(P1)が防御せずCONFIRM (被弾)
    runner.step(ActionType.ACTION_CONFIRM)

    # 元の攻撃者(P1)が夢状態になり、P0は正常であること
    assert runner.state.get_curses(1, godfield_core.CurseType.CURSE_DREAM) is True
    assert runner.state.get_curses(0, godfield_core.CurseType.CURSE_DREAM) is False


def test_halo_reflection():
    """
    検証内容: 天王神の「後光」(閃光付与、攻撃力0)が反射可能であり、雑貨扱いになることの検証。
    - 相手(P1)の天王神が「後光」を使い、P0がスーパーミラーで反射。
    - 反射された結果、P1自身が閃光状態になり、P0は無事であることを確認。
    """
    super_mirror_id = find_card_by_name("スーパーミラー")
    shield_id = find_card_by_name("革の服")

    act_seed = None
    for seed in range(500):
        test_run = SimulationRunner()
        test_run.state.seed_rng(seed)
        test_run.state.current_phase = GamePhase.PHASE_MAIN
        test_run.state.current_actor_id = 0
        test_run.state.set_hp(0, 40)
        test_run.state.set_hp(1, 40)
        test_run.state.set_mp(0, 40)
        test_run.state.set_mp(1, 40)
        test_run.state.set_guardian(1, 5)  # 天王神(5)
        test_run.state.set_true_hand(0, 0, super_mirror_id)
        test_run.state.set_true_hand(0, 1, shield_id)

        # メインフェイズで手札1を捨てる
        test_run.step(ActionType.ACTION_DISCARD)
        test_run.perform_defense([1])

        # 後光(HALO)の雑貨反射フェイズに移行したシードを探す
        if (
            test_run.state.current_phase == GamePhase.PHASE_SUNDRY_SELECT_MIRROR
            and test_run.state.pending_attack_source_id == find_card_by_name("gurdians/halo")
        ):
            act_seed = seed
            break

    assert act_seed is not None, "天王神の後光シードが見つかりませんでした"

    runner = SimulationRunner()
    runner.state.seed_rng(act_seed)
    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_hp(0, 40)
    runner.state.set_hp(1, 40)
    runner.state.set_mp(0, 40)
    runner.state.set_mp(1, 40)
    runner.state.set_guardian(1, 5)
    runner.state.set_true_hand(0, 0, super_mirror_id)
    runner.state.set_true_hand(0, 1, shield_id)

    # 1. ターン終了 Confirm
    runner.step(ActionType.ACTION_DISCARD)
    runner.perform_defense([1])

    # 雑貨反射フェイズ(P0)へ
    assert runner.state.current_phase == GamePhase.PHASE_SUNDRY_SELECT_MIRROR
    assert runner.state.current_actor_id == 0

    # 2. スーパーミラーを選択して反射
    runner.step(ActionType.ACTION_SELECT_HAND_0)

    # 反射されて相手(P1)の雑貨反射フェイズになること
    assert runner.state.current_phase == GamePhase.PHASE_SUNDRY_SELECT_MIRROR
    assert runner.state.current_actor_id == 1

    # 3. 相手(P1)が防御せずCONFIRM (被弾)
    runner.step(ActionType.ACTION_CONFIRM)

    # 元の攻撃者(P1)が閃光状態になり、P0は正常であること
    assert runner.state.get_curses(1, godfield_core.CurseType.CURSE_FLASH) is True
    assert runner.state.get_curses(0, godfield_core.CurseType.CURSE_FLASH) is False


def test_ominous_premonition_reflection():
    """
    検証内容: 冥王神の「不吉な予感」(暗雲付与、攻撃力0)が反射可能であり、雑貨扱いになることの検証。
    """
    super_mirror_id = find_card_by_name("スーパーミラー")
    shield_id = find_card_by_name("革の服")

    act_seed = None
    for seed in range(500):
        test_run = SimulationRunner()
        test_run.state.seed_rng(seed)
        test_run.state.current_phase = GamePhase.PHASE_MAIN
        test_run.state.current_actor_id = 0
        test_run.state.set_hp(0, 40)
        test_run.state.set_hp(1, 40)
        test_run.state.set_mp(0, 40)
        test_run.state.set_mp(1, 40)
        test_run.state.set_guardian(1, 6)  # 冥王神(6)
        test_run.state.set_true_hand(0, 0, super_mirror_id)
        test_run.state.set_true_hand(0, 1, shield_id)

        # メインフェイズで手札1を捨てる
        test_run.step(ActionType.ACTION_DISCARD)
        test_run.perform_defense([1])

        # 不吉な予感(OMINOUS_PREMONITION)の雑貨反射フェイズに移行したシードを探す
        if (
            test_run.state.current_phase == GamePhase.PHASE_SUNDRY_SELECT_MIRROR
            and test_run.state.pending_attack_source_id == find_card_by_name("gurdians/ominous-premonition")
        ):
            act_seed = seed
            break

    assert act_seed is not None, "冥王神の不吉な予感シードが見つかりませんでした"

    runner = SimulationRunner()
    runner.state.seed_rng(act_seed)
    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_hp(0, 40)
    runner.state.set_hp(1, 40)
    runner.state.set_mp(0, 40)
    runner.state.set_mp(1, 40)
    runner.state.set_guardian(1, 6)
    runner.state.set_true_hand(0, 0, super_mirror_id)
    runner.state.set_true_hand(0, 1, shield_id)

    # 1. ターン終了 Confirm
    runner.step(ActionType.ACTION_DISCARD)
    runner.perform_defense([1])

    # 雑貨反射フェイズ(P0)へ
    assert runner.state.current_phase == GamePhase.PHASE_SUNDRY_SELECT_MIRROR
    assert runner.state.current_actor_id == 0

    # 2. スーパーミラーを選択して反射
    runner.step(ActionType.ACTION_SELECT_HAND_0)

    # 反射されて相手(P1)の雑貨反射フェイズになること
    assert runner.state.current_phase == GamePhase.PHASE_SUNDRY_SELECT_MIRROR
    assert runner.state.current_actor_id == 1

    # 3. 相手(P1)が防御せずCONFIRM (被弾)
    runner.step(ActionType.ACTION_CONFIRM)

    # 元の攻撃者(P1)が暗雲状態になり、P0は正常であること
    assert runner.state.get_curses(1, godfield_core.CurseType.CURSE_DARK_CLOUD) is True
    assert runner.state.get_curses(0, godfield_core.CurseType.CURSE_DARK_CLOUD) is False


def test_little_something_targets_self():
    """
    検証内容: 金星神の「つまらないもの」(自分お金+8)および「高級アクセサリー」(自分お金+20)の検証。
    - 相手(P1)の金星神がこれらを実行した際、P1自身にお金が加算されることを確認。
    """
    shield_id = find_card_by_name("革の服")

    # つまらないもの または 高級アクセサリーが起動するシードを探す
    target_seed = None
    for seed in range(500):
        test_run = SimulationRunner()
        test_run.state.seed_rng(seed)
        test_run.state.current_phase = GamePhase.PHASE_MAIN
        test_run.state.current_actor_id = 0
        test_run.state.set_hp(0, 40)
        test_run.state.set_hp(1, 40)
        test_run.state.set_money(0, 10)
        test_run.state.set_money(1, 10)
        test_run.state.set_guardian(1, 8)  # 金星神(8)
        test_run.state.set_true_hand(0, 0, shield_id)

        test_run.step(ActionType.ACTION_DISCARD)
        test_run.perform_defense([0])

        # 10 + 8 = 18 または 10 + 20 = 30 になっているシード
        if test_run.state.get_money(1) in (18, 30):
            target_seed = seed
            break

    assert target_seed is not None, "金星神の自己バフシードが見つかりませんでした"

    runner = SimulationRunner()
    runner.state.seed_rng(target_seed)
    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_hp(0, 40)
    runner.state.set_hp(1, 40)
    runner.state.set_money(0, 10)
    runner.state.set_money(1, 10)
    runner.state.set_guardian(1, 8)
    runner.state.set_true_hand(0, 0, shield_id)

    runner.step(ActionType.ACTION_DISCARD)
    runner.perform_defense([0])

    # P1のお金が増えており(18 または 30)、P0は変化なし(10)であることを確認
    assert runner.state.get_money(1) in (18, 30)
    assert runner.state.get_money(0) == 10

def test_sickness_turn_end_after_combat():
    """
    検証内容: 戦闘解決後にターン終了した際、病気ダメージが「ターンプレイヤー（攻撃側）」に正しく適用されること。
    - P0が風邪（COLD）状態。
    - P0がP1へ武器攻撃し、P1が防御を完了する。
    - 戦闘終了（PHASE_END）時に、風邪の1ダメージがP0（攻撃側）に適用されることを確認。
    - P1（防御側）には適用されないことを確認。
    """
    runner = SimulationRunner()
    weapon_id = find_card_by_name("weapons/bronze-club")
    shield_id = find_card_by_name("armor/leather-cap")

    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_hp(0, 40)
    runner.state.set_hp(1, 40)
    runner.state.set_sickness(0, SicknessType.SICKNESS_COLD)  # P0が風邪
    runner.state.set_sickness(1, SicknessType.SICKNESS_NONE)

    runner.set_hand(0, [weapon_id])
    runner.set_hand(1, [shield_id])

    # P0が攻撃
    runner.perform_attack([0])

    # P1の防御ターン
    assert runner.state.current_phase == GamePhase.PHASE_DEFENSE
    assert runner.state.current_actor_id == 1

    # P1が木の盾で防御
    runner.perform_defense([0])

    # ターン終了処理が完了し、P1のメインフェイズへ移行していること
    assert runner.state.current_phase == GamePhase.PHASE_MAIN
    assert runner.state.current_actor_id == 1

    # 病気ダメージがP0（ターンプレイヤー）に適用され、HPが39になっていること
    assert runner.state.get_hp(0) == 39
    assert runner.state.get_hp(1) == 40

# ==========================================
# Merged from: tests/core/test_discrepancy_fixes.py
# ==========================================


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


