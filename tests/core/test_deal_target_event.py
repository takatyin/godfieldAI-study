"""「買う」「売る」が、誰を対象にしたのかをイベントに残すこと。

他のカードは対象選択の時点で CONFIRM_ATTACK を発行しますが、売る・買うだけは
その手前で return しており、対象が履歴に残っていませんでした。とくに
「買うを自分に使う」経路は、手札が1枚相手に公開されるにもかかわらず
イベントを1件も出さないため、可視化のログが完全に空になっていました。
"""


from godfield_core import EventType
from tests.core.dsl import Game, Side, ev

ME, OPP = 0, 1


def test_buying_from_the_opponent_is_recorded():
    (
        Game(
            p0=Side(hand=["買う", "ハートのしずく"], money=50),
            p1=Side(hand=["アイアンアーマー", "ハートのしずく"], money=50),
        )
        .select("買う")
        .target_opp()
        .expect_events(ev(EventType.CONFIRM_ATTACK, card="買う", actor=ME, target=OPP))
    )


def test_selling_to_the_opponent_is_recorded():
    """売るは出品カードを仮置きしてから対象選択に進む。"""
    (
        Game(
            p0=Side(hand=["売る", "ハートのしずく"], money=50),
            p1=Side(hand=["アイアンアーマー"], money=50),
        )
        .select("売る", "ハートのしずく")
        .target_opp()
        .expect_events(ev(EventType.CONFIRM_ATTACK, card="売る", actor=ME, target=OPP))
    )


def test_buying_from_yourself_is_recorded():
    """自分に「買う」を使う経路は、以前はイベントを1件も出していなかった。"""
    (
        Game(
            p0=Side(hand=["買う", "ハートのしずく", "アイアンアーマー"], money=50),
            p1=Side(hand=["ハートのしずく"], money=50),
        )
        .select("買う")
        .target_self()
        .expect_events(ev(EventType.CONFIRM_ATTACK, card="買う", actor=ME, target=ME))
    )


def test_buying_from_yourself_reveals_exactly_one_card():
    """仕様どおり、自分の未展開・未使用の手札が1枚だけ相手に公開される。"""
    game = Game(
        p0=Side(hand=["買う", "ハートのしずく", "アイアンアーマー"], money=50),
        p1=Side(hand=["ハートのしずく"], money=50),
    )

    def revealed() -> int:
        state = game.state
        return sum(
            1 for i in range(len(game.hand(ME)) + 3)
            if state.get_true_hand(ME, i) >= 0 and state.get_is_known_to_opp(ME, i)
        )

    before = revealed()
    game.select("買う").target_self()
    assert revealed() - before == 1, "公開されるのは1枚だけのはず"
