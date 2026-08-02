"""手札枚数と公開状態が、観測に正しく入っていること。

これらが無かったせいで、方策は「無料で相手の手札を1枚奪える」「防具を捨てると
手札が減る」「買うを自分に使うと自分のカードが公開される」を一切認識できず、
どれも 50% 前後のコイントスになっていた。
"""

import godfield_core
from godfield_rl import feature_config as fc
from tests.core.dsl import Game, Side

ME, OPP = 0, 1
MAX_HAND = godfield_core.MAX_HAND_SIZE
FOG = godfield_core.CurseType.CURSE_FOG


def observe(game: Game, player: int):
    return godfield_core.get_observation(game.state, player)


def count(normalized: float) -> int:
    """正規化された枚数を枚数に戻します（float32 なので丸めが要る）。"""
    return round(normalized * MAX_HAND)


def test_hand_counts_reflect_the_actual_number_of_cards():
    game = Game(
        p0=Side(hand=["パンチ", "アイアンアーマー", "＜氷＞"]),
        p1=Side(hand=["パンチ"] * 7),
    )
    obs = observe(game, ME)
    assert count(obs.hand_count_me) == 3
    assert count(obs.hand_count_opp) == 7


def test_hand_counts_are_mirrored_from_the_other_seat():
    game = Game(p0=Side(hand=["パンチ"] * 3), p1=Side(hand=["パンチ"] * 7))
    obs = observe(game, OPP)
    assert count(obs.hand_count_me) == 7
    assert count(obs.hand_count_opp) == 3


def test_opponent_hand_count_survives_fog():
    """霧は中身を隠すが枚数は隠さない（場に出ている枚数は数えられる）。"""
    game = Game(
        p0=Side(hand=["パンチ"], curses=[FOG]),
        p1=Side(hand=["パンチ"] * 5, known_to_opp=[0, 1]),
    )
    obs = observe(game, ME)
    assert count(obs.hand_count_opp) == 5
    # 中身のほうは隠れたまま（公開済みでも霧の下では見えない）
    assert all(v < 0 for v in obs.get_opponent_hand_cards())


def test_own_revealed_cards_are_flagged_in_slot_order():
    """自分の手札は並べ替えないので、フラグはスロット添字で対応する。"""
    game = Game(p0=Side(hand=["パンチ", "アイアンアーマー", "＜氷＞"], known_to_opp=[1]))
    obs = observe(game, ME)
    flags = obs.get_hand_known_to_opp()
    assert flags[0] == 0.0
    assert flags[1] == 1.0, "公開済みのスロットが立っていない"
    assert flags[2] == 0.0


def test_empty_slots_are_not_flagged_as_revealed():
    game = Game(p0=Side(hand=["パンチ"]))
    obs = observe(game, ME)
    assert all(v == 0.0 for v in obs.get_hand_known_to_opp()[1:])


def test_opponent_deployed_flag_follows_the_packed_order():
    """相手側は左詰めするので、フラグも詰めた後の位置に合わせる。

    元のスロット番号で持つと、左詰めにした意味（位置のリーク防止）が失われる。
    """
    game = Game(
        p0=Side(),
        # スロット3だけ展開済み、スロット1は公開済み。詰めると [1, 3] の順に並ぶ
        p1=Side(hand=["パンチ", "＜氷＞", "アイアンアーマー", "＜炎＞"],
                deployed=[3], known_to_opp=[1]),
    )
    obs = observe(game, ME)
    shown = [c for c in obs.get_opponent_hand_cards() if c >= 0]
    assert len(shown) == 2, f"見えるのは2枚のはず: {shown}"
    flags = obs.get_opponent_deployed()
    assert flags[0] == 0.0, "公開済みなだけのカードに展開フラグが立っている"
    assert flags[1] == 1.0, "展開済みのカードにフラグが立っていない"
    assert all(v == 0.0 for v in flags[2:])


def test_deployed_cards_stay_visible_under_fog():
    """霧でも展開済みの奇跡は見える（既存の仕様）。フラグも一緒に残ること。"""
    game = Game(
        p0=Side(curses=[FOG]),
        p1=Side(hand=["＜氷＞", "パンチ"], deployed=[0], known_to_opp=[1]),
    )
    obs = observe(game, ME)
    assert obs.get_opponent_deployed()[0] == 1.0
    # 公開されただけのカードは霧で隠れるので、残るのは展開済みの1枚だけ
    assert sum(1 for c in obs.get_opponent_hand_cards() if c >= 0) == 1


def test_layout_offsets_point_at_the_same_values():
    """feature_config のオフセットが C++ の構造体と一致していること。"""
    game = Game(
        p0=Side(hand=["パンチ", "アイアンアーマー"], known_to_opp=[1]),
        p1=Side(hand=["パンチ"] * 4),
    )
    flat = godfield_core.get_observation(game.state, ME).to_numpy()
    assert count(flat[fc.HAND_COUNT_START]) == 2
    assert count(flat[fc.HAND_COUNT_START + 1]) == 4
    assert flat[fc.HAND_KNOWN_TO_OPP_START + 1] == 1.0
