"""イベントログが、見ている人の視点で一貫していること。

以前は行為者を席0固定で「自分」と呼んでいたため、プレイヤー1の視点では
自分の行動が「敵」と表示されていた（対象側は player_id を見ていたので、
1行の中で基準が食い違っていた）。さらに「敵 自分へ 【回復】 を使った」は
『敵が敵自身に』とも『敵が私に』とも読めた。
"""

import pytest

from visualizer.event_formatter import OPPONENT_NAME, VIEWER_NAME, format_event_log

USE_CARD = 3          # EventType::USE_CARD
GUARDIAN_ENTER = 25
SMILE_DEW = 188       # スマイルのしずく（+HP5）


class Event:
    """C++ の GameEvent のうち、書式化に使う項目だけを持つ代役。"""

    def __init__(self, event_type, actor, target_id=-1, card_id=-1, value=0.0):
        self.event_type = event_type
        self.actor = actor
        self.target_id = target_id
        self.card_id = card_id
        self.value = value


def line(event, viewer) -> str:
    """画面に出る1行だけを取り出します（戻り値は付随情報を含む dict）。"""
    return format_event_log(event, viewer)["text"]


@pytest.mark.parametrize("viewer", [0, 1])
def test_actor_is_named_from_the_viewers_seat(viewer):
    """どちらの席から見ても、行動した本人が「あなた」になる。"""
    mine = line(Event(USE_CARD, actor=viewer, target_id=viewer, card_id=SMILE_DEW), viewer)
    theirs = line(Event(USE_CARD, actor=1 - viewer, target_id=1 - viewer, card_id=SMILE_DEW), viewer)

    assert mine.startswith(VIEWER_NAME)
    assert theirs.startswith(OPPONENT_NAME)


@pytest.mark.parametrize("viewer", [0, 1])
def test_self_targeting_names_the_actor_instead_of_saying_jibun(viewer):
    """行為者が自分自身を対象にした行は、誰のことか一意に読めること。"""
    opponent_on_self = line(Event(USE_CARD, actor=1 - viewer, target_id=1 - viewer, card_id=SMILE_DEW), viewer)

    assert opponent_on_self == f"{OPPONENT_NAME} が {OPPONENT_NAME}自身 に 【スマイルのしずく】 を使った"
    # 「自分」は閲覧者を指すのか行為者を指すのかが読めないので使わない
    assert "自分へ" not in opponent_on_self


@pytest.mark.parametrize("viewer", [0, 1])
def test_opponent_targeting_the_viewer_is_unambiguous(viewer):
    """相手が「あなた」に使った行が、自傷と混ざらないこと。"""
    text = line(Event(USE_CARD, actor=1 - viewer, target_id=viewer, card_id=SMILE_DEW), viewer)

    assert text == f"{OPPONENT_NAME} が {VIEWER_NAME} に 【スマイルのしずく】 を使った"


@pytest.mark.parametrize("viewer", [0, 1])
def test_the_two_directions_never_render_the_same(viewer):
    """『相手が自分自身に』と『相手があなたに』が別の文言になること。"""
    on_self = line(Event(USE_CARD, actor=1 - viewer, target_id=1 - viewer, card_id=SMILE_DEW), viewer)
    on_viewer = line(Event(USE_CARD, actor=1 - viewer, target_id=viewer, card_id=SMILE_DEW), viewer)

    assert on_self != on_viewer


@pytest.mark.parametrize("viewer", [0, 1])
def test_seat_numbers_are_never_shown(viewer):
    """席番号は出さない（どちらが自分かの手掛かりにならないため）。"""
    for actor in (0, 1):
        text = line(Event(GUARDIAN_ENTER, actor=actor, target_id=actor, value=3.0), viewer)
        assert "プレイヤー" not in text
        assert "0" not in text.replace("HP0", "")


@pytest.mark.parametrize("viewer", [0, 1])
def test_particle_reads_naturally_after_the_name(viewer):
    """『あなた に守護神が宿った！』のように助詞が続く行が壊れないこと。"""
    text = line(Event(GUARDIAN_ENTER, actor=viewer, target_id=viewer, value=3.0), viewer)
    assert text.startswith(f"{VIEWER_NAME} に守護神")


def test_unknown_event_type_is_skipped():
    assert format_event_log(Event(0, actor=0), 0) is None
