import godfield_core
from godfield_core import ActionType, GamePhase

from .test_utils import SimulationRunner, find_card_by_name


def test_discard_logic():
    """
    検証内容: 捨てる (Discard) アクションの制御と実行。
    - メインフェイズで ACTION_DISCARD が有効。防御カードを直接選択することは不可。
    - PHASE_DISCARD に遷移後、盾（革の服）は捨てられる。
    - 武器（パンチ）や太陽のお守りは捨てられない。
    - 捨てたカードは CARD_EMPTY になり、使用済みフラグ is_used が立っていること。
    """
    runner = SimulationRunner()
    shield_id = find_card_by_name("革の服")
    weapon_id = find_card_by_name("パンチ")
    sun_amulet_id = find_card_by_name("太陽のお守り")

    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0

    # 0: 盾 (革の服)
    # 1: 武器 (パンチ)
    # 2: 太陽のお守り
    runner.state.set_true_hand(0, 0, shield_id)
    runner.state.set_true_hand(0, 1, weapon_id)
    runner.state.set_true_hand(0, 2, sun_amulet_id)

    # 1. メインフェイズでの破棄選択
    actions = godfield_core.get_legal_actions(runner.state)
    assert actions[ActionType.ACTION_DISCARD] is True          # 捨てるアクション自体は選択可能
    assert actions[ActionType.ACTION_SELECT_HAND_0] is False  # 盾を直接メインフェイズで選択することは不可
    assert actions[ActionType.ACTION_SELECT_HAND_1] is True   # 武器は直接メインフェイズで選択可能 (攻撃用)
    assert actions[ActionType.ACTION_SELECT_HAND_2] is False  # お守りは直接メインフェイズで選択不可

    # 破棄フェイズへ遷移
    runner.step(action=ActionType.ACTION_DISCARD)
    assert runner.state.current_phase == GamePhase.PHASE_DISCARD

    # 2. 破棄フェイズでの選択
    actions_discard = godfield_core.get_legal_actions(runner.state)
    assert actions_discard[ActionType.ACTION_SELECT_HAND_0] is True   # 盾は破棄対象として選択可能
    assert actions_discard[ActionType.ACTION_SELECT_HAND_1] is False  # 武器は破棄不可
    assert actions_discard[ActionType.ACTION_SELECT_HAND_2] is False  # お守りは破棄不可
    assert actions_discard[ActionType.ACTION_CONFIRM] is False        # まだ何も選択していないため確定不可

    # 盾を選択
    runner.step(action=ActionType.ACTION_SELECT_HAND_0)

    # 確定可能になる
    actions_staged = godfield_core.get_legal_actions(runner.state)
    assert actions_staged[ActionType.ACTION_CONFIRM] is True

    runner.step(action=ActionType.ACTION_CONFIRM)

    # 結果確認: 手札スロット0が空になり、かつ is_used が false（ドローによる補填を行わないため）
    assert runner.state.get_true_hand(0, 0) == godfield_core.CARD_EMPTY
    assert runner.state.get_is_used(0, 0) is False


def test_exchange_logic():
    """
    検証内容: 両替 (Exchange) の数値配分とHP死。
    - 両替開始時に HP + MP + Money の合計値が算出される。
    - PHASE_EXCHANGE_HP では合計値を越えない範囲の数値のみ選択可能。
    - 数値指定は ACTION_NUM_0 〜 ACTION_NUM_99 を使用。
    - HP=0 を指定し、MPを選択して両替を完了させると即座に死亡（done）。
    """
    runner = SimulationRunner()
    exchange_id = find_card_by_name("両替")

    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_hp(0, 40)
    runner.state.set_mp(0, 20)
    runner.state.set_money(0, 15)  # 合計 = 75
    runner.state.set_true_hand(0, 0, exchange_id)

    # 両替を使用
    runner.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner.step(action=ActionType.ACTION_TARGET_SELF)

    # Phase 6 新フェイズ: PHASE_EXCHANGE_HP へ遷移
    assert runner.state.current_phase == GamePhase.PHASE_EXCHANGE_HP

    # 合法手チェック: 75 以下の数値アクションが有効
    actions_hp = godfield_core.get_legal_actions(runner.state)
    assert actions_hp[ActionType.ACTION_NUM_30] is True
    assert actions_hp[ActionType.ACTION_NUM_75] is True
    assert actions_hp[ActionType.ACTION_NUM_76] is False  # 合計を超える値は不可

    # HPを 30 に指定
    runner.step(action=ActionType.ACTION_NUM_30)
    assert runner.state.current_phase == GamePhase.PHASE_EXCHANGE_MP

    # MPの選択可能な上限は合計(75) - HP(30) = 45
    actions_mp = godfield_core.get_legal_actions(runner.state)
    assert actions_mp[ActionType.ACTION_NUM_20] is True
    assert actions_mp[ActionType.ACTION_NUM_45] is True
    assert actions_mp[ActionType.ACTION_NUM_46] is False

    # MPを 20 に指定 (残金 75 - 30 - 20 = 25)
    runner.step(action=ActionType.ACTION_NUM_20)

    # 解決確認
    assert runner.state.get_hp(0) == 30
    assert runner.state.get_mp(0) == 20
    assert runner.state.get_money(0) == 25
    assert runner.state.current_phase == GamePhase.PHASE_MAIN  # ターンが終了して次のターンへ

    # --- 異常系: HP=0 指定で即死 ---
    runner2 = SimulationRunner()
    runner2.state.current_phase = GamePhase.PHASE_MAIN
    runner2.state.current_actor_id = 0
    runner2.state.set_hp(0, 40)
    runner2.state.set_mp(0, 20)
    runner2.state.set_money(0, 10)  # 合計 = 70
    runner2.state.set_true_hand(0, 0, exchange_id)

    runner2.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner2.step(action=ActionType.ACTION_TARGET_SELF)
    runner2.step(action=ActionType.ACTION_NUM_0)   # HPを 0 に指定 (enters PHASE_EXCHANGE_MP)
    runner2.step(action=ActionType.ACTION_NUM_20)  # MPを 20 に指定して確定

    # 即死判定
    assert runner2.state.is_done is True
    assert runner2.state.p0_reward == -1.0


def test_sell_logic():
    """
    検証内容: 売る (Sell) アクション。
    - 自分に売る: お金不足分が MP -> HP から引かれ、カードは手札に戻る。
    - 相手に売る: 相手の Money -> MP -> HP から引かれ、カードは相手の手札に移動し、自分はお金を受け取る。
    """
    # 1. 自分に売る
    runner = SimulationRunner()
    sell_id = find_card_by_name("売る")
    pot_id = find_card_by_name("守護封印のつぼ")  # 価格: 10

    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_money(0, 5)   # お金が足りない (残り5)
    runner.state.set_mp(0, 8)      # MPで5支払う (残り3)
    runner.state.set_hp(0, 50)     # HPは減らない

    runner.state.set_true_hand(0, 0, sell_id)
    runner.state.set_true_hand(0, 1, pot_id)

    runner.step(action=ActionType.ACTION_SELECT_HAND_0)
    assert runner.state.current_phase == GamePhase.PHASE_SELL_SELECT

    runner.step(action=ActionType.ACTION_SELECT_HAND_1)  # つぼを売る
    assert runner.state.current_phase == GamePhase.PHASE_MAIN_TARGET_SELECT

    runner.step(action=ActionType.ACTION_TARGET_SELF)  # 自分を対象
    assert runner.state.current_phase == GamePhase.PHASE_MAIN

    # 自身への支払いの結果: money=10 (売り手として10回収), mp=3, hp=50
    assert runner.state.get_money(0) == 10
    assert runner.state.get_mp(0) == 3
    assert runner.state.get_hp(0) == 50
    # 売ったカードは自分に戻る
    assert runner.state.get_true_hand(0, 1) == pot_id

    # 2. 相手に売る
    runner2 = SimulationRunner()
    runner2.state.current_phase = GamePhase.PHASE_MAIN
    runner2.state.current_actor_id = 0
    runner2.state.set_money(0, 0)
    runner2.state.set_money(1, 4)   # 相手のお金 4 (つぼ10に対して6不足)
    runner2.state.set_mp(1, 10)     # 相手のMP 10 (残り6を支払って4になる)

    runner2.state.set_true_hand(0, 0, sell_id)
    runner2.state.set_true_hand(0, 1, pot_id)

    runner2.step(action=ActionType.ACTION_SELECT_HAND_0)
    assert runner2.state.current_phase == GamePhase.PHASE_SELL_SELECT

    runner2.step(action=ActionType.ACTION_SELECT_HAND_1)  # つぼを売る
    assert runner2.state.current_phase == GamePhase.PHASE_MAIN_TARGET_SELECT

    runner2.step(action=ActionType.ACTION_TARGET_OPP)  # 相手を対象
    assert runner2.state.current_phase == GamePhase.PHASE_SELL_SELECT_MIRROR

    runner2.step(action=ActionType.ACTION_CONFIRM)  # Opponent accepts the sell

    # 相手の支払い結果
    assert runner2.state.get_money(1) == 0
    assert runner2.state.get_mp(1) == 4
    # 自分はお金を10受け取る
    assert runner2.state.get_money(0) == 10
    # カードは相手の手札のいずれかの空スロットに移動
    found = False
    for j in range(18):
        if runner2.state.get_true_hand(1, j) == pot_id:
            found = True
            assert runner2.state.get_is_known_to_opp(1, j) is True # 売られた側のカードは公開（既知）になる
            break
    assert found is True

    # 3. 自分に売って死亡（5/0/0 から価格 10 を売りつけて 0/0/10 になり死亡）
    runner3 = SimulationRunner()
    runner3.state.current_phase = GamePhase.PHASE_MAIN
    runner3.state.current_actor_id = 0
    runner3.state.set_hp(0, 5)
    runner3.state.set_mp(0, 0)
    runner3.state.set_money(0, 0)

    runner3.state.set_true_hand(0, 0, sell_id)
    runner3.state.set_true_hand(0, 1, pot_id)  # 価格: 10

    runner3.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner3.step(action=ActionType.ACTION_SELECT_HAND_1)
    runner3.step(action=ActionType.ACTION_TARGET_SELF)

    assert runner3.state.is_done is True
    assert runner3.state.get_hp(0) == 0
    assert runner3.state.get_mp(0) == 0
    assert runner3.state.get_money(0) == 10
    assert runner3.state.p0_reward == -1.0

    # 4. 相手に売って相手が死亡（相手が 10/5/5 で価格 30 の「神の剣」を売られ、相手は 0/0/0 になり、自分は +30money）
    runner4 = SimulationRunner()
    god_sword_id = find_card_by_name("神の剣")  # 価格: 30

    runner4.state.current_phase = GamePhase.PHASE_MAIN
    runner4.state.current_actor_id = 0
    runner4.state.set_money(0, 0)
    runner4.state.set_hp(1, 10)
    runner4.state.set_mp(1, 5)
    runner4.state.set_money(1, 5)  # 相手の支払能力合計: 5 + 5 + 10 = 20

    runner4.state.set_true_hand(0, 0, sell_id)
    runner4.state.set_true_hand(0, 1, god_sword_id)

    runner4.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner4.step(action=ActionType.ACTION_SELECT_HAND_1)
    runner4.step(action=ActionType.ACTION_TARGET_OPP)
    runner4.step(action=ActionType.ACTION_CONFIRM)

    # 5. 売るに対して相手がスーパーミラーで跳ね返す
    # 自分が相手に「つぼ (価格 10)」を売ろうとしたが、相手がスーパーミラーで跳ね返し、自分がつぼを買わされる
    runner5 = SimulationRunner()
    super_mirror_id = find_card_by_name("スーパーミラー")
    
    runner5.state.current_phase = GamePhase.PHASE_MAIN
    runner5.state.current_actor_id = 0
    runner5.state.set_money(0, 10)   # 自分の購入資金 (つぼ代10)
    runner5.state.set_money(1, 0)    # 相手のお金 0
    
    runner5.state.set_true_hand(0, 0, sell_id)
    runner5.state.set_true_hand(0, 1, pot_id)
    runner5.state.set_true_hand(1, 0, super_mirror_id)
    
    runner5.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner5.step(action=ActionType.ACTION_SELECT_HAND_1)
    runner5.step(action=ActionType.ACTION_TARGET_OPP)
    
    # 相手はスーパーミラーを使用する
    assert runner5.state.current_phase == GamePhase.PHASE_SELL_SELECT_MIRROR
    assert runner5.state.current_actor_id == 1
    runner5.step(action=ActionType.ACTION_SELECT_HAND_0) # スーパーミラーを使用
    
    # 反射された結果、フェイズはPHASE_SELL_SELECT_MIRRORのままで、手番が自分（アクター0）に移る
    assert runner5.state.current_phase == GamePhase.PHASE_SELL_SELECT_MIRROR
    assert runner5.state.current_actor_id == 0
    
    # 自分が受諾(Accept)する
    runner5.step(action=ActionType.ACTION_CONFIRM)
    
    # 自分の支払い結果: お金10つぼ購入で0になる
    assert runner5.state.get_money(0) == 0
    # 相手(売り手)はお金10を受け取る
    assert runner5.state.get_money(1) == 10
    # カードは自分の手札に戻る（元々0:0が売る、0:1がつぼだった。つぼは一度消去されて空スロットのどこかに入る）
    found = False
    for j in range(18):
        if runner5.state.get_true_hand(0, j) == pot_id:
            found = True
            assert runner5.state.get_is_known_to_opp(0, j) is True # 反射されて買い戻した側のカードは公開（既知）になる
            break
    assert found is True


def test_buy_logic():
    """
    検証内容: 買う (Buy) アクション。
    - 相手に買う: 相手の手札からランダムに1枚提示され、お金があれば購入可能。
    """
    runner = SimulationRunner()
    buy_id = find_card_by_name("買う")
    pot_id = find_card_by_name("守護封印のつぼ")  # 価格: 10

    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_money(0, 20)  # 購入可能額
    runner.state.set_money(1, 0)

    runner.state.set_true_hand(0, 0, buy_id)
    runner.state.set_true_hand(1, 0, pot_id)  # 相手の手札につぼ

    runner.step(action=ActionType.ACTION_SELECT_HAND_0)
    assert runner.state.current_phase == GamePhase.PHASE_MAIN_TARGET_SELECT
    runner.step(action=ActionType.ACTION_TARGET_OPP)  # 相手を対象

    assert runner.state.current_phase == GamePhase.PHASE_BUY_SELECT_MIRROR
    runner.step(action=ActionType.ACTION_CONFIRM)  # Opponent accepts the buy
    assert runner.state.current_phase == GamePhase.PHASE_BUY

    # 提示されたカードが既知フラグオンになる
    assert runner.state.get_is_known_to_opp(1, 0) is True

    # 購入を実行
    actions_buy = godfield_core.get_legal_actions(runner.state)
    assert actions_buy[ActionType.ACTION_DEAL_YES] is True
    assert actions_buy[ActionType.ACTION_DEAL_NO] is True

    runner.step(action=ActionType.ACTION_DEAL_YES)

    # 結果確認
    assert runner.state.get_money(0) == 10  # 20 - 10 = 10
    assert runner.state.get_money(1) == 10  # 相手にお金が入る
    # 相手のスロット0は空になり、自分につぼが移る
    assert runner.state.get_true_hand(1, 0) == godfield_core.CARD_EMPTY

    found = False
    for j in range(18):
        if runner.state.get_true_hand(0, j) == pot_id:
            found = True
            assert runner.state.get_is_known_to_opp(0, j) is True # 買い取った側のカードは公開（既知）になる
            break
    assert found is True

    # 2. 手札が満杯（18枚）の状態で買う
    runner2 = SimulationRunner()
    buy_id = find_card_by_name("買う")
    shield_id = find_card_by_name("革の服")
    pot_id = find_card_by_name("守護封印のつぼ")  # 価格: 10

    runner2.state.current_phase = GamePhase.PHASE_MAIN
    runner2.state.current_actor_id = 0
    runner2.state.set_money(0, 20)
    runner2.state.set_money(1, 0)

    # P0の手札をすべて埋める
    # スロット0: 買う
    # スロット1~17: 革の服
    runner2.state.set_true_hand(0, 0, buy_id)
    for i in range(1, 18):
        runner2.state.set_true_hand(0, i, shield_id)

    # 相手のスロット0につぼ
    runner2.state.set_true_hand(1, 0, pot_id)

    # 買うを使用
    runner2.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner2.step(action=ActionType.ACTION_TARGET_OPP)
    runner2.step(action=ActionType.ACTION_CONFIRM)
    runner2.step(action=ActionType.ACTION_DEAL_YES)

    # 解決後はターンが終了し、スロット0は新規ドローによって埋められているため、「買う」ではなくなっている
    # (ただし、スロット1~17のうちのいずれかが購入したカード「つぼ」に置き換わっており、購入カードが保存されていることを確認する)

    # スロット1~17のいずれか1つがつぼ（pot_id）に置き換わっていること
    pot_count = 0
    shield_count = 0
    for i in range(1, 18):
        card = runner2.state.get_true_hand(0, i)
        if card == pot_id:
            pot_count += 1
        elif card == shield_id:
            shield_count += 1

    assert pot_count == 1
    assert shield_count == 16

    # 3. 買うに対して相手がスーパーミラーで跳ね返す
    # P0がP1に対して「買う」を使用。P1はスーパーミラーで跳ね返し、P1がP0の手札から買う側に回る。
    runner3 = SimulationRunner()
    buy_id = find_card_by_name("買う")
    super_mirror_id = find_card_by_name("スーパーミラー")
    pot_id = find_card_by_name("守護封印のつぼ")
    
    runner3.state.current_phase = GamePhase.PHASE_MAIN
    runner3.state.current_actor_id = 0
    runner3.state.set_money(0, 0)
    runner3.state.set_money(1, 20)  # 反射者P1が20円持っているので購入可能
    
    runner3.state.set_true_hand(0, 0, buy_id)
    runner3.state.set_true_hand(0, 1, pot_id)  # P0の手札につぼ (P1が買う対象になる)
    runner3.state.set_true_hand(1, 0, super_mirror_id)
    
    runner3.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner3.step(action=ActionType.ACTION_TARGET_OPP)
    
    assert runner3.state.current_phase == GamePhase.PHASE_BUY_SELECT_MIRROR
    assert runner3.state.current_actor_id == 1
    
    # P1はスーパーミラーを使用する
    runner3.step(action=ActionType.ACTION_SELECT_HAND_0)
    
    # 反射された結果、フェイズはPHASE_BUY_SELECT_MIRRORのまま維持され、アクターがP0(相手)になる
    assert runner3.state.current_phase == GamePhase.PHASE_BUY_SELECT_MIRROR
    assert runner3.state.current_actor_id == 0
    
    # P0は受諾(ACTION_CONFIRM)する
    runner3.step(action=ActionType.ACTION_CONFIRM)
    
    # 受諾した結果、フェイズはPHASE_BUYになり、アクターがP1(買い手)になる
    assert runner3.state.current_phase == GamePhase.PHASE_BUY
    assert runner3.state.current_actor_id == 1
    
    # 売り手P0の手札から「つぼ」が提示される（staged_cardsにインデックス1が入る）
    revealed_idx = runner3.state.get_staged_card(0, 0)
    assert runner3.state.get_true_hand(0, revealed_idx) == pot_id
    
    # 購入を決断
    runner3.step(action=ActionType.ACTION_DEAL_YES)
    
    # 結果確認
    assert runner3.state.get_money(1) == 10  # 20 - 10 = 10
    assert runner3.state.get_money(0) == 10  # P0に10円入る
    # P0の手札からつぼが消え、P1の手札につぼが入る
    assert runner3.state.get_true_hand(0, revealed_idx) == godfield_core.CARD_EMPTY
    found = False
    for j in range(18):
        if runner3.state.get_true_hand(1, j) == pot_id:
            found = True
            assert runner3.state.get_is_known_to_opp(1, j) is True # 反射されて買い取った側のカードは公開（既知）になる
            break
    assert found is True

    # 4. 買うしかない状態でスーパーミラー反射され、買われそうになって受諾すると買うに失敗してそのままターン終了する
    runner4 = SimulationRunner()
    buy_id = find_card_by_name("買う")
    super_mirror_id = find_card_by_name("スーパーミラー")
    
    runner4.state.current_phase = GamePhase.PHASE_MAIN
    runner4.state.current_actor_id = 0
    runner4.state.set_money(0, 0)
    runner4.state.set_money(1, 20)
    
    runner4.state.set_true_hand(0, 0, buy_id)
    # スロット1~17は全て空にする
    for j in range(1, 18):
        runner4.state.set_true_hand(0, j, godfield_core.CARD_EMPTY)
        
    runner4.state.set_true_hand(1, 0, super_mirror_id)
    
    runner4.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner4.step(action=ActionType.ACTION_TARGET_OPP)
    
    # 相手はスーパーミラーを使用する
    runner4.step(action=ActionType.ACTION_SELECT_HAND_0)
    
    # P0は受諾する
    runner4.step(action=ActionType.ACTION_CONFIRM)
    
    # 手札に「買う」以外のカード（提示できるカード）が無いため、買う処理は失敗して自動的にターン終了（次のターンのPHASE_MAIN）になる
    # 注意: PHASE_ENDは自動進行するため、step() 呼出し後は次のプレイヤーの PHASE_MAIN になる
    # ここではP0の手番が終了し、P1のPHASE_MAINになる
    assert runner4.state.current_phase == GamePhase.PHASE_MAIN
    assert runner4.state.current_actor_id == 1
    
    # P0は「買う」カードを消費し、新しく山札から1枚ドローしているはず（スロット0〜17のうち、17枚が空で、1枚だけ何かがある状態）
    empty_card_count = 0
    for j in range(18):
        card = runner4.state.get_true_hand(0, j)
        if card == godfield_core.CARD_EMPTY:
            empty_card_count += 1
            
    assert empty_card_count == 17


def test_attack_observability():
    """
    検証内容: 複数枚攻撃時、攻撃確定後も防御解決されるまで攻撃者の staged_cards と is_known_to_opp が維持され、
    防御側から攻撃内容（どのカードをどの順番で使ったか）が完全に観測できること。
    """
    runner = SimulationRunner()
    wood_sword_id = find_card_by_name("木刀")
    blowgun_id = find_card_by_name("吹き矢")
    wood_shield_id = find_card_by_name("木の盾")

    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0

    # P0の手札: [木刀, 吹き矢, ...]
    runner.state.set_true_hand(0, 0, wood_sword_id)
    runner.state.set_true_hand(0, 1, blowgun_id)

    # P1の手札: [木の盾, ...]
    runner.state.set_true_hand(1, 0, wood_shield_id)

    # 1. P0が攻撃（木刀）を選択
    runner.step(action=ActionType.ACTION_SELECT_HAND_0)
    assert runner.state.get_is_known_to_opp(0, 0) is False  # 選択中（ステージング中）は非公開

    # 2. P0が攻撃追加（吹き矢）を選択
    assert runner.state.current_phase == GamePhase.PHASE_ATTACK_PLUS
    runner.step(action=ActionType.ACTION_SELECT_HAND_1)
    assert runner.state.get_is_known_to_opp(0, 1) is False  # 選択中（ステージング中）は非公開

    # 3. P0がターゲット（P1）を指定して攻撃を確定
    runner.step(action=ActionType.ACTION_TARGET_OPP)

    # 確定した時点で、相手（P1）に公開される
    assert runner.state.get_is_known_to_opp(0, 0) is True
    assert runner.state.get_is_known_to_opp(0, 1) is True

    # P1の防御フェイズ（PHASE_DEFENSE）に入る
    assert runner.state.current_phase == GamePhase.PHASE_DEFENSE
    assert runner.state.current_actor_id == 1

    # 【重要】防御中も、攻撃者（P0）の staged_cards がクリアされずに維持されていること
    assert runner.state.get_num_staged_cards(0) == 2
    assert runner.state.get_staged_card(0, 0) == 0  # 1枚目に木刀 (手札スロット0)
    assert runner.state.get_staged_card(0, 1) == 1  # 2枚目に吹き矢 (手札スロット1)

    # 4. P1が防御（木の盾）を選択して確定
    runner.step(action=ActionType.ACTION_SELECT_HAND_0)
    assert runner.state.get_is_known_to_opp(1, 0) is False  # 防具選択中も非公開
    runner.step(action=ActionType.ACTION_CONFIRM)

    # 防御解決後はターンが終了（PHASE_END -> 次のメイン）し、両者の staged_cards がクリアされる
    assert runner.state.get_num_staged_cards(0) == 0
    assert runner.state.get_num_staged_cards(1) == 0


def test_sundry_logic():
    """
    検証内容: 雑貨 (Sundry) アクションの解決およびミラー反射挙動。
    - 自分対象: ミラー確認をスキップし即座に効果適用。
    - 相手対象: ミラーがあれば反射（PHASE_SUNDRY_SELECT_MIRROR）へ移行。
    - スーパーミラーによる反射と再反射のフロー。
    """
    sundry_id = find_card_by_name("天国草")  # 雑貨。HP/MPなどを回復する効果
    super_mirror_id = find_card_by_name("スーパーミラー")

    # 1. 自分対象: ミラー確認なしで即座に解決
    runner_self = SimulationRunner()
    runner_self.state.current_phase = GamePhase.PHASE_MAIN
    runner_self.state.current_actor_id = 0
    runner_self.state.set_mp(0, 10)  # MP 10

    runner_self.state.set_true_hand(0, 0, sundry_id)
    runner_self.step(action=ActionType.ACTION_SELECT_HAND_0)
    
    assert runner_self.state.current_phase == GamePhase.PHASE_MAIN_TARGET_SELECT
    runner_self.step(action=ActionType.ACTION_TARGET_SELF) # 自分対象

    # 即時解決され、PHASE_ENDを経て次のプレイヤーのPHASE_MAINになる
    assert runner_self.state.current_phase == GamePhase.PHASE_MAIN
    assert runner_self.state.current_actor_id == 1
    # MPが回復していること
    assert runner_self.state.get_mp(0) > 10

    # 2. 相手対象（受諾）: 相手へ効果適用
    runner_opp = SimulationRunner()
    runner_opp.state.current_phase = GamePhase.PHASE_MAIN
    runner_opp.state.current_actor_id = 0
    runner_opp.state.set_mp(1, 10)

    runner_opp.state.set_true_hand(0, 0, sundry_id)
    runner_opp.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner_opp.step(action=ActionType.ACTION_TARGET_OPP) # 相手対象

    # 相手のミラー選択フェイズに移行
    assert runner_opp.state.current_phase == GamePhase.PHASE_SUNDRY_SELECT_MIRROR
    assert runner_opp.state.current_actor_id == 1

    # 相手が受諾(ACTION_CONFIRM)する
    runner_opp.step(action=ActionType.ACTION_CONFIRM)

    # 解決されて次のターンのPHASE_MAINへ
    assert runner_opp.state.current_phase == GamePhase.PHASE_MAIN
    assert runner_opp.state.current_actor_id == 1
    # 相手(P1)のMPが回復していること
    assert runner_opp.state.get_mp(1) > 10

    # 3. 相手対象（反射）: スーパーミラーで跳ね返され、自分に効果適用
    runner_reflect = SimulationRunner()
    runner_reflect.state.current_phase = GamePhase.PHASE_MAIN
    runner_reflect.state.current_actor_id = 0
    runner_reflect.state.set_mp(0, 10)
    runner_reflect.state.set_mp(1, 10)

    runner_reflect.state.set_true_hand(0, 0, sundry_id)
    runner_reflect.state.set_true_hand(1, 0, super_mirror_id)

    runner_reflect.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner_reflect.step(action=ActionType.ACTION_TARGET_OPP)

    # P1はスーパーミラーを使用する
    assert runner_reflect.state.current_phase == GamePhase.PHASE_SUNDRY_SELECT_MIRROR
    assert runner_reflect.state.current_actor_id == 1
    runner_reflect.step(action=ActionType.ACTION_SELECT_HAND_0)

    # 反射結果、フェイズはPHASE_SUNDRY_SELECT_MIRRORのままで、アクターがP0(自分)に交代する
    assert runner_reflect.state.current_phase == GamePhase.PHASE_SUNDRY_SELECT_MIRROR
    assert runner_reflect.state.current_actor_id == 0

    # 自分が受諾する
    runner_reflect.step(action=ActionType.ACTION_CONFIRM)

    # 解決されて自分(P0)のMPが回復する
    assert runner_reflect.state.get_mp(0) > 10
    # 相手(P1)のMPは10のまま
    assert runner_reflect.state.get_mp(1) == 10


def test_buy_logic_refusal_known():
    """
    検証内容: 買う (Buy) アクションにおいて、購入を拒否した場合の is_known_to_opp フラグの挙動。
    - パターン1: 相手の手札から提示されたカードが新規タイプの場合
      ➔ 拒否後も is_known_to_opp は True のまま（相手がそれを持っていることを記憶）。
    - パターン2: 相手の手札内に、既に同じカードタイプで is_known_to_opp == True のカードが存在する場合
      ➔ スロット重複公開を防ぐため、今回提示されたカードの is_known_to_opp は False に戻る。
    - パターン3: 相手のフィールド上に、同じ名前の「展開済みの奇跡（is_deployed == True）」が存在するが、
      手札内の未展開の同名奇跡は非公開（known=False）の状態で、それが提示された場合
      ➔ 展開済みと手札内（未展開）は別情報として扱うため、拒否後も手札の奇跡は is_known_to_opp == True のまま。
    """
    buy_id = find_card_by_name("買う")
    shield_id = find_card_by_name("革の服")
    fire_miracle_id = find_card_by_name("＜火の玉＞")

    # --- パターン1: 新規カードタイプの提示と拒否 ---
    runner1 = SimulationRunner()
    runner1.state.current_phase = GamePhase.PHASE_MAIN
    runner1.state.current_actor_id = 0
    runner1.state.set_money(0, 20)
    runner1.state.set_true_hand(0, 0, buy_id)
    runner1.state.set_true_hand(1, 0, shield_id) # 相手の手札スロット0に「革の服」（非公開）

    runner1.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner1.step(action=ActionType.ACTION_TARGET_OPP)
    runner1.step(action=ActionType.ACTION_CONFIRM)

    # 提示された時点で公開される
    assert runner1.state.get_is_known_to_opp(1, 0) is True

    # 拒否（ACTION_DEAL_NO）を選択
    runner1.step(action=ActionType.ACTION_DEAL_NO)
    # 結果: 購入拒否後も公開フラグは True が維持される
    assert runner1.state.get_is_known_to_opp(1, 0) is True

    # --- パターン2: すでに同種の手札公開カードが存在する状態での提示と拒否 ---
    runner2 = SimulationRunner()
    runner2.state.current_phase = GamePhase.PHASE_MAIN
    runner2.state.current_actor_id = 0
    runner2.state.set_money(0, 20)
    runner2.state.set_true_hand(0, 0, buy_id)
    runner2.state.set_true_hand(1, 0, shield_id) # スロット0に「革の服」（非公開、今回の提示対象）
    runner2.state.set_true_hand(1, 1, shield_id) # スロット1に「革の服」（既に公開済み）
    runner2.state.set_is_known_to_opp(1, 1, True)

    runner2.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner2.step(action=ActionType.ACTION_TARGET_OPP)
    runner2.step(action=ActionType.ACTION_CONFIRM)

    # 提示されたスロット0は一時的に True になる
    assert runner2.state.get_is_known_to_opp(1, 0) is True

    # 拒否（ACTION_DEAL_NO）を選択
    runner2.step(action=ActionType.ACTION_DEAL_NO)
    # 結果: すでにスロット1に既知の「革の服」があったため、スロット0は非公開 (False) に戻る
    assert runner2.state.get_is_known_to_opp(1, 0) is False
    assert runner2.state.get_is_known_to_opp(1, 1) is True # スロット1は当然 True のまま

    # --- パターン3: 展開済みの同名奇跡が存在する状態での提示と拒否 ---
    runner3 = SimulationRunner()
    runner3.state.current_phase = GamePhase.PHASE_MAIN
    runner3.state.current_actor_id = 0
    runner3.state.set_money(0, 20)
    runner3.state.set_true_hand(0, 0, buy_id)
    runner3.state.set_true_hand(1, 0, fire_miracle_id) # スロット0に手札（未展開）の「火」
    runner3.state.set_true_hand(1, 1, fire_miracle_id) # スロット1に「展開済み」の「火」
    runner3.state.set_is_deployed(1, 1, True)
    runner3.state.set_is_known_to_opp(1, 1, True) # 展開済みのため既知

    runner3.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner3.step(action=ActionType.ACTION_TARGET_OPP)
    runner3.step(action=ActionType.ACTION_CONFIRM)

    # 提示された時点で手札の「火」が公開される
    assert runner3.state.get_is_known_to_opp(1, 0) is True

    # 拒否（ACTION_DEAL_NO）を選択
    runner3.step(action=ActionType.ACTION_DEAL_NO)
    # 結果: 展開済みのものは手札内情報と重複しないため、手札の「火」も公開状態（True）が維持される
    assert runner3.state.get_is_known_to_opp(1, 0) is True
    assert runner3.state.get_is_known_to_opp(1, 1) is True


