"""昇天弓の攻撃が直前の攻撃の保留状態を引き継がないことのテスト。

昇天弓は「死亡時に光属性・攻撃力30で、所持していた弓の枚数分だけ攻撃する」カードで、
状態異常の付与やCP奪取といった効果は一切持ちません。

しかし昇天弓の防御フェイズ起動処理は `pending_attack_*` 系のフィールドを個別に
設定しており、状態異常（`pending_attack_curse`）とCP奪取（`pending_take_cp`）の
リセットが漏れていました。これらを初期化する `cleanup_phase_end()` は
ターン終了処理の CLEANUP ステップでしか呼ばれず、昇天弓が発射される
DEATH_CHECK_START はそれより前に走るため、直前の攻撃の効果が弓に引き継がれます。

【移行メモ】
従来は昇天弓（命中率75%）が命中するシードを最大2000回探索していました。
命中側しか検証できていなかったため、外れた場合に保留状態がどうなるかは
未検証のままでした。
"""

from godfield_core import Element, GamePhase, RollKind, SicknessType
from tests.core.dsl import Side, card_feature, card_id, element_of

FILLER = "armor/wood-shield"
BOW_POWER = 30  # 死亡時反撃はカードマスタの攻撃力ではなくエンジン側の固定値


def cursed_attack_then_bow(board, *, bow_hits: bool):
    """「激突風剣」で攻撃した直後に、相手の昇天弓が自分へ飛んでくる盤面を解決します。

    激突風剣: 攻撃力13・命中率100%・無属性・風邪を付与。
    昇天弓を事前にキューへ積んでおくことで、ターン終了時の死亡判定で発射されます。
    """
    g = board(
        p0=Side(hp=90, hand=["weapons/severe-gale-sword"]),  # 弓の30では死なないHP
        p1=Side(hp=40, hand=[], pending_ascension_bows=1),   # 防具なしで素受けさせる
    )
    g.rng.deck_always(FILLER)
    g.rng.ascension_bow(bow_hits)
    g.attack("weapons/severe-gale-sword")
    g.take_hit()  # P1 が防御せず被弾
    if g.state.current_phase == GamePhase.PHASE_DEFENSE:
        g.take_hit()  # 弓が命中した場合は P0 が被弾
    return g


def test_gale_sword_applies_cold_to_the_target(board):
    """前提の確認: 激突風剣が相手に命中し、風邪を付与すること。"""
    power = card_feature("weapons/severe-gale-sword", "attack_power")
    g = cursed_attack_then_bow(board, bow_hits=False)

    g.expect(p1_hp=40 - power, p1_sickness=SicknessType.SICKNESS_COLD)
    assert element_of("weapons/severe-gale-sword") == Element.ELEM_NONE


def test_ascension_bow_does_not_inherit_the_previous_attack_curse(board):
    """昇天弓が直前の攻撃の状態異常付与を引き継がないことを検証します。

    攻撃を受けた P1 には風邪が付きますが、昇天弓には状態異常付与の効果がないため、
    被弾した P0 は健康なままである必要があります。
    """
    g = cursed_attack_then_bow(board, bow_hits=True)

    # 昇天弓は状態異常を付与しない
    g.expect(p0_sickness=SicknessType.SICKNESS_NONE)
    # 風邪を引いていないのでターン終了時の病気ダメージもなく、弓の30ダメージのみ
    g.expect(p0_hp=90 - BOW_POWER)


def test_ascension_bow_miss_leaves_the_shooter_unharmed(board):
    """昇天弓が外れた場合、P0 は無傷で状態異常も付かないことを検証します。

    従来は命中するシードだけを探索していたため、外れ側は未検証でした。
    """
    g = cursed_attack_then_bow(board, bow_hits=False)

    g.expect(p0_hp=90, p0_sickness=SicknessType.SICKNESS_NONE, p1_bows=0)
    assert g.rng.consumed(RollKind.ASCENSION_BOW_HIT) == 1


def test_ascension_bow_fires_with_light_element_and_fixed_power(board):
    """昇天弓の反撃が光属性・固定威力30で組まれることを検証します。"""
    g = board(
        p0=Side(hp=90, hand=["weapons/severe-gale-sword"]),
        p1=Side(hp=40, hand=[], pending_ascension_bows=1),
    )
    g.rng.deck_always(FILLER)
    g.rng.ascension_bow(True)
    g.attack("weapons/severe-gale-sword")
    g.take_hit()

    g.expect(
        phase=GamePhase.PHASE_DEFENSE,
        attacker=1,
        defender=0,
        pending_power=BOW_POWER,
        pending_element=Element.ELEM_LIGHT,
    )
    # 攻撃元が直前の激突風剣ではなく昇天弓に差し替わっていること
    assert g.state.pending_attack_source_id == card_id("weapons/ascension-bow")
