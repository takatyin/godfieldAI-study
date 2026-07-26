"""昇天弓の攻撃が直前の攻撃の保留状態を引き継がないことのテスト。

昇天弓は「死亡時に光属性・命中率75%・攻撃力30で、所持していた弓の枚数分だけ攻撃する」
カードであり、状態異常の付与やお金の奪取といった効果は一切持ちません。

しかし昇天弓の防御フェイズ起動処理は `pending_attack_*` 系のフィールドを個別に
設定しており、状態異常（`pending_attack_curse`）とCP奪取（`pending_take_cp`）の
リセットが漏れていました。これらを初期化する `cleanup_phase_end()` は
ターン終了処理の CLEANUP ステップでしか呼ばれず、昇天弓が発射される
DEATH_CHECK_START はそれより前に走るため、直前の攻撃の効果が弓に引き継がれます。
"""

import godfield_core
from godfield_core import ActionType
from tests.core.test_utils import SimulationRunner, find_card_by_name

SICKNESS_NONE = godfield_core.SicknessType.SICKNESS_NONE
SICKNESS_COLD = godfield_core.SicknessType.SICKNESS_COLD

SEED_SEARCH_LIMIT = 2000


def _setup_cursed_attack_then_bow(sim: SimulationRunner, seed: int):
    """「激突風剣」で攻撃した直後に、相手の昇天弓が自分へ飛んでくる盤面を作ります。

    激突風剣: 攻撃力13・命中率100%・無属性・風邪を付与。
    昇天弓を事前にキューへ積んでおくことで、ターン終了時の死亡判定で発射されます。
    """
    gale_sword_id = find_card_by_name("weapons/severe-gale-sword")

    sim.reset_state()
    sim.state.seed_rng(seed)
    sim.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
    sim.state.current_actor_id = 0
    sim.state.set_hp(0, 90)  # 昇天弓の30ダメージでは死なないHP
    sim.state.set_hp(1, 40)
    sim.state.set_sickness(0, SICKNESS_NONE)
    sim.state.set_sickness(1, SICKNESS_NONE)

    sim.set_hand(0, [gale_sword_id])
    sim.set_hand(1, [])  # 防具を持たせず、防御は自動確定させる

    # プレイヤー1の昇天弓を発射待ちキューに積む
    sim.state.set_pending_ascension_bows(1, 1)


def _resolve_attack_and_bow(sim: SimulationRunner):
    """攻撃 → プレイヤー1の防御確定 → （弓命中時）プレイヤー0の防御確定まで進めます。"""
    sim.perform_attack([0])
    sim.step(ActionType.ACTION_CONFIRM)  # プレイヤー1が防御を確定（防具なしのため素受け）
    if sim.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE:
        # 昇天弓が命中し、プレイヤー0に防御フェイズが回ってきた
        sim.step(ActionType.ACTION_CONFIRM)


def _find_seed_where_bow_hits() -> int:
    """昇天弓（命中率75%）が命中し、プレイヤー0がダメージを受けるシードを探します。"""
    sim = SimulationRunner()
    for seed in range(SEED_SEARCH_LIMIT):
        _setup_cursed_attack_then_bow(sim, seed)
        _resolve_attack_and_bow(sim)
        if sim.state.get_hp(0) < 90:  # 昇天弓が命中している
            return seed

    raise ValueError("Could not find a seed where the ascension bow hits player 0")


def test_ascension_bow_does_not_inherit_previous_attack_curse():
    """
    検証内容: 昇天弓が直前の攻撃の状態異常付与を引き継がないこと。
    - プレイヤー0が「激突風剣」（風邪付与）でプレイヤー1を攻撃した直後、
      プレイヤー1の昇天弓がプレイヤー0に命中する状況を作ります。
    - 攻撃を受けたプレイヤー1には風邪が付与されますが、昇天弓には状態異常付与の
      効果がないため、被弾したプレイヤー0は健康なままである必要があります。
    """
    seed = _find_seed_where_bow_hits()

    sim = SimulationRunner()
    _setup_cursed_attack_then_bow(sim, seed)
    _resolve_attack_and_bow(sim)

    # 前提: 激突風剣がプレイヤー1に命中し、風邪を付与している
    assert sim.state.get_hp(1) == 27  # 40 - 13
    assert sim.state.get_sickness(1) == SICKNESS_COLD

    # 昇天弓は状態異常を付与しないため、プレイヤー0は健康なまま
    assert sim.state.get_sickness(0) == SICKNESS_NONE

    # 風邪を引いていなければターン終了時の病気ダメージもないため、弓の30ダメージのみ
    assert sim.state.get_hp(0) == 60  # 90 - 30
