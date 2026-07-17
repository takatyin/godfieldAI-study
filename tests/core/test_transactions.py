import godfield_core
from godfield_core import ActionType, GamePhase
from tests.core.test_utils import SimulationRunner, find_card_by_name


def test_exchange_logic_normal():
    """
    検証内容: 両替 (Exchange) の正常分配フローのテスト。
    - 両替カードを使用し、HP/MP/Money の合計値を再分配できることを確認します。
    - 合計値（75）を超える再分配（HP 76 など）が非合法手になることを確認します。
    - 新しい割り振りを確定させた際、HP/MP/Money が指定通りに更新されることを確認します。
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

    assert runner.state.current_phase == GamePhase.PHASE_EXCHANGE_HP

    # 合計を超える値は不可
    actions_hp = godfield_core.get_legal_actions(runner.state)
    assert actions_hp[ActionType.ACTION_NUM_30] is True
    assert actions_hp[ActionType.ACTION_NUM_75] is True
    assert actions_hp[ActionType.ACTION_NUM_76] is False

    # HPを 30 に指定 -> MP指定フェイズへ
    runner.step(action=ActionType.ACTION_NUM_30)
    assert runner.state.current_phase == GamePhase.PHASE_EXCHANGE_MP

    # MPの上限は 75 - 30 = 45
    actions_mp = godfield_core.get_legal_actions(runner.state)
    assert actions_mp[ActionType.ACTION_NUM_45] is True
    assert actions_mp[ActionType.ACTION_NUM_46] is False

    # MPを 20 に指定 (残金 25)
    runner.step(action=ActionType.ACTION_NUM_20)

    # 解決確認
    assert runner.state.get_hp(0) == 30
    assert runner.state.get_mp(0) == 20
    assert runner.state.get_money(0) == 25
    assert runner.state.current_phase == GamePhase.PHASE_MAIN


def test_exchange_logic_zero_hp_death():
    """
    検証内容: 両替でのHP 0 指定による即死テスト。
    - 両替でHPの再配分に 0 を指定した場合、両替処理完了時に即座に死亡（is_done = True）となることを確認します。
    """
    runner = SimulationRunner()
    exchange_id = find_card_by_name("両替")

    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_hp(0, 40)
    runner.state.set_mp(0, 20)
    runner.state.set_money(0, 10)  # 合計 = 70
    runner.state.set_true_hand(0, 0, exchange_id)

    runner.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner.step(action=ActionType.ACTION_TARGET_SELF)
    runner.step(action=ActionType.ACTION_NUM_0)   # HPを 0 に指定
    runner.step(action=ActionType.ACTION_NUM_20)  # MPを 20 に指定して確定

    # 即死判定
    assert runner.state.is_done is True
    assert runner.state.p0_reward == -1.0


def test_sell_to_self():
    """
    検証内容: 自分に対する売却（強制買い戻し）テスト。
    - 自分の手札のカード（守護封印のつぼ: 価格 10）を自分自身に売却した際、お金が足りない分は MP -> HP の順に消費して支払われることを確認します。
    - 売却されたカードは自分の手札に維持されることを確認します。
    """
    runner = SimulationRunner()
    sell_id = find_card_by_name("売る")
    pot_id = find_card_by_name("守護封印のつぼ")  # 価格 10

    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_money(0, 5)   # お金 5 (5不足)
    runner.state.set_mp(0, 8)      # MPで5支払う (残り3)
    runner.state.set_hp(0, 50)

    runner.state.set_true_hand(0, 0, sell_id)
    runner.state.set_true_hand(0, 1, pot_id)

    runner.step(action=ActionType.ACTION_SELECT_HAND_0)  # 売る
    runner.step(action=ActionType.ACTION_SELECT_HAND_1)  # つぼを選択
    runner.step(action=ActionType.ACTION_TARGET_SELF)  # 自分を対象

    # 結果: money = 10 (売却益回収), mp = 3, hp = 50
    assert runner.state.get_money(0) == 10
    assert runner.state.get_mp(0) == 3
    assert runner.state.get_true_hand(0, 1) == pot_id


def test_sell_to_opp_accept():
    """
    検証内容: 相手に対する売却の正常解決テスト。
    - 手札のカード（守護封印のつぼ: 価格 10）を相手に売り、相手が受諾（Accept）した際、相手の資産（Money -> MP -> HP）から代金が差し引かれることを確認します。
    - 売却されたカードが相手の手札の空き枠に移り、かつ相手の画面上で既知（is_known_to_opp = True）になることを確認します。
    """
    runner = SimulationRunner()
    sell_id = find_card_by_name("売る")
    pot_id = find_card_by_name("守護封印のつぼ")

    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_money(0, 0)
    runner.state.set_money(1, 4)   # 相手のお金 4 (6不足)
    runner.state.set_mp(1, 10)     # 相手のMP 10 (残り6支払って4)

    runner.state.set_true_hand(0, 0, sell_id)
    runner.state.set_true_hand(0, 1, pot_id)

    runner.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner.step(action=ActionType.ACTION_SELECT_HAND_1)
    runner.step(action=ActionType.ACTION_TARGET_OPP)
    runner.step(action=ActionType.ACTION_CONFIRM)

    # 相手の支払い結果
    assert runner.state.get_money(1) == 0
    assert runner.state.get_mp(1) == 4
    # 自分の売却益
    assert runner.state.get_money(0) == 10

    # カード移動の確認
    found = False
    for j in range(18):
        if runner.state.get_true_hand(1, j) == pot_id:
            found = True
            assert runner.state.get_is_known_to_opp(1, j) is True
            break
    assert found is True


def test_sell_to_self_death():
    """
    検証内容: 自分に対する売却での破産即死テスト。
    - 全総資産（HP 5, MP 0, Money 0）を下回る価格のカード（つぼ: 価格 10）を自分に売却した際、代金を支払い切れずに死亡（is_done = True, HP = 0）することを確認します。
    """
    runner = SimulationRunner()
    sell_id = find_card_by_name("売る")
    pot_id = find_card_by_name("守護封印のつぼ")

    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_hp(0, 5)
    runner.state.set_mp(0, 0)
    runner.state.set_money(0, 0)

    runner.state.set_true_hand(0, 0, sell_id)
    runner.state.set_true_hand(0, 1, pot_id)

    runner.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner.step(action=ActionType.ACTION_SELECT_HAND_1)
    runner.step(action=ActionType.ACTION_TARGET_SELF)

    assert runner.state.is_done is True
    assert runner.state.get_hp(0) == 0
    assert runner.state.p0_reward == -1.0


def test_sell_to_opp_death():
    """
    検証内容: 相手に対する売却による相手の破産即死テスト。
    - 相手の総資産（HP 10, MP 5, Money 5 = 計20）を超える高額カード（神の剣: 価格 30）を相手に売りつけ、相手が受諾した際、相手が死亡（is_done = True）することを確認します。
    """
    runner = SimulationRunner()
    sell_id = find_card_by_name("売る")
    god_sword_id = find_card_by_name("神の剣")  # 価格 30

    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_money(0, 0)
    runner.state.set_hp(1, 10)
    runner.state.set_mp(1, 5)
    runner.state.set_money(1, 5)

    runner.state.set_true_hand(0, 0, sell_id)
    runner.state.set_true_hand(0, 1, god_sword_id)

    runner.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner.step(action=ActionType.ACTION_SELECT_HAND_1)
    runner.step(action=ActionType.ACTION_TARGET_OPP)
    runner.step(action=ActionType.ACTION_CONFIRM)

    # 相手が死亡していること
    assert runner.state.is_done is True


def test_sell_to_opp_mirror_reflect():
    """
    検証内容: 売却時のスーパーミラー反射と強制買い戻し。
    - 相手に売却を行おうとした際、相手が「スーパーミラー」で反射した場合、手番が自分（アクター0）に交代し、自分でそのカード（つぼ）を買い取る（受諾する）流れを確認します。
    """
    runner = SimulationRunner()
    sell_id = find_card_by_name("売る")
    pot_id = find_card_by_name("守護封印のつぼ")
    super_mirror_id = find_card_by_name("スーパーミラー")

    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_money(0, 10)
    runner.state.set_money(1, 0)

    runner.state.set_true_hand(0, 0, sell_id)
    runner.state.set_true_hand(0, 1, pot_id)
    runner.state.set_true_hand(1, 0, super_mirror_id)

    runner.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner.step(action=ActionType.ACTION_SELECT_HAND_1)
    runner.step(action=ActionType.ACTION_TARGET_OPP)

    # 相手がスーパーミラー使用
    assert runner.state.current_phase == GamePhase.PHASE_SELL_SELECT_MIRROR
    runner.step(action=ActionType.ACTION_SELECT_HAND_0)

    # 反射されてアクターが自分(0)に交代
    assert runner.state.current_phase == GamePhase.PHASE_SELL_SELECT_MIRROR
    assert runner.state.current_actor_id == 0

    # 自分が受諾
    runner.step(action=ActionType.ACTION_CONFIRM)

    # 自分がつぼを買い戻した結果の検証
    assert runner.state.get_money(0) == 0
    assert runner.state.get_money(1) == 10
    
    found = False
    for j in range(18):
        if runner.state.get_true_hand(0, j) == pot_id:
            found = True
            assert runner.state.get_is_known_to_opp(0, j) is True
            break
    assert found is True


def test_buy_from_opp_accept():
    """
    検証内容: 相手からの購入（Buy）の正常解決テスト。
    - 自分が「買う」を使用し、相手の手札（つぼ: 価格 10）を購入した際、自分の手持ちのお金から 10 が引かれ、相手に 10 お金が入ることを確認します。
    - 買い取ったカードが自分の手札に移り、かつ相手の画面上で既知（is_known_to_opp = True）になることを確認します。
    """
    runner = SimulationRunner()
    buy_id = find_card_by_name("買う")
    pot_id = find_card_by_name("守護封印のつぼ")

    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_money(0, 20)
    runner.state.set_money(1, 0)
    runner.state.set_true_hand(0, 0, buy_id)
    runner.state.set_true_hand(1, 0, pot_id)

    runner.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner.step(action=ActionType.ACTION_TARGET_OPP)
    runner.step(action=ActionType.ACTION_CONFIRM)

    # 相手の手札が公開状態になる
    assert runner.state.get_is_known_to_opp(1, 0) is True

    # 購入YES
    runner.step(action=ActionType.ACTION_DEAL_YES)

    # 代金移動
    assert runner.state.get_money(0) == 10
    assert runner.state.get_money(1) == 10
    assert runner.state.get_true_hand(1, 0) == godfield_core.CARD_EMPTY

    found = False
    for j in range(18):
        if runner.state.get_true_hand(0, j) == pot_id:
            found = True
            assert runner.state.get_is_known_to_opp(0, j) is True
            break
    assert found is True


def test_buy_from_opp_full_hand():
    """
    検証内容: 手札満杯（18枚）状態でのカード購入テスト。
    - 自分の手札が 18 枚全て埋まっている状態でカードを購入した際、購入したカード（つぼ）が手札のいずれかの既存スロットの防具と正しく置き換わって保存されることを確認します。
    """
    runner = SimulationRunner()
    buy_id = find_card_by_name("買う")
    shield_id = find_card_by_name("革の服")
    pot_id = find_card_by_name("守護封印のつぼ")

    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_money(0, 20)
    runner.state.set_money(1, 0)

    # 手札を埋める (0: 買う, 1~17: 革の服)
    runner.state.set_true_hand(0, 0, buy_id)
    for i in range(1, 18):
        runner.state.set_true_hand(0, i, shield_id)

    runner.state.set_true_hand(1, 0, pot_id)

    runner.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner.step(action=ActionType.ACTION_TARGET_OPP)
    runner.step(action=ActionType.ACTION_CONFIRM)
    runner.step(action=ActionType.ACTION_DEAL_YES)

    # スロット1~17のいずれか1つがつぼに置き換わっていること
    pot_count = 0
    shield_count = 0
    for i in range(1, 18):
        card = runner.state.get_true_hand(0, i)
        if card == pot_id:
            pot_count += 1
        elif card == shield_id:
            shield_count += 1

    assert pot_count == 1
    assert shield_count == 16


def test_buy_from_opp_mirror_reflect():
    """
    検証内容: 購入時のスーパーミラー反射と強制逆購入。
    - 相手に対して「買う」を使用した際、相手が「スーパーミラー」で反射した場合、手番が相手（アクター1）に交代して、相手が自分の手札から買い取る側に回ることを確認します。
    """
    runner = SimulationRunner()
    buy_id = find_card_by_name("買う")
    super_mirror_id = find_card_by_name("スーパーミラー")
    pot_id = find_card_by_name("守護封印のつぼ")

    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_money(0, 0)
    runner.state.set_money(1, 20)

    runner.state.set_true_hand(0, 0, buy_id)
    runner.state.set_true_hand(0, 1, pot_id)
    runner.state.set_true_hand(1, 0, super_mirror_id)

    runner.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner.step(action=ActionType.ACTION_TARGET_OPP)

    # 相手がスーパーミラー使用
    runner.step(ActionType.ACTION_SELECT_HAND_0)

    # アクターがP0(相手)に交代
    assert runner.state.current_phase == GamePhase.PHASE_BUY_SELECT_MIRROR
    assert runner.state.current_actor_id == 0

    # P0が受諾
    runner.step(ActionType.ACTION_CONFIRM)

    # フェイズが PHASE_BUY に移行し、アクターが買い手P1になること
    assert runner.state.current_phase == GamePhase.PHASE_BUY
    assert runner.state.current_actor_id == 1

    # 提示されたカードがつぼ（スロット1）であること
    revealed_idx = runner.state.get_staged_card(0, 0)
    assert runner.state.get_true_hand(0, revealed_idx) == pot_id

    # 購入決定
    runner.step(ActionType.ACTION_DEAL_YES)

    # 代金移動とカード移動の確認
    assert runner.state.get_money(1) == 10
    assert runner.state.get_money(0) == 10
    assert runner.state.get_true_hand(0, revealed_idx) == godfield_core.CARD_EMPTY
    
    found = False
    for j in range(18):
        if runner.state.get_true_hand(1, j) == pot_id:
            found = True
            assert runner.state.get_is_known_to_opp(1, j) is True
            break
    assert found is True


def test_buy_from_opp_mirror_reflect_empty_hand_cancel():
    """
    検証内容: 購入反射時の売却側手札無しによる自動キャンセル。
    - 「買う」のみが手札にあり、他が全て空の状態で相手に「買う」を撃ち、スーパーミラーで跳ね返され、受諾した場合に、売る側の手札が存在しないため購入処理が自動的にキャンセル（スキップ）されて手番が終了することを確認します。
    """
    runner = SimulationRunner()
    buy_id = find_card_by_name("買う")
    super_mirror_id = find_card_by_name("スーパーミラー")

    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_money(0, 0)
    runner.state.set_money(1, 20)

    runner.state.set_true_hand(0, 0, buy_id)
    for j in range(1, 18):
        runner.state.set_true_hand(0, j, godfield_core.CARD_EMPTY)

    runner.state.set_true_hand(1, 0, super_mirror_id)

    runner.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner.step(action=ActionType.ACTION_TARGET_OPP)
    runner.step(action=ActionType.ACTION_SELECT_HAND_0)  # スーパーミラー
    runner.step(action=ActionType.ACTION_CONFIRM)

    # 自動的にキャンセルされ、相手(1)のメインフェイズになっていること
    assert runner.state.current_phase == GamePhase.PHASE_MAIN
    assert runner.state.current_actor_id == 1


def test_buy_refusal_known_new_card():
    """
    検証内容: 購入拒否時の新規カード情報の公開維持テスト。
    - 新しいカード（革の服: 非公開）の購入を拒否（ACTION_DEAL_NO）した場合でも、そのカードがそのスロットにあるという情報（is_known_to_opp）は公開されたまま（True）維持されることを確認します。
    """
    runner = SimulationRunner()
    buy_id = find_card_by_name("買う")
    shield_id = find_card_by_name("革の服")

    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_money(0, 20)
    runner.state.set_true_hand(0, 0, buy_id)
    runner.state.set_true_hand(1, 0, shield_id)

    runner.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner.step(action=ActionType.ACTION_TARGET_OPP)
    runner.step(action=ActionType.ACTION_CONFIRM)

    # 公開される
    assert runner.state.get_is_known_to_opp(1, 0) is True

    # 拒否
    runner.step(ActionType.ACTION_DEAL_NO)
    assert runner.state.get_is_known_to_opp(1, 0) is True


def test_buy_refusal_known_duplicate_card():
    """
    検証内容: 購入拒否時の同種カード重複公開の防止テスト。
    - 既に手札の別スロット（スロット1）に公開済みの「革の服」がある状態で、新たに非公開の同名カード（スロット0: 革の服）が提示され、それを購入拒否した場合に、スロット0の情報公開フラグが非公開（False）に戻ることを確認します（情報量上限クランプ）。
    """
    runner = SimulationRunner()
    buy_id = find_card_by_name("買う")
    shield_id = find_card_by_name("革の服")

    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_money(0, 20)
    runner.state.set_true_hand(0, 0, buy_id)
    runner.state.set_true_hand(1, 0, shield_id)  # 今回の提示スロット (非公開)
    runner.state.set_true_hand(1, 1, shield_id)  # すでに既知のスロット
    runner.state.set_is_known_to_opp(1, 1, True)

    runner.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner.step(action=ActionType.ACTION_TARGET_OPP)
    runner.step(action=ActionType.ACTION_CONFIRM)

    # 提示中は一時的に True
    assert runner.state.get_is_known_to_opp(1, 0) is True

    # 拒否
    runner.step(ActionType.ACTION_DEAL_NO)
    # 重複公開防止ルールにより False に戻る
    assert runner.state.get_is_known_to_opp(1, 0) is False
    assert runner.state.get_is_known_to_opp(1, 1) is True


def test_buy_refusal_known_deployed_miracle():
    """
    検証内容: 購入拒否時の展開中同名奇跡との独立公開テスト。
    - フィールド上に展開済みの「＜火の玉＞」が存在している状態で、手札の未展開かつ非公開の「＜火の玉＞」が提示され、それを購入拒否した場合、展開済みの情報とは独立して、手札の「＜火の玉＞」の情報公開フラグが公開（True）に維持されることを確認します。
    """
    runner = SimulationRunner()
    buy_id = find_card_by_name("買う")
    fire_miracle_id = find_card_by_name("＜火の玉＞")

    runner.state.current_phase = GamePhase.PHASE_MAIN
    runner.state.current_actor_id = 0
    runner.state.set_money(0, 20)
    runner.state.set_true_hand(0, 0, buy_id)
    runner.state.set_true_hand(1, 0, fire_miracle_id) # 手札（非公開）
    runner.state.set_true_hand(1, 1, fire_miracle_id) # 展開済み（既知）
    runner.state.set_is_deployed(1, 1, True)
    runner.state.set_is_known_to_opp(1, 1, True)

    runner.step(action=ActionType.ACTION_SELECT_HAND_0)
    runner.step(action=ActionType.ACTION_TARGET_OPP)
    runner.step(action=ActionType.ACTION_CONFIRM)

    assert runner.state.get_is_known_to_opp(1, 0) is True

    # 拒否
    runner.step(ActionType.ACTION_DEAL_NO)
    
    # 展開済みのものとは別扱いのため、手札のコピーも True のまま維持される
    assert runner.state.get_is_known_to_opp(1, 0) is True
    assert runner.state.get_is_known_to_opp(1, 1) is True


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
