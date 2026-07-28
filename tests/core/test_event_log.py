"""イベント履歴の記録内容と、可視化ツール向けの整形結果の検証。

【移行メモ】
従来は守護神が行動する25%や昇天弓の命中を、それぞれ50・100回のシード探索で
引き当てていました。また `sim.set_hand(0, [115])` のようにカードIDが数値で
直書きされていました（115 は革の服）。判定は直接指示し、カードは名前で指定します。
"""

import pytest

import godfield_core
from godfield_core import CurseEvent, EventType, GamePhase, GuardianType
from tests.core.dsl import Side, card_id, card_name, ev
from visualizer.event_formatter import format_event_log

FILLER = "armor/wood-shield"
DISCARDABLE = "armor/leather-clothes"


def events_of(game, event_type: EventType):
    """指定した種別のイベントを、観測の履歴から時系列順に取り出します。"""
    obs = godfield_core.get_observation(game.state, 0)
    return [e for e in obs.get_history() if e.event_type == int(event_type)]


def test_guardian_action_is_logged_and_formatted(board):
    """守護神の行動が EFFECT_GUARDIAN として記録され、守護神名を含む文言に整形されることを検証します。

    従来は守護神が行動する25%を引くまで最大50シードを試していました。
    """
    g = board(
        p0=Side(hp=40, mp=50, money=99, hand=[DISCARDABLE]),
        p1=Side(hp=40, mp=50, money=99, guardian=int(GuardianType.MARS)),
    )
    g.rng.deck_always(FILLER)
    g.rng.guardian_action_card(int(GuardianType.MARS), "gurdians/fire-shout")
    g.rng.hits(always=True)

    g.pray()

    guardian_events = events_of(g, EventType.EFFECT_GUARDIAN)
    assert guardian_events, "守護神の EFFECT_GUARDIAN イベントが記録されるべきです"

    fmt = format_event_log(guardian_events[-1], 0)
    assert fmt is not None
    assert "火星神" in fmt["text"]
    assert "発動" in fmt["text"] or "行動" in fmt["text"]


def test_discard_flow_logs_stage_then_discard(board):
    """「捨てる」の一連の流れが【置いた 捨てる】→【置いた カード名】→【捨てた】と記録されることを検証します。"""
    g = board(p0=Side(hp=40, mp=50, money=99, hand=[DISCARDABLE]), p1=Side(hp=40))
    g.rng.deck_always(FILLER)

    # 1. 「捨てる」自体を置く（カードIDなし）
    g.step(godfield_core.ActionType.ACTION_DISCARD)
    g.expect(phase=GamePhase.PHASE_DISCARD)

    stage_events = events_of(g, EventType.STAGE_CARD)
    assert stage_events, "「捨てる」を置いたイベントが記録されるべきです"
    assert stage_events[-1].card_id == -1
    assert "置いた 【捨てる】" in format_event_log(stage_events[-1], 0)["text"]

    # 2. 捨てるカードを置く
    g.select(DISCARDABLE)
    stage_events = events_of(g, EventType.STAGE_CARD)
    assert stage_events[-1].card_id == card_id(DISCARDABLE)
    assert f"置いた 【{card_name(card_id(DISCARDABLE))}】" in (
        format_event_log(stage_events[-1], 0)["text"]
    )

    # 3. 確定
    g.confirm()
    discard_events = events_of(g, EventType.DISCARD_CARD)
    assert discard_events, "捨てたイベントが記録されるべきです"
    assert discard_events[-1].card_id == card_id(DISCARDABLE)

    text = format_event_log(discard_events[-1], 0)["text"]
    assert card_name(card_id(DISCARDABLE)) in text
    assert "捨てた" in text


def test_guardian_enter_and_leave_events(board):
    """守護神の降臨（守護封印のつぼ）と退散（＜解放＞）がイベントに記録されることを検証します。"""
    summoned = int(GuardianType.SATURN)
    g = board(p0=Side(hp=40, mp=50, hand=["sundries/guardian-pot"]), p1=Side(hp=40))
    g.rng.deck_always(FILLER)
    g.rng.guardian_pot(summoned)

    g.attack("sundries/guardian-pot", to_self=True)
    g.confirm()

    g.expect(p0_guardian=summoned)
    enter_events = events_of(g, EventType.GUARDIAN_ENTER)
    assert enter_events
    assert enter_events[-1].value == summoned
    assert "宿った！" in format_event_log(enter_events[-1], 0)["text"]

    # ＜解放＞で両者の守護神を解除する
    g.state.current_phase = GamePhase.PHASE_MAIN
    g.state.current_actor_id = 0
    g.state.set_true_hand(0, 0, card_id("miracles/release"))
    for i in range(1, 18):
        g.state.set_true_hand(0, i, godfield_core.CARD_EMPTY)

    g.attack("miracles/release", to_self=True)
    g.confirm()

    g.expect(p0_guardian=0)
    leave_events = events_of(g, EventType.GUARDIAN_LEAVE)
    assert leave_events
    assert "帰っていった" in format_event_log(leave_events[-1], 0)["text"]


def test_curse_applied_and_cleared_events(board):
    """災いの付与と解除が EFFECT_CURSE のビットフラグで記録されることを検証します。"""
    g = board(
        p0=Side(hp=40, mp=50, hand=["miracles/fog"]),
        p1=Side(hp=40, mp=50, hand=["miracles/song"]),
    )
    g.rng.deck_always(FILLER)

    # 霧の奇跡を相手に使う
    g.attack("miracles/fog")
    g.confirm()

    g.expect(p1_curses={godfield_core.CurseType.CURSE_FOG})
    applied = events_of(g, EventType.EFFECT_CURSE)[-1]
    assert (int(applied.value) & CurseEvent.MASK_TYPE) == int(CurseEvent.TYPE_FOG)
    assert int(applied.value) & int(CurseEvent.FLAG_APPLIED)

    text = format_event_log(applied, 0)["text"]
    assert "霧" in text and "状態になった" in text

    # 相手が＜歌声＞で自分の霧を解除する
    g.state.current_phase = GamePhase.PHASE_MAIN
    g.state.current_actor_id = 1
    g.attack("miracles/song", to_self=True)
    g.confirm()

    g.expect(p1_curses=set())
    cleared = events_of(g, EventType.EFFECT_CURSE)[-1]
    assert (int(cleared.value) & CurseEvent.MASK_TYPE) == int(CurseEvent.TYPE_FOG)
    assert int(cleared.value) & int(CurseEvent.FLAG_CLEARED)

    text = format_event_log(cleared, 0)["text"]
    assert "霧" in text and "回復した" in text


@pytest.mark.parametrize(
    ("card", "sickness"),
    [
        ("miracles/tone", godfield_core.SicknessType.SICKNESS_COLD),
        ("miracles/tone", godfield_core.SicknessType.SICKNESS_FEVER),
        ("miracles/song", godfield_core.SicknessType.SICKNESS_HELL),
        ("sundries/heart-shell", godfield_core.SicknessType.SICKNESS_HEAVEN),
    ],
    ids=["音色で風邪", "音色で熱病", "歌で地獄病", "ハートの貝がらで天国病"],
)
def test_sickness_cured_event(board, card, sickness):
    """病気の治癒が EFFECT_SICKNESS の FLAG_CURED として記録されることを検証します。

    以前は治癒だけが state.sickness への直接代入で、イベントが一切出ていませんでした。
    呪いは remove_curse() が FLAG_CLEARED を出しているのに対して非対称だったため、
    履歴からは「相手の病気が治った」ことが読み取れませんでした。

    `value` の下位4ビットには「治る前の病気」が入ります。何が治ったのか分からないと
    履歴として意味がないためです。
    """
    g = board(
        p0=Side(hp=40, mp=50, sickness=sickness, hand=[card]),
        p1=Side(hp=40, mp=50),
    )
    g.rng.deck_always(FILLER)

    g.attack(card, to_self=True)
    g.confirm()

    g.expect(p0_sickness=godfield_core.SicknessType.SICKNESS_NONE)

    cured = events_of(g, EventType.EFFECT_SICKNESS)[-1]
    assert int(cured.value) & int(godfield_core.SicknessEvent.FLAG_CURED), (
        f"治癒が FLAG_CURED として記録されるべきです: value={int(cured.value)}"
    )
    assert (int(cured.value) & godfield_core.SicknessEvent.MASK_TYPE) == int(sickness), (
        "治る前の病気の種別が記録されるべきです"
    )

    text = format_event_log(cured, 0)["text"]
    assert "治った" in text


def test_darkness_instant_death_is_logged_and_formatted(board):
    """闇属性の即死が INSTANT_DEATH として記録され、専用の文言に整形されることを検証します。"""
    g = board(
        p0=Side(hp=99, mp=99, hand=["miracles/darkness"]),
        p1=Side(hp=99, mp=10, hand=[FILLER]),
    )
    g.rng.deck_always(FILLER)

    g.attack("miracles/darkness")
    g.take_hit()

    deaths = events_of(g, EventType.INSTANT_DEATH)
    assert deaths
    text = format_event_log(deaths[-1], 0)["text"]
    assert "即死" in text


def test_healthy_player_produces_no_cure_event(board):
    """病気でないプレイヤーを治療しても、治癒イベントが出ないことを検証します。

    呪いの apply_curse() / remove_curse() と同じく、状態が変わらないときは
    イベントを出しません。これがないと上のテストは「常にイベントが出る」だけを
    見ていることになります。
    """
    g = board(
        p0=Side(hp=40, mp=50, hand=["miracles/song"]),
        p1=Side(hp=40, mp=50),
    )
    g.rng.deck_always(FILLER)

    g.attack("miracles/song", to_self=True)
    g.confirm()

    assert not events_of(g, EventType.EFFECT_SICKNESS)


def test_ascension_bow_use_is_logged(board):
    """昇天弓が起動した際に CONFIRM_ATTACK として記録されることを検証します。"""
    bow = "weapons/ascension-bow"
    g = board(
        p0=Side(hp=1, mp=10, hand=[bow]),
        p1=Side(hp=40, mp=10, hand=["weapons/wooden-sword"]),
        actor=1,
    )
    g.rng.deck_always(FILLER)
    g.rng.ascension_bow(True)

    g.attack("weapons/wooden-sword")
    g.take_hit()  # P0 が被弾して死亡し、昇天弓が起動する

    confirm_events = [
        e for e in events_of(g, EventType.CONFIRM_ATTACK) if e.card_id == card_id(bow)
    ]
    assert confirm_events, "昇天弓の使用イベントが記録されるべきです"

    text = format_event_log(confirm_events[0], 0)["text"]
    assert "昇天弓" in text and "使った" in text


def test_ascension_bow_miss_is_logged(board):
    """昇天弓が命中失敗した際に ATTACK_MISS として記録されることを検証します。

    従来はミスが出るまで最大100シードを試していました。
    """
    bow = "weapons/ascension-bow"
    g = board(
        p0=Side(hp=1, mp=10, hand=[bow]),
        p1=Side(hp=40, mp=10, hand=["weapons/wooden-sword"]),
        actor=1,
    )
    g.rng.deck_always(FILLER)
    g.rng.ascension_bow(False)

    g.attack("weapons/wooden-sword")
    g.take_hit()

    miss_events = [
        e for e in events_of(g, EventType.ATTACK_MISS) if e.card_id == card_id(bow)
    ]
    assert miss_events, "昇天弓の命中失敗イベントが記録されるべきです"

    text = format_event_log(miss_events[0], 0)["text"]
    assert "昇天弓" in text
    assert "命中失敗" in text or "ミス" in text


def event_sequence(game):
    """発生したイベント種別を時系列順の名前リストで返します。"""
    return [e.type.name for e in game.event_log()]


def test_plain_attack_emits_no_attack_hit_event(board):
    """命中率100%の単体攻撃では ATTACK_HIT が発行されないことを検証します。

    ATTACK_HIT / ATTACK_MISS は「命中判定が実際に行われた攻撃」でのみ配信される
    仕様です（docs/event_log_spec.md 参照）。当たることが確定している攻撃では
    「当たった」を伝える必要がないため配信されません。被弾量は TAKE_DAMAGE で
    配信されるので、ダメージ表示には影響しません。

    イベント列を完全一致で固定することで、余計なイベントが増えた場合にも気付けます。
    """
    g = board(p0=Side(hp=40, mp=50, hand=["weapons/punch"]), p1=Side(hp=40, hand=[FILLER]))
    g.rng.deck_always(FILLER)
    g.attack("weapons/punch")
    g.take_hit()

    assert event_sequence(g) == [
        "STAGE_CARD", "CONFIRM_ATTACK", "CONFIRM_DEFENSE", "TAKE_DAMAGE",
    ]


@pytest.mark.parametrize("hits", [True, False], ids=["命中", "ミス"])
def test_accuracy_checked_attack_emits_hit_or_miss(board, hits):
    """命中判定を伴う攻撃では ATTACK_HIT / ATTACK_MISS が発行されることを検証します。"""
    g = board(
        p0=Side(hp=40, mp=50, hand=["weapons/vine-shoot"]),
        p1=Side(hp=40, hand=[FILLER]),
    )
    g.rng.deck_always(FILLER)
    g.rng.hits(always=hits)
    g.attack("weapons/vine-shoot")
    if hits:
        g.take_hit()

    if hits:
        assert event_sequence(g) == [
            "STAGE_CARD", "CONFIRM_ATTACK", "ATTACK_HIT", "CONFIRM_DEFENSE", "TAKE_DAMAGE",
        ]
    else:
        assert event_sequence(g) == ["STAGE_CARD", "CONFIRM_ATTACK", "ATTACK_MISS"]


@pytest.mark.parametrize(
    "card",
    ["weapons/spark-bag", "miracles/smoke"],
    ids=["全体武器", "全体奇跡"],
)
def test_group_attack_emits_attack_hit(board, card):
    """全体攻撃では武器・奇跡ともに ATTACK_HIT が発行されることを検証します。"""
    g = board(p0=Side(hp=40, mp=50, hand=[card]), p1=Side(hp=40, hand=[FILLER]))
    g.rng.deck_always(FILLER)
    g.attack(card)
    g.take_hit()

    assert "ATTACK_HIT" in event_sequence(g)


@pytest.mark.parametrize(
    "event_type",
    [
        EventType.STAGE_CARD,
        EventType.CONFIRM_ATTACK,
        EventType.CONFIRM_DEFENSE,
        EventType.TAKE_DAMAGE,
    ],
)
def test_common_combat_events_are_formattable(board, event_type):
    """通常の戦闘で発生する主要イベントが、すべて整形可能であることを検証します。

    整形器が未知のイベント種別で None を返したり例外を投げたりすると、
    可視化ツールがそのイベントだけ黙って表示しなくなります。
    """
    g = board(p0=Side(hp=40, hand=["weapons/punch"]), p1=Side(hp=40, hand=[FILLER]))
    g.rng.deck_always(FILLER)
    g.attack("weapons/punch")
    g.take_hit()

    found = events_of(g, event_type)
    assert found, f"{event_type.name} が発生するべき局面です"
    for e in found:
        fmt = format_event_log(e, 0)
        assert fmt is not None and fmt.get("text"), f"{event_type.name} の整形に失敗しました"


@pytest.mark.parametrize(
    ("phase_name", "first", "extra"),
    [
        ("攻撃プラス", "weapons/punch", "weapons/blowgun"),
        ("奇跡プラス", "miracles/fireball", "sundries/spiritual-doll"),
    ],
)
def test_every_staging_phase_logs_the_card_it_stages(board, phase_name, first, extra):
    """カードを重ねる操作が、どのフェイズでも STAGE_CARD として履歴に残ることを検証します。

    以前は奇跡プラスだけが STAGE_CARD を発行しておらず、精霊系カードを重ねて
    消費MPを0にする操作が履歴に残りませんでした。履歴は観測に含まれるため、
    エージェントからはその操作だけが見えない状態でした。

    仮置きフェイズは6つあり、他の5つは発行していたので、抜けと判断しています。
    """
    g = board(
        p0=Side(hp=40, mp=20, hand=[first, extra]),
        p1=Side(hp=40, mp=20),
    )
    g.rng.deck_always("armor/wood-shield")

    g.select(first)
    g.select(extra)

    g.expect_events(
        ev(EventType.STAGE_CARD, card=first),
        ev(EventType.STAGE_CARD, card=extra),
    )
