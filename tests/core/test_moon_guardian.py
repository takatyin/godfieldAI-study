import godfield_core
from tests.core.test_utils import SimulationRunner, find_card_by_name


def find_seed_for_moon_miracle(target_miracle_id: int) -> int:
    """
    プレイヤー1に月神が憑依している状態で、プレイヤー0が「祈る」を行ってターン終了した際に
    月神が特定の奇跡 (chosen_miracle) を発動するシード値を探索します。
    """
    for seed in range(10000):
        sim = SimulationRunner()
        sim.state.seed_rng(seed)
        sim.set_status(player=0, hp=99, mp=10, money=10)
        sim.set_status(player=1, hp=40, mp=10, money=10)  # HP 40 (泉回復検知用)
        sim.state.set_guardian(1, 10)  # P1 に月神が憑依

        # P0 のターンを「祈る」で終了させる
        sim.step(godfield_core.ActionType.ACTION_PRAY)

        # 状態を確認
        if target_miracle_id == find_card_by_name("miracles/aura"):
            # オーラ + 満月刀 (物理ATK20)
            if (
                sim.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
                and sim.state.pending_attack_power == 20
            ):
                return seed
        elif target_miracle_id == find_card_by_name("miracles/mirage"):
            # 蜃気楼 + 満月刀 (物理ATK10 全体)
            if (
                sim.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
                and sim.state.pending_attack_power == 10
                and sim.state.pending_is_group_attack
            ):
                return seed
        elif target_miracle_id == find_card_by_name("miracles/spring"):
            # 泉 (P1 HP+10 ➡ 50)
            if sim.state.get_hp(1) == 50 and sim.state.current_phase == godfield_core.GamePhase.PHASE_MAIN:
                return seed
        elif target_miracle_id == find_card_by_name("miracles/treasure"):
            # 財宝 (P1 Money+10 ➡ 20)
            if sim.state.get_money(1) == 20 and sim.state.current_phase == godfield_core.GamePhase.PHASE_MAIN:
                return seed
        elif target_miracle_id == find_card_by_name("miracles/release"):
            # 解放 (両者の守護神が 0 になる)
            if (
                sim.state.get_guardian(0) == 0
                and sim.state.get_guardian(1) == 0
                and sim.state.current_phase == godfield_core.GamePhase.PHASE_MAIN
            ):
                return seed
        elif target_miracle_id == 999:  # 攻撃奇跡
            if sim.state.current_phase == godfield_core.GamePhase.PHASE_MIRACLE_DEFENSE:
                if sim.state.pending_attack_power > 0:
                    return seed

    # 歌声用の別探索 (P1 に風邪 sickness=1 を付与しておく)
    for seed in range(10000):
        sim = SimulationRunner()
        sim.state.seed_rng(seed)
        sim.set_status(player=0, hp=99, mp=10, money=10)
        sim.set_status(player=1, hp=99, mp=10, money=10)
        sim.state.set_sickness(1, godfield_core.SicknessType.SICKNESS_COLD)
        sim.state.set_guardian(1, 10)
        sim.step(godfield_core.ActionType.ACTION_PRAY)
        if (
            sim.state.get_sickness(1) == godfield_core.SicknessType.SICKNESS_NONE
            and sim.state.current_phase == godfield_core.GamePhase.PHASE_MAIN
        ):
            return seed

    raise ValueError(f"Could not find seed for Moon miracle {target_miracle_id}")


def test_moon_aura():
    """月神: オーラ重ね (物理ATK20)"""
    aura_id = find_card_by_name("miracles/aura")
    seed = find_seed_for_moon_miracle(aura_id)
    sim = SimulationRunner()
    sim.state.seed_rng(seed)
    sim.set_status(player=0, hp=99)
    sim.set_status(player=1, hp=40)
    sim.state.set_guardian(1, 10)
    sim.step(godfield_core.ActionType.ACTION_PRAY)

    assert sim.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
    assert sim.state.defender_id == 0
    assert sim.state.attacker_id == 1
    assert sim.state.pending_attack_source_id == find_card_by_name("gurdians/full-moon-blade")
    assert sim.state.pending_attack_power == 20
    assert sim.state.pending_attack_element == godfield_core.Element.ELEM_NONE
    assert not sim.state.pending_is_group_attack


def test_moon_mirage():
    """月神: 蜃気楼重ね (物理ATK10 全体)"""
    mirage_id = find_card_by_name("miracles/mirage")
    seed = find_seed_for_moon_miracle(mirage_id)
    sim = SimulationRunner()
    sim.state.seed_rng(seed)
    sim.set_status(player=0, hp=99)
    sim.set_status(player=1, hp=40)
    sim.state.set_guardian(1, 10)
    sim.step(godfield_core.ActionType.ACTION_PRAY)

    assert sim.state.current_phase == godfield_core.GamePhase.PHASE_DEFENSE
    assert sim.state.defender_id == 0
    assert sim.state.attacker_id == 1
    assert sim.state.pending_attack_source_id == find_card_by_name("gurdians/full-moon-blade")
    assert sim.state.pending_attack_power == 10
    assert sim.state.pending_attack_element == godfield_core.Element.ELEM_NONE
    assert sim.state.pending_is_group_attack


def test_moon_spring():
    """月神: 泉 (HP+10)"""
    spring_id = find_card_by_name("miracles/spring")
    seed = find_seed_for_moon_miracle(spring_id)
    sim = SimulationRunner()
    sim.state.seed_rng(seed)
    sim.set_status(player=0, hp=99)
    sim.set_status(player=1, hp=40)
    sim.state.set_guardian(1, 10)
    sim.step(godfield_core.ActionType.ACTION_PRAY)

    assert sim.state.get_hp(1) == 50
    assert sim.state.current_phase == godfield_core.GamePhase.PHASE_MAIN


def test_moon_treasure():
    """月神: 財宝 (Money+10)"""
    treasure_id = find_card_by_name("miracles/treasure")
    seed = find_seed_for_moon_miracle(treasure_id)
    sim = SimulationRunner()
    sim.state.seed_rng(seed)
    sim.set_status(player=0, hp=99)
    sim.set_status(player=1, hp=40, money=10)
    sim.state.set_guardian(1, 10)
    sim.step(godfield_core.ActionType.ACTION_PRAY)

    assert sim.state.get_money(1) == 20


def test_moon_release():
    """月神: 解放 (お互いの守護神を解除)"""
    release_id = find_card_by_name("miracles/release")
    seed = find_seed_for_moon_miracle(release_id)
    sim = SimulationRunner()
    sim.state.seed_rng(seed)
    sim.set_status(player=0, hp=99)
    sim.set_status(player=1, hp=40)
    sim.state.set_guardian(1, 10)
    sim.state.set_guardian(0, 3)
    sim.step(godfield_core.ActionType.ACTION_PRAY)

    assert sim.state.get_guardian(0) == 0
    assert sim.state.get_guardian(1) == 0


def test_moon_song():
    """月神: 歌声 (お祓い)"""
    song_id = find_card_by_name("miracles/song")
    seed = find_seed_for_moon_miracle(song_id)
    sim = SimulationRunner()
    sim.state.seed_rng(seed)
    sim.set_status(player=0, hp=99)
    sim.set_status(player=1, hp=99)
    sim.state.set_sickness(1, godfield_core.SicknessType.SICKNESS_COLD)
    sim.state.set_guardian(1, 10)
    sim.step(godfield_core.ActionType.ACTION_PRAY)

    assert sim.state.get_sickness(1) == godfield_core.SicknessType.SICKNESS_NONE


def test_moon_attack_miracles():
    """月神: 通常攻撃奇跡"""
    seed = find_seed_for_moon_miracle(999)
    sim = SimulationRunner()
    sim.state.seed_rng(seed)
    sim.set_status(player=0, hp=99)
    sim.set_status(player=1, hp=40)
    sim.state.set_guardian(1, 10)
    sim.step(godfield_core.ActionType.ACTION_PRAY)

    assert sim.state.current_phase == godfield_core.GamePhase.PHASE_MIRACLE_DEFENSE
    assert sim.state.defender_id == 0
    assert sim.state.attacker_id == 1
    assert sim.state.pending_attack_power > 0
    assert sim.state.pending_attack_source_id in range(100, 270)
