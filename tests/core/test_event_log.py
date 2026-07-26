import pytest
import godfield_core
from godfield_core import GamePhase, Element, ActionType, EventType
from tests.core.test_utils import SimulationRunner, find_card_by_name
from visualize_server import format_event_log

def test_guardian_event_logging():
    """守護神の行動発動時に EFFECT_GUARDIAN イベントが記録され、正確にフォーマットされるかテスト"""
    found_guardian_event = False
    for seed in range(50):
        sim_test = SimulationRunner()
        sim_test.state.seed_rng(seed)
        sim_test.set_hand(0, [115]) # 革の服
        sim_test.set_status(0, hp=40, mp=50, money=99)
        sim_test.set_status(1, hp=40, mp=50, money=99)
        sim_test.state.set_guardian(1, 1) # 火星神 (Mars = 1)
        
        # 祈る
        sim_test.step(ActionType.ACTION_PRAY)
        
        # 履歴チェック
        obs = godfield_core.get_observation(sim_test.state, 0)
        for ev in obs.get_history():
            if ev.event_type == int(EventType.EFFECT_GUARDIAN):
                found_guardian_event = True
                fmt = format_event_log(ev, 0)
                assert fmt is not None
                assert "火星神" in fmt["text"]
                assert "発動" in fmt["text"] or "行動" in fmt["text"]
                break
        if found_guardian_event:
            break
            
    assert found_guardian_event, "守護神の EFFECT_GUARDIAN イベントが記録されるべきです"

def test_discard_phase_event_logging():
    """「捨てる」アクション時の【置いた 捨てる】➔【置いた 革の服】➔【革の服 を捨てた】の統一フロー検証"""
    sim = SimulationRunner()
    sim.set_status(0, hp=40, mp=50, money=99)
    # P0の手札に ID 115 (革の服 - 捨てられるカード) をセット
    sim.set_hand(0, [115])
    sim.state.current_phase = GamePhase.PHASE_MAIN
    sim.state.current_actor_id = 0
    
    # 1. メインフェイズで ACTION_DISCARD を選択
    sim.step(ActionType.ACTION_DISCARD)
    assert sim.state.current_phase == GamePhase.PHASE_DISCARD
    obs_discard_action = godfield_core.get_observation(sim.state, 0)
    stage_events = [ev for ev in obs_discard_action.get_history() if ev.event_type == int(EventType.STAGE_CARD)]
    assert len(stage_events) > 0
    assert stage_events[-1].card_id == -1
    fmt_discard_stage = format_event_log(stage_events[-1], 0)
    assert "置いた 【捨てる】" in fmt_discard_stage["text"]
    
    # 2. 手札0番目 (ID 115) を仮置き
    sim.step(ActionType.ACTION_SELECT_HAND_0)
    obs_stage = godfield_core.get_observation(sim.state, 0)
    stage_events = [ev for ev in obs_stage.get_history() if ev.event_type == int(EventType.STAGE_CARD)]
    assert stage_events[-1].card_id == 115
    fmt_card_stage = format_event_log(stage_events[-1], 0)
    assert "置いた 【革の服】" in fmt_card_stage["text"]
    
    # 3. ACTION_CONFIRM で捨てるのを確定
    sim.step(ActionType.ACTION_CONFIRM)
    
    # DISCARD_CARD イベントが記録されたかチェック
    obs = godfield_core.get_observation(sim.state, 0)
    discard_events = [ev for ev in obs.get_history() if ev.event_type == int(EventType.DISCARD_CARD)]
    assert len(discard_events) > 0
    assert discard_events[-1].card_id == 115
    fmt = format_event_log(discard_events[-1], 0)
    assert fmt is not None
    assert "革の服" in fmt["text"]
    assert "捨てた" in fmt["text"]

def test_guardian_summon_and_leave_events():
    """守護の壺使用時の GUARDIAN_ENTER、解放使用時の GUARDIAN_LEAVE イベントの検証"""
    sim = SimulationRunner()
    pot_id = find_card_by_name('sundries/guardian-pot')
    release_id = find_card_by_name('miracles/release')
    
    sim.state.current_phase = GamePhase.PHASE_MAIN
    sim.state.current_actor_id = 0
    sim.state.set_mp(0, 50)
    
    # 守護の壺を使用
    sim.set_hand(0, [pot_id])
    sim.perform_attack([0], to_self=True)
    sim.step(ActionType.ACTION_CONFIRM)
    
    # 守護神が降臨していること
    assert sim.state.get_guardian(0) > 0
    
    # イベントログから GUARDIAN_ENTER が検出できること
    obs = godfield_core.get_observation(sim.state, 0)
    enter_events = [ev for ev in obs.get_history() if ev.event_type == int(EventType.GUARDIAN_ENTER)]
    assert len(enter_events) > 0
    assert enter_events[-1].value == sim.state.get_guardian(0)
    fmt_enter = format_event_log(enter_events[-1], 0)
    assert "宿った！" in fmt_enter["text"]
    
    # 解放を使用
    sim.state.current_phase = GamePhase.PHASE_MAIN
    sim.state.current_actor_id = 0
    sim.set_hand(0, [release_id])
    sim.perform_attack([0], to_self=True)
    sim.step(ActionType.ACTION_CONFIRM)
    
    # 守護神が消滅していること
    assert sim.state.get_guardian(0) == 0
    
    # イベントログから GUARDIAN_LEAVE が検出できること
    obs = godfield_core.get_observation(sim.state, 0)
    leave_events = [ev for ev in obs.get_history() if ev.event_type == int(EventType.GUARDIAN_LEAVE)]
    assert len(leave_events) > 0
    fmt_leave = format_event_log(leave_events[-1], 0)
    assert "帰っていった" in fmt_leave["text"]

def test_curse_events():
    """霧の奇跡使用時の EFFECT_CURSE イベント（付与・解除）の検証"""
    sim = SimulationRunner()
    fog_miracle = find_card_by_name('miracles/fog')
    song_miracle = find_card_by_name('miracles/song')
    
    sim.state.current_phase = GamePhase.PHASE_MAIN
    sim.state.current_actor_id = 0
    sim.state.set_mp(0, 50)
    
    # 霧の奇跡を相手に使用
    sim.set_hand(0, [fog_miracle])
    sim.perform_attack([0])
    sim.step(ActionType.ACTION_CONFIRM)
    
    # 相手が霧状態になっていること
    assert sim.state.get_curses(1, godfield_core.CurseType.CURSE_FOG) == True
    
    # イベントログから EFFECT_CURSE (付与) が検出できること
    obs = godfield_core.get_observation(sim.state, 0)
    curse_events = [ev for ev in obs.get_history() if ev.event_type == int(EventType.EFFECT_CURSE)]
    assert len(curse_events) > 0
    val = int(curse_events[-1].value)
    assert (val & 0x0F) == int(godfield_core.CurseEvent.TYPE_FOG)
    assert bool(val & int(godfield_core.CurseEvent.FLAG_APPLIED)) == True
    
    fmt_applied = format_event_log(curse_events[-1], 0)
    assert "霧" in fmt_applied["text"]
    assert "状態になった" in fmt_applied["text"]
    
    # 相手のターン。歌声を使用して解除
    sim.state.current_phase = GamePhase.PHASE_MAIN
    sim.state.current_actor_id = 1
    sim.state.set_mp(1, 50)
    sim.set_hand(1, [song_miracle])
    sim.perform_attack([0], to_self=True)
    sim.step(ActionType.ACTION_CONFIRM)
    
    # 相手の霧状態が解除されていること
    assert sim.state.get_curses(1, godfield_core.CurseType.CURSE_FOG) == False
    
    # イベントログから EFFECT_CURSE (解除) が検出できること
    obs = godfield_core.get_observation(sim.state, 0)
    curse_events = [ev for ev in obs.get_history() if ev.event_type == int(EventType.EFFECT_CURSE)]
    assert len(curse_events) > 0
    val = int(curse_events[-1].value)
    assert (val & 0x0F) == int(godfield_core.CurseEvent.TYPE_FOG)
    assert bool(val & int(godfield_core.CurseEvent.FLAG_CLEARED)) == True
    
    fmt_cleared = format_event_log(curse_events[-1], 0)
    assert "霧" in fmt_cleared["text"]
    assert "回復した" in fmt_cleared["text"]


def test_ascension_bow_event_logging():
    """昇天弓発動（確定）および命中失敗（ミス）イベントが正しくログに記録・フォーマットされるかテスト"""
    # 1. 昇天弓が発動してキューに登録される（CONFIRM_ATTACK）の検証
    sim = SimulationRunner()
    sim.set_status(0, hp=1, mp=10)
    sim.set_status(1, hp=40, mp=10)
    
    # P0の手札に昇天弓（ID 109）をセット
    sim.state.set_true_hand(0, 0, 109)
    sim.state.set_apparent_hand(0, 0, 109)
    
    # P1のメインフェイズから木剣で攻撃
    sim.state.current_phase = GamePhase.PHASE_MAIN
    sim.state.current_actor_id = 1
    wood_sword_id = find_card_by_name("weapons/wooden-sword") # 威力3
    sim.state.set_true_hand(1, 0, wood_sword_id)
    sim.state.set_apparent_hand(1, 0, wood_sword_id)
    
    # P1攻撃
    sim.perform_attack([0])
    
    # P0防御フェイズ、スルーして死亡
    sim.step(ActionType.ACTION_CONFIRM) # スルー (CONFIRM)
    
    # P0が死亡したため昇天弓がキューに入る。
    # 履歴を走査して 昇天弓の使用（CONFIRM_ATTACK）が記録されているか検証
    obs = godfield_core.get_observation(sim.state, 0)
    history = obs.get_history()
    
    confirm_bow_events = [ev for ev in history if ev.event_type == int(EventType.CONFIRM_ATTACK) and ev.card_id == 109]
    assert len(confirm_bow_events) > 0, "昇天弓の使用イベントが記録されているはずです"
    
    fmt = format_event_log(confirm_bow_events[0], 0)
    assert "昇天弓" in fmt["text"]
    assert "使った" in fmt["text"]

    # 2. 昇天弓が「命中失敗（ミス）」した場合のログフォーマット検証
    # ミスが発生するまでランダムなシードで試行
    found_miss = False
    for seed in range(100):
        sim_miss = SimulationRunner()
        sim_miss.state.seed_rng(seed)
        sim_miss.set_status(0, hp=1, mp=10)
        sim_miss.set_status(1, hp=40, mp=10)
        sim_miss.state.set_true_hand(0, 0, 109)
        sim_miss.state.set_apparent_hand(0, 0, 109)
        
        sim_miss.state.current_phase = GamePhase.PHASE_MAIN
        sim_miss.state.current_actor_id = 1
        sim_miss.state.set_true_hand(1, 0, wood_sword_id)
        sim_miss.state.set_apparent_hand(1, 0, wood_sword_id)
        
        sim_miss.perform_attack([0])
        sim_miss.step(ActionType.ACTION_CONFIRM)
        
        # 履歴を取得してミスイベントを探す
        obs_miss = godfield_core.get_observation(sim_miss.state, 0)
        miss_events = [ev for ev in obs_miss.get_history() if ev.event_type == int(EventType.ATTACK_MISS) and ev.card_id == 109]
        if len(miss_events) > 0:
            found_miss = True
            fmt_miss = format_event_log(miss_events[0], 0)
            assert "昇天弓" in fmt_miss["text"]
            assert "命中失敗" in fmt_miss["text"] or "ミス" in fmt_miss["text"]
            break
            
    assert found_miss, "昇天弓が命中失敗したイベントがテスト中に検出されるはずです"

