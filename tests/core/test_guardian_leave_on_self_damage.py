"""守護神の離脱判定（自傷ダメージ経路）のテスト。

守護神は「ダメージを受けてHPが減少した」際に GUARDIAN_LEAVE_RATE の確率で離脱します。
この判定は相手からの攻撃を受けた場合だけでなく、自分自身へのダメージ
（奇跡の自己攻撃、終末の時に引いた悪魔カードなど）でも同様に行われる必要があります。

ここでは自傷ダメージ経路でも離脱判定が「確率的に」実行されること
（＝必ず離脱するのでもなく、判定自体がスキップされるのでもないこと）を検証します。
"""

import godfield_core
from godfield_core import ActionType
from tests.core.test_utils import SimulationRunner, find_card_by_name

GUARDIAN_NONE = 0
GUARDIAN_MARS = 1

SEED_SEARCH_LIMIT = 5000


def _setup_miracle_self_attack(sim: SimulationRunner, seed: int):
    """HP40・守護神ありのP0が、自分自身へ＜滝＞(命中率100%, ATK25)を撃つ盤面を作ります。"""
    waterfall_id = find_card_by_name("＜滝＞")

    sim.reset_state()
    sim.state.seed_rng(seed)
    sim.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    sim.state.current_actor_id = 0
    sim.state.set_hp(0, 40)
    sim.state.set_mp(0, 40)
    sim.state.set_guardian(0, GUARDIAN_MARS)
    sim.state.set_guardian(1, GUARDIAN_NONE)  # 相手の守護神行動によるノイズを排除
    sim.set_hand(0, [waterfall_id])


def _resolve_miracle_self_attack(sim: SimulationRunner):
    sim.step(ActionType.ACTION_SELECT_HAND_0)
    sim.step(ActionType.ACTION_TARGET_SELF)


def _find_seed_for_miracle_self_attack(want_leave: bool) -> int:
    """自己攻撃で守護神が離脱する（またはしない）シードを探します。"""
    sim = SimulationRunner()
    for seed in range(SEED_SEARCH_LIMIT):
        _setup_miracle_self_attack(sim, seed)
        _resolve_miracle_self_attack(sim)

        # 自傷ダメージが実際に入っていることを前提条件として確認
        if sim.state.get_hp(0) >= 40:
            continue

        did_leave = sim.state.get_guardian(0) == GUARDIAN_NONE
        if did_leave == want_leave:
            return seed

    raise ValueError(f"Could not find a seed with guardian_leave={want_leave} for miracle self-attack")


def test_miracle_self_attack_can_trigger_guardian_leave():
    """
    検証内容: 奇跡を自分自身に撃った際の守護神離脱判定。
    - 自分に＜滝＞(ATK25)を撃ってHPが減少した場合、守護神の離脱判定が行われ、
      判定に当たったシードでは守護神が離脱（GUARDIAN_NONE）することを確認します。
    """
    seed = _find_seed_for_miracle_self_attack(want_leave=True)

    sim = SimulationRunner()
    _setup_miracle_self_attack(sim, seed)
    _resolve_miracle_self_attack(sim)

    assert sim.state.get_hp(0) == 15  # 40 - 25
    assert sim.state.get_guardian(0) == GUARDIAN_NONE


def test_miracle_self_attack_guardian_leave_is_probabilistic():
    """
    検証内容: 自傷ダメージによる守護神離脱が確率判定であることの確認。
    - 離脱判定に外れたシードでは、HPが減少していても守護神が残留することを確認します。
    - これにより、離脱が「必ず起きる」実装になっていないことを保証します。
    """
    seed = _find_seed_for_miracle_self_attack(want_leave=False)

    sim = SimulationRunner()
    _setup_miracle_self_attack(sim, seed)
    _resolve_miracle_self_attack(sim)

    assert sim.state.get_hp(0) == 15  # 40 - 25
    assert sim.state.get_guardian(0) == GUARDIAN_MARS


def _setup_thump_thump_tear(sim: SimulationRunner, seed: int):
    """守護神ありのP0が、自分自身へ「ドキドキ涙」を使う盤面を作ります。

    ドキドキ涙はHPが+10か-10のいずれかにランダムで振れる雑貨です。
    """
    tear_id = find_card_by_name("sundries/thump-thump-tear")

    sim.reset_state()
    sim.state.seed_rng(seed)
    sim.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    sim.state.current_actor_id = 0
    sim.state.set_hp(0, 40)
    sim.state.set_guardian(0, GUARDIAN_MARS)
    sim.state.set_guardian(1, GUARDIAN_NONE)
    sim.set_hand(0, [tear_id])


def _find_seed_for_thump_thump_tear_leave() -> int:
    """ドキドキ涙がHP-10を引き、かつ守護神が離脱するシードを探します。"""
    sim = SimulationRunner()
    for seed in range(SEED_SEARCH_LIMIT):
        _setup_thump_thump_tear(sim, seed)
        sim.step(ActionType.ACTION_SELECT_HAND_0)
        sim.step(ActionType.ACTION_TARGET_SELF)

        if sim.state.get_hp(0) != 30:  # HP-10 を引いたケースのみ対象
            continue
        if sim.state.get_guardian(0) == GUARDIAN_NONE:
            return seed

    raise ValueError("Could not find a seed where the thump thump tear triggers guardian leave")


def test_thump_thump_tear_hp_loss_can_trigger_guardian_leave():
    """
    検証内容: 雑貨「ドキドキ涙」によるHP減少でも守護神の離脱判定が行われること。
    - ドキドキ涙はHPが±10に振れる雑貨で、-10を引いた場合はダメージとして扱われます。
    - 攻撃由来でなくHPが減った場合でも、守護神の離脱判定が走ることを確認します。
    """
    seed = _find_seed_for_thump_thump_tear_leave()

    sim = SimulationRunner()
    _setup_thump_thump_tear(sim, seed)
    sim.step(ActionType.ACTION_SELECT_HAND_0)
    sim.step(ActionType.ACTION_TARGET_SELF)

    assert sim.state.get_hp(0) == 30  # 40 - 10
    assert sim.state.get_guardian(0) == GUARDIAN_NONE


def _setup_apocalypse_devil_draw(sim: SimulationRunner, seed: int):
    """終末の時（ターン150以降）に、空きスロットへドローするP0の盤面を作ります。

    終末の時のドローでは一定確率で悪魔カードが引かれ、即時に自傷ダメージが入ります。
    """
    sim.reset_state()
    sim.state.seed_rng(seed)
    sim.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    sim.state.current_actor_id = 0
    sim.state.current_turn = 150  # APOCALYPSE_TURN
    sim.state.set_hp(0, 90)  # 大悪魔(30)でも死亡しないHP
    sim.state.set_guardian(0, GUARDIAN_MARS)
    sim.state.set_guardian(1, GUARDIAN_NONE)
    sim.set_hand(0, [])  # 手札を空にしてドロー枠を確保


def _find_seed_for_devil_self_damage() -> int:
    """終末の時のドローで悪魔を引き、かつ守護神が離脱するシードを探します。"""
    sim = SimulationRunner()
    for seed in range(SEED_SEARCH_LIMIT):
        _setup_apocalypse_devil_draw(sim, seed)
        sim.step(ActionType.ACTION_PRAY)

        # 悪魔による自傷ダメージが入ったケースのみを対象にする
        if sim.state.get_hp(0) >= 90:
            continue
        if sim.state.get_guardian(0) == GUARDIAN_NONE:
            return seed

    raise ValueError("Could not find a seed where an apocalypse devil draw triggers guardian leave")


def test_apocalypse_devil_damage_can_trigger_guardian_leave():
    """
    検証内容: 終末の時に引いた悪魔カードの自傷ダメージによる守護神離脱判定。
    - 終末の時のドローで悪魔を引くとHPが即時に減少しますが、この自傷ダメージでも
      守護神の離脱判定が行われることを確認します。
    """
    seed = _find_seed_for_devil_self_damage()

    sim = SimulationRunner()
    _setup_apocalypse_devil_draw(sim, seed)
    sim.step(ActionType.ACTION_PRAY)

    assert sim.state.get_hp(0) < 90  # 悪魔による自傷ダメージが入っている
    assert sim.state.get_guardian(0) == GUARDIAN_NONE
