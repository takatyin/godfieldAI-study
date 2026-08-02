"""ISMCTS（情報集合モンテカルロ木探索）の検証。

学習だけでは拾えない細い筋を探索で見つけるための機構です。求めているのは、

  - 非常に不利な局面で、確率の低い勝ち筋を選ぶ
  - 非常に有利な局面で、確率の低い負け筋を潰す
  - 夢状態で「本当の手札はこうかもしれない」を数える

そのため「落ちないこと」ではなく、以下の性質を検証します。

  1. 決定化が、探索側から見えている情報を書き換えない（見えないものだけ引き直す）
  2. 木は情報集合ごとに1本で、決定化ごとに分かれない（strategy fusion を避ける）
  3. 根では全合法手を必ず1回は見る（方策が0と切り捨てた手を落とさない）
"""

import pytest

import godfield_core
from tests.core.dsl import Game, Side, card_id

MAX_HAND = godfield_core.MAX_HAND_SIZE

WEAPON = "weapons/punch"
ARMOR = "armor/leather-cap"
MIRACLE = "miracles/ice"


def config(**kwargs) -> godfield_core.IsmctsConfig:
    """テスト用の軽い設定（本番既定の1万回は重すぎるため小さくする）。"""
    cfg = godfield_core.IsmctsConfig()
    cfg.num_simulations = 200
    cfg.rollout_max_steps = 60
    cfg.seed = 12345
    for key, value in kwargs.items():
        setattr(cfg, key, value)
    return cfg


def search(game: Game, player: int = 0, **kwargs) -> godfield_core.IsmctsResult:
    return godfield_core.ismcts_search(game.state, player, config(**kwargs))


def board(**kwargs) -> Game:
    """武器・防具・奇跡が選べる、合法手が複数ある局面。"""
    return Game(
        p0=Side(hand=[WEAPON, ARMOR, MIRACLE], mp=20),
        p1=Side(hand=[ARMOR]),
        **kwargs,
    )


# ============================================================================
# 基本
# ============================================================================


def test_search_returns_a_legal_action():
    game = board()
    result = search(game)

    legal = [a for a, ok in enumerate(game.legal_actions()) if ok]
    assert result.best_action in legal, (
        f"非合法な手を返しました: {result.best_action} / 合法手: {legal}"
    )


def test_result_arrays_line_up():
    result = search(board())

    assert len(result.actions) == len(result.visits) == len(result.values) == len(result.priors)
    assert len(result.actions) > 1, "合法手が複数ある局面のはずです"
    assert sum(result.visits) > 0


def test_root_actions_are_exactly_the_legal_actions():
    game = board()
    result = search(game)

    legal = [a for a, ok in enumerate(game.legal_actions()) if ok]
    assert sorted(result.actions) == legal


def test_more_simulations_means_more_visits():
    few = search(board(), num_simulations=100)
    many = search(board(), num_simulations=500)

    assert sum(many.visits) > sum(few.visits)


@pytest.mark.parametrize("sims", [1, 2, 10])
def test_tiny_budgets_do_not_crash(sims):
    """合法手の数より少ない予算でも壊れないこと。"""
    result = search(board(), num_simulations=sims)
    assert result.best_action in result.actions


# ============================================================================
# 細い筋を落とさないための仕掛け
# ============================================================================


def test_every_root_action_is_tried_at_least_once():
    """根では全合法手を1回は見る。

    自傷攻撃のように学習済み方策が事前確率をほぼ0にする手は、素の PUCT では
    二度と訪問されない。根は1ノードしかないので、追加コストは |A|/num_simulations
    （15手・200回なら 7.5%、本番の1万回なら 0.15%）でしかない。
    """
    result = search(board(), num_simulations=300, expand_root_fully=True)

    unseen = [a for a, v in zip(result.actions, result.visits) if v == 0]
    assert not unseen, f"一度も評価していない根の手があります: {unseen}"


def test_prior_floor_keeps_every_action_reachable():
    """事前分布の下限により、どの手にも0でない確率が残る。"""
    result = search(board(), prior_floor=0.05)

    assert all(p > 0 for p in result.priors), f"事前確率0の手があります: {list(result.priors)}"
    assert abs(sum(result.priors) - 1.0) < 1e-3, (
        f"事前分布が正規化されていません: 合計 {sum(result.priors)}"
    )


# ============================================================================
# 探索して初めて分かることを見つけられるか
# ============================================================================


def test_search_takes_the_win_when_one_exists():
    """相手が瀕死なら、攻撃カードを選ぶ手が最も高く評価される。"""
    game = Game(p0=Side(hp=40, hand=[WEAPON, ARMOR]), p1=Side(hp=1))
    result = search(game, num_simulations=800)

    weapon_slot = godfield_core.ActionType.ACTION_SELECT_HAND_0
    assert result.best_action == int(weapon_slot), (
        "勝ちに直結する攻撃を選んでいません: "
        f"{godfield_core.ActionType(result.best_action).name}"
    )
    value = dict(zip(result.actions, result.values))[int(weapon_slot)]
    assert value > 0.5, f"勝ち筋の価値が低すぎます: {value:+.3f}"


def test_a_hopeless_position_is_valued_as_losing():
    """勝ち目のない局面では、どの手を選んでも価値が負になる。

    これは「相手手番のノードで符号を反転する」処理の回帰テストです。反転を忘れると
    相手がこちらに都合よく指してくれる前提の探索になり、負けている局面が
    負けに見えなくなります（＝有利な局面で細い負け筋を潰せなくなる）。
    """
    game = Game(
        p0=Side(hp=1, hand=[ARMOR]),
        p1=Side(hp=40, hand=["weapons/gold-club"] * 4),
    )
    result = search(game, num_simulations=1500)

    assert all(v < -0.3 for v in result.values), (
        "詰んでいる局面が負けとして評価されていません: "
        f"{[f'{v:+.2f}' for v in result.values]}"
    )


def test_a_winning_position_is_valued_as_winning():
    game = Game(p0=Side(hp=40, hand=[WEAPON, WEAPON, WEAPON]), p1=Side(hp=1))
    result = search(game, num_simulations=800)

    assert max(result.values) > 0.5, (
        f"勝勢の局面が勝ちとして評価されていません: {[f'{v:+.2f}' for v in result.values]}"
    )


def test_search_survives_a_large_hidden_opponent_hand():
    """相手の手札が多いほど、決定化のたびに合法手が入れ替わる。

    木に固定した手をそのまま指そうとすると、非合法な手を `step_game` に渡して
    状態を壊します。合法手を毎回引き直していることの検証です。
    """
    game = Game(
        p0=Side(hp=40, hand=[WEAPON, ARMOR, MIRACLE], mp=20),
        p1=Side(hp=40, hand=[WEAPON] * 14, mp=30),
    )
    result = search(game, num_simulations=2000)

    assert result.best_action in result.actions
    assert all(-1.0 <= v <= 1.0 for v in result.values)


# ============================================================================
# 決定化 — 見えているものは変えない
# ============================================================================


def hand_of(game: Game, player: int) -> list[int]:
    return [game.state.get_true_hand(player, i) for i in range(MAX_HAND)]


def test_determinize_does_not_touch_my_own_hand():
    game = Game(p0=Side(hand=[WEAPON, ARMOR, MIRACLE]), p1=Side(hand=[ARMOR] * 5))
    before = hand_of(game, 0)

    godfield_core.ismcts_determinize(game.state, 0, 999)

    assert hand_of(game, 0) == before, "自分の手札が書き換わっています"


def test_determinize_does_not_touch_revealed_opponent_cards():
    """公開済み・展開済みの相手カードは既知の情報なので変えてはならない。"""
    game = Game(
        p0=Side(hand=[WEAPON]),
        p1=Side(hand=[MIRACLE, ARMOR, WEAPON, WEAPON], mp=20, known_to_opp=[1], deployed=[0]),
    )
    before = (game.state.get_true_hand(1, 0), game.state.get_true_hand(1, 1))

    godfield_core.ismcts_determinize(game.state, 0, 999)

    after = (game.state.get_true_hand(1, 0), game.state.get_true_hand(1, 1))
    assert after == before, (
        "相手の公開済み・展開済みカードが書き換わっています: "
        f"期待 {before} / 実際 {after}"
    )


def test_determinize_resamples_hidden_opponent_cards():
    """見えていない相手の手札は山札の分布から引き直される。"""
    changed = False
    for seed in range(20):
        game = Game(p0=Side(hand=[WEAPON]), p1=Side(hand=[WEAPON] * 8))
        godfield_core.ismcts_determinize(game.state, 0, seed)
        if any(game.state.get_true_hand(1, i) != card_id(WEAPON) for i in range(8)):
            changed = True
            break
    assert changed, "20通りのシードで引き直しても相手の手札が一度も変わりませんでした"


def test_determinize_preserves_the_opponent_hand_size():
    """枚数は既知の情報。空きスロットを埋めたりカードを消したりしない。"""
    game = Game(p0=Side(hand=[WEAPON]), p1=Side(hand=[WEAPON, MIRACLE, ARMOR]))
    occupied = lambda: sum(  # noqa: E731
        1 for i in range(MAX_HAND) if game.state.get_true_hand(1, i) != godfield_core.CARD_EMPTY
    )
    before = occupied()

    godfield_core.ismcts_determinize(game.state, 0, 7)

    assert occupied() == before


def test_determinize_is_symmetric_for_player_1():
    """探索側が P1 のときは、P0 の手札が引き直され P1 の手札が保たれる。"""
    game = Game(p0=Side(hand=[WEAPON] * 8), p1=Side(hand=[WEAPON, ARMOR, MIRACLE]))
    mine_before = hand_of(game, 1)

    godfield_core.ismcts_determinize(game.state, 1, 3)

    assert hand_of(game, 1) == mine_before, "探索側 P1 の手札が書き換わっています"


# ============================================================================
# 決定性
# ============================================================================


def test_the_same_seed_gives_the_same_search():
    a = search(board(), seed=42)
    b = search(board(), seed=42)

    assert list(a.visits) == list(b.visits)
    assert a.best_action == b.best_action


def test_different_seeds_explore_differently():
    a = search(board(), seed=1, num_simulations=300)
    b = search(board(), seed=2, num_simulations=300)

    assert list(a.visits) != list(b.visits), "シードを変えても探索が全く同一です"


# ============================================================================
# 統計
# ============================================================================


def test_stats_are_recorded():
    search(board(), num_simulations=200)
    stats = godfield_core.ismcts_last_stats()

    assert stats.simulations == 200
    assert stats.nodes > 1, "木が根だけで育っていません"
    assert stats.game_steps > 0
    assert stats.max_depth >= 1


def test_the_tree_is_shared_across_determinizations():
    """決定化ごとに木を作り直していないこと（PIMC ではなく ISMCTS であること）。

    決定化ごとに独立した木を張ると、ノード数はシミュレーション回数に比例して
    増える。情報集合ごとに1本なら、根の子は合法手の数で頭打ちになる。
    """
    result = search(board(), num_simulations=400)
    stats = godfield_core.ismcts_last_stats()

    root_children = len(result.actions)
    assert stats.nodes < stats.simulations * root_children, (
        "決定化ごとに木が分かれている疑いがあります: "
        f"ノード数 {stats.nodes} / シミュレーション {stats.simulations}"
    )
