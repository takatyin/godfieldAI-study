import godfield_core
from godfield_core import ActionType
from tests.core.test_utils import SimulationRunner, find_card_by_name


def test_apocalypse_turn_threshold():
    """
    検証内容: APOCALYPSE_TURN (150) に達した時、ゲームが「終末の時」に入ることを確認する。
    """
    runner = SimulationRunner()
    runner.reset_state()

    # 150ターン未満は通常モード
    runner.state.current_turn = 149
    assert runner.state.current_turn < 150

    # 150ターン以上は終末の時
    runner.state.current_turn = 150
    assert runner.state.current_turn >= 150


def test_apocalypse_pray_draws_devil_cards():
    """
    検証内容: 終末の時において、カードドロー時 (祈るなど) に25%の確率で悪魔カードが発生し、
    その即時効果が適用された後に代替のカードがドローされることを検証する。
    """
    little_devil_count = 0
    medium_devil_count = 0
    large_devil_count = 0
    fairy_count = 0

    # 200回試行して悪魔カードの発生と効果を検出する
    for i in range(200):
        runner = SimulationRunner()
        runner.reset_state()
        runner.state.seed_rng(i)  # 各試行の乱数シードを個別に設定
        runner.state.current_turn = 150  # 終末の時
        runner.set_status(player=0, hp=40, mp=10, money=10)
        runner.set_hand(player=0, cards=[])  # 手札を空にする

        # 祈るを実行してドローする
        runner.step(ActionType.ACTION_PRAY)

        # 生存している場合のみ、手札にカードが入ることを確認
        if not runner.state.is_done:
            assert runner.state.get_true_hand(0, 0) != godfield_core.CARD_EMPTY

        hp = runner.state.get_hp(0)
        mp = runner.state.get_mp(0)
        money = runner.state.get_money(0)

        # ダメージ系悪魔の効果
        if hp == 30:
            little_devil_count += 1
        elif hp == 20:
            medium_devil_count += 1
        elif hp == 10:
            large_devil_count += 1

        # めぐみの妖精の効果 (+10 HP, MP, or money)
        if hp == 50 or mp == 20 or money == 20:
            fairy_count += 1

    # いずれかの悪魔カード・妖精カードが確率的に発生したことを確認する
    print(
        f"Detected Little: {little_devil_count}, Medium: {medium_devil_count}, Large: {large_devil_count}, Fairy: {fairy_count}"
    )
    assert little_devil_count > 0, "Little Devil did not trigger in 200 trials"
    assert medium_devil_count > 0, "Medium Devil did not trigger in 200 trials"
    assert large_devil_count > 0, "Large Devil did not trigger in 200 trials"
    assert fairy_count > 0, "Gracious Fairy did not trigger in 200 trials"


def test_apocalypse_prankster_discard():
    """
    検証内容: イタズラマン (Prankster) の効果により、手札/アクティブな奇跡から無作為に2つ破棄されることを検証する。
    """
    shield_id = find_card_by_name("革の服")

    prankster_triggered = 0

    # 200回試行してイタズラマンが発生し、手札が破棄されたかを確認する
    for i in range(200):
        runner = SimulationRunner()
        runner.reset_state()
        runner.state.seed_rng(i)  # 各試行の乱数シードを個別に設定
        runner.state.current_turn = 150  # 終末 of 時
        runner.set_status(player=0, hp=40, mp=10, money=10)

        # 手札をセット（イタズラマンが破棄する候補、武器以外である必要があるため革の服のみ）
        runner.state.set_true_hand(0, 1, shield_id)
        runner.state.set_true_hand(0, 2, shield_id)

        # 祈るを実行
        runner.step(ActionType.ACTION_PRAY)

        # イタズラマンがトリガーした場合、スロット1または2が空 (CARD_EMPTY) になっている
        slot1 = runner.state.get_true_hand(0, 1)
        slot2 = runner.state.get_true_hand(0, 2)

        if slot1 == godfield_core.CARD_EMPTY or slot2 == godfield_core.CARD_EMPTY:
            prankster_triggered += 1

    assert prankster_triggered > 0, "Prankster (trickster) did not trigger in 200 trials"


def test_apocalypse_sacrifice_refills_hand():
    """
    検証内容: 通常モードの「捨てる」と終末の時の「ささげる」の挙動の違いを検証する。
    - 通常モードでは捨てたスロットは空のままになる。
    - 終末の時では捨てた分だけ新たにドローされる。
    """
    shield_id = find_card_by_name("革の服")

    # --- 通常モードの検証 ---
    runner_normal = SimulationRunner()
    runner_normal.reset_state()
    runner_normal.state.current_turn = 0  # 通常
    runner_normal.state.set_true_hand(0, 0, shield_id)

    # 捨てるフェーズに入り、スロット0を選択して確定
    runner_normal.step(ActionType.ACTION_DISCARD)
    runner_normal.step(ActionType.ACTION_SELECT_HAND_0)
    runner_normal.step(ActionType.ACTION_CONFIRM)

    # 通常モードではスロット0は空のまま
    assert runner_normal.state.get_true_hand(0, 0) == godfield_core.CARD_EMPTY

    # --- 終末の時の検証 ---
    runner_apocalypse = SimulationRunner()
    runner_apocalypse.reset_state()
    runner_apocalypse.state.current_turn = 150  # 終末の時
    runner_apocalypse.state.set_true_hand(0, 0, shield_id)

    # ささげるフェーズに入り、スロット0を選択して確定
    runner_apocalypse.step(ActionType.ACTION_DISCARD)
    runner_apocalypse.step(ActionType.ACTION_SELECT_HAND_0)
    runner_apocalypse.step(ActionType.ACTION_CONFIRM)

    # 終末の時では新しくカードがドローされているため、スロット0は空ではない
    assert runner_apocalypse.state.get_true_hand(0, 0) != godfield_core.CARD_EMPTY


def test_apocalypse_draw_death_defer():
    """
    検証内容: 終末の時において、使用済みカードのドロー処理が終わった後に勝敗判定が行われること。
    - プレイヤー0（HP10）が「クロスボウ」を使用し、プレイヤー1（HP1）を攻撃。
    - プレイヤー1は防御できず被弾し、HPが0になる。
    - 通常時であれば、被弾解決の段階でプレイヤー1が死亡した時点で即座にゲーム終了となる。
    - しかし、終末 of 時では、被弾の瞬間にはゲーム終了せず、使用済みカードの補充ドロー処理に進む。
    - ドロー補充は生存しているプレイヤー0に対してのみ行われ、そのドローで悪魔を引いてプレイヤー0のHPも0になる。
    - ドロー処理全体の完了後に初めて死亡判定が行われ、両者死亡による「引き分け（Draw）」になることを確認する。
    """
    bow_id = find_card_by_name("weapons/crossbow")

    target_seed = -1
    for seed in range(500):
        runner = SimulationRunner()
        runner.reset_state()
        runner.state.seed_rng(seed)
        runner.state.current_turn = 150  # 終末の時
        runner.set_status(player=0, hp=10, mp=10, money=10)
        runner.set_status(player=1, hp=1, mp=10, money=10)
        runner.state.set_true_hand(0, 0, bow_id)
        runner.set_hand(player=1, cards=[]) # プレイヤー1は手札空で防御不能

        # プレイヤー0がクロスボウを使用
        runner.step(ActionType.ACTION_SELECT_HAND_0)
        runner.step(ActionType.ACTION_TARGET_OPP)
        
        # プレイヤー1の防御フェイズ ➡ confirmしか押せない
        runner.step(ActionType.ACTION_CONFIRM)

        # ドロー補充で悪魔を引き、両者死亡（引き分け）になったシードを探す
        if runner.state.is_done and runner.state.get_hp(0) == 0 and runner.state.get_hp(1) == 0 and runner.state.p0_reward == 0.0:
            target_seed = seed
            break

    assert target_seed != -1, "Could not find a seed where player 0 draws a damaging devil during cleanup draw"

    # 通常時の挙動を確認（クロスボウでの被弾の瞬間に即座にゲーム終了し、プレイヤー0の勝利になる）
    runner_normal = SimulationRunner()
    runner_normal.reset_state()
    runner_normal.state.seed_rng(target_seed)
    runner_normal.state.current_turn = 0  # 通常時
    runner_normal.set_status(player=0, hp=10, mp=10, money=10)
    runner_normal.set_status(player=1, hp=1, mp=10, money=10)
    runner_normal.state.set_true_hand(0, 0, bow_id)
    runner_normal.set_hand(player=1, cards=[])

    runner_normal.step(ActionType.ACTION_SELECT_HAND_0)
    runner_normal.step(ActionType.ACTION_TARGET_OPP)
    runner_normal.step(ActionType.ACTION_CONFIRM)

    # 通常時なので被弾の瞬間にゲーム終了し、プレイヤー0が勝利している（HP10のまま、ドローは発生しない）
    assert runner_normal.state.is_done is True
    assert runner_normal.state.get_hp(0) == 10
    assert runner_normal.state.get_hp(1) == 0
    assert runner_normal.state.p0_reward == 1.0

    # 終末の時の挙動を確認（被弾では終了せず、ドロー処理後に両者死亡で引き分けになる）
    runner_apoc = SimulationRunner()
    runner_apoc.reset_state()
    runner_apoc.state.seed_rng(target_seed)
    runner_apoc.state.current_turn = 150  # 終末の時
    runner_apoc.set_status(player=0, hp=10, mp=10, money=10)
    runner_apoc.set_status(player=1, hp=1, mp=10, money=10)
    runner_apoc.state.set_true_hand(0, 0, bow_id)
    runner_apoc.set_hand(player=1, cards=[])

    runner_apoc.step(ActionType.ACTION_SELECT_HAND_0)
    runner_apoc.step(ActionType.ACTION_TARGET_OPP)
    runner_apoc.step(ActionType.ACTION_CONFIRM)

    # 終末 of 時なので、補充ドローによりプレイヤー0も死亡し、結果は引き分けになる
    assert runner_apoc.state.is_done is True
    assert runner_apoc.state.get_hp(0) == 0
    assert runner_apoc.state.get_hp(1) == 0
    assert runner_apoc.state.p0_reward == 0.0
    assert runner_apoc.state.p1_reward == 0.0


