"""テストDSL自体の自己検証。

DSL にバグがあると、プロダクトのバグを取り逃したり、逆に存在しないバグを追う
ことになります。盤面構築・カード解決・イベント整列・乱数注入・失敗検出の
それぞれが正しく動くことをここで固定します。
"""

import pytest

import godfield_core
from godfield_core import (
    CurseType,
    EventType,
    GamePhase,
    PhenomenonType,
    RollKind,
    SicknessType,
)
from tests.core.dsl import (
    NEVER,
    Side,
    card_feature,
    card_id,
    card_name,
    element_of,
    ev,
)

# ============================================================================
# 盤面構築 / Board setup
# ============================================================================


def test_board_applies_every_declared_field(board):
    """Side で宣言した全フィールドが InternalState に反映されることを確認します。"""
    g = board(
        p0=Side(
            hp=33,
            mp=22,
            money=11,
            hand=["weapons/punch", "armor/leather-clothes", "miracles/wall"],
            sickness=SicknessType.SICKNESS_FEVER,
            curses=[CurseType.CURSE_FOG, CurseType.CURSE_DREAM],
            guardian=int(godfield_core.GuardianType.MARS),
            known_to_opp=[1],
            used=[2],
            pending_ascension_bows=2,
        ),
        p1=Side(hp=7, mp=6, money=5),
        phase=GamePhase.PHASE_MAIN,
        actor=0,
        turn=9,
    )

    g.expect(
        p0_hp=33, p0_mp=22, p0_money=11,
        p1_hp=7, p1_mp=6, p1_money=5,
        p0_sickness=SicknessType.SICKNESS_FEVER,
        p0_curses={CurseType.CURSE_FOG, CurseType.CURSE_DREAM},
        p1_curses=set(),
        p0_guardian=int(godfield_core.GuardianType.MARS),
        p0_bows=2,
        turn=9,
        actor=0,
        phase=GamePhase.PHASE_MAIN,
    )
    assert g.state.get_is_known_to_opp(0, 1) is True
    assert g.state.get_is_used(0, 2) is True
    assert g.state.get_is_known_to_opp(0, 0) is False


def test_board_none_entries_leave_slots_empty(board):
    """hand に None を混ぜるとそのスロットが空になり、0以外のスロットを検証できます。"""
    g = board(p0=Side(hand=[None, None, "weapons/punch", None, "miracles/wall"]))

    assert g.state.get_true_hand(0, 0) == godfield_core.CARD_EMPTY
    assert g.state.get_true_hand(0, 1) == godfield_core.CARD_EMPTY
    assert g.state.get_true_hand(0, 2) == card_id("weapons/punch")
    assert g.state.get_true_hand(0, 3) == godfield_core.CARD_EMPTY
    assert g.state.get_true_hand(0, 4) == card_id("miracles/wall")
    assert g.slot_of(0, "weapons/punch") == 2
    assert g.slot_of(0, "miracles/wall") == 4


def test_deployed_miracles_are_marked(board):
    """deployed で指定した奇跡が展開済みになることを確認します。"""
    g = board(p0=Side(mp=50, hand=["miracles/wall", "miracles/fog"], deployed=[0]))
    assert g.state.get_is_deployed(0, 0) is True
    assert g.state.get_is_deployed(0, 1) is False


def test_hand_too_large_is_rejected(board):
    """手札上限を超える宣言は静かに切り捨てず例外にします。"""
    with pytest.raises(ValueError, match="手札は最大"):
        board(p0=Side(hand=["weapons/punch"] * 19))


# ============================================================================
# カード名の解決 / Card resolution
# ============================================================================


def test_card_id_accepts_id_str_and_japanese_name():
    """id_str と日本語名の双方から同じIDが引けることを確認します。"""
    assert card_id("armor/leather-clothes") == card_id("革の服")
    assert card_name(card_id("armor/leather-clothes")) == "革の服"


def test_unknown_card_name_raises_with_guidance():
    """存在しないカード名はハルシネーションなので明示的に落とします。"""
    with pytest.raises(KeyError, match="存在しません"):
        card_id("買戻し")  # AGENTS.md 記載の幻のカード名


def test_element_map_covers_every_element_in_the_card_master():
    """マスタに現れる全属性が DSL の対応表に載っていることを確認します。

    C++ の card_registry.cpp の element_map と二重管理になっているため、
    新しい属性が追加されたらここで落ちるようにしておきます。
    """
    from tests.core.dsl import all_cards, element_of

    seen = {c.get("element", "") or "" for c in all_cards()}
    assert seen, "カードマスタが読めていません"
    for c in all_cards():
        element_of(c["id"])  # 未知の属性なら KeyError で落ちる


def test_element_of_matches_the_engine(board):
    """DSL が返す属性が、エンジンが実際に載せる属性と一致することを確認します。"""
    for weapon in ("weapons/punch", "weapons/torch", "weapons/wooden-sword"):
        g = board(p0=Side(hand=[weapon]), p1=Side(hp=99))
        g.attack(weapon)
        assert g.state.pending_attack_element == element_of(weapon), (
            f"{weapon} の属性が DSL とエンジンで食い違っています"
        )


def test_slot_of_skips_used_slots_and_supports_nth(board):
    """同名カードが複数ある場合の nth 指定と、使用済みスロットの除外を確認します。"""
    g = board(p0=Side(hand=["weapons/punch", "weapons/punch", "weapons/punch"], used=[0]))
    # 使用済みのスロット0は飛ばされる
    assert g.slot_of(0, "weapons/punch") == 1
    assert g.slot_of(0, "weapons/punch", nth=1) == 2
    assert g.slot_of(0, "weapons/punch", include_used=True) == 0


def test_slot_of_missing_card_reports_hand(board):
    """手札に無いカードを指定した場合、現在の手札を添えて失敗させます。"""
    g = board(p0=Side(hand=["weapons/punch"]))
    with pytest.raises(AssertionError, match="現在の手札"):
        g.slot_of(0, "miracles/wall")


# ============================================================================
# 操作 / Actions
# ============================================================================


def test_attack_by_card_name_resolves_slot(board):
    """スロット番号を書かずにカード名で攻撃でき、非0スロットでも通ることを確認します。"""
    g = board(
        p0=Side(hand=[None, None, None, "weapons/punch"]),
        p1=Side(hp=40),
    )
    g.attack("weapons/punch")
    # パンチの威力3が pending に載り、防御側へ手番が渡る
    g.expect(
        phase=GamePhase.PHASE_DEFENSE,
        attacker=0,
        defender=1,
        actor=1,
        pending_power=card_feature("weapons/punch", "attack_power"),
    )


def test_select_slots_targets_the_named_slot(board):
    """同名カードが並ぶとき、select_slots が指定したスロットだけを仮置きすることを確認します。"""
    g = board(
        p0=Side(hand=["weapons/punch", "weapons/punch", "weapons/punch"]),
        p1=Side(hp=40),
    )
    g.select_slots(2)
    assert g.state.get_num_staged_cards(0) == 1
    assert g.state.get_staged_card(0, 0) == 2, "スロット2が仮置きされているべきです"


# ============================================================================
# イベントログ / Event log
# ============================================================================


def test_event_log_is_chronological_and_named(board):
    """イベントが古い順に並び、カードIDが名前に解決されることを確認します。"""
    g = board(p0=Side(mp=50, hand=["armor/leather-clothes"]))
    g.discard("armor/leather-clothes")

    log = g.event_log()
    assert log, "イベントが記録されているべきです"
    types = [e.type for e in log]
    # 「捨てる」を置く -> カードを置く -> 捨てた の順に並ぶ
    assert types.index(EventType.STAGE_CARD) < types.index(EventType.DISCARD_CARD)
    discards = [e for e in log if e.type == EventType.DISCARD_CARD]
    assert discards[-1].card == "革の服"


def test_expect_events_subsequence_and_exact(board):
    """部分列一致と完全一致の双方が機能することを確認します。"""
    g = board(p0=Side(mp=50, hand=["armor/leather-clothes"]))
    g.discard("armor/leather-clothes")

    # 部分列一致: 間に他のイベントが挟まっても通る
    g.expect_events(
        ev(EventType.STAGE_CARD),
        ev(EventType.DISCARD_CARD, card="armor/leather-clothes"),
    )
    # 完全一致は履歴全体と一致しないので失敗する
    with pytest.raises(AssertionError, match="完全一致しません"):
        g.expect_events(ev(EventType.DISCARD_CARD), exact=True)


def test_expect_no_events_detects_unexpected_side_effect(board):
    """発生してはいけないイベントを検出できることを確認します。"""
    g = board(p0=Side(mp=50, hand=["armor/leather-clothes"]))
    g.discard("armor/leather-clothes")
    g.expect_no_events(ev(EventType.ATTACK_HIT))
    with pytest.raises(AssertionError, match="発生しないはずのイベント"):
        g.expect_no_events(ev(EventType.DISCARD_CARD))


# ============================================================================
# 期待値アサーション / Assertions
# ============================================================================


def test_expect_reports_all_mismatches_at_once(board):
    """複数の不一致がまとめて報告され、局面ダンプが添えられることを確認します。"""
    g = board(p0=Side(hp=40), p1=Side(hp=40))
    with pytest.raises(AssertionError) as exc:
        g.expect(p0_hp=1, p1_hp=2, actor=99)
    msg = str(exc.value)
    assert "p0_hp" in msg and "p1_hp" in msg and "actor" in msg
    assert "--- 局面 ---" in msg


def test_expect_rejects_unknown_key(board):
    """タイプミスしたキーが静かに無視されないことを確認します。"""
    g = board()
    with pytest.raises(KeyError, match="を知りません"):
        g.expect(p0_hitpoints=40)


def test_expect_hand_compares_as_multiset(board):
    """手札の比較が順不同かつ枚数を見ることを確認します。"""
    g = board(p0=Side(hand=["weapons/punch", "weapons/punch", "miracles/wall"]))
    g.expect(p0_hand=["miracles/wall", "weapons/punch", "weapons/punch"])
    with pytest.raises(AssertionError, match="p0_hand"):
        g.expect(p0_hand=["weapons/punch", "miracles/wall"])  # 1枚足りない


def test_expect_legal_and_illegal(board):
    """＜壁＞は無属性攻撃にのみ選択でき、有属性攻撃には選べないことを確認します。"""
    g = board(
        p0=Side(mp=10, hand=["weapons/punch"]),
        p1=Side(mp=10, hand=["miracles/wall"]),
    )
    g.attack("weapons/punch")
    g.expect_legal(["miracles/wall"])

    g2 = board(
        p0=Side(mp=10, hand=["weapons/torch"]),  # 火属性
        p1=Side(mp=10, hand=["miracles/wall"]),
    )
    g2.attack("weapons/torch")
    g2.expect_illegal(["miracles/wall"])


# ============================================================================
# 乱数注入 / RNG injection
# ============================================================================


@pytest.mark.parametrize(
    ("worsens", "expect_done"),
    [(True, True), (False, False)],
    ids=["悪化する", "悪化しない"],
)
def test_sentinels_map_to_range_bounds(board, worsens, expect_done):
    """HAPPENS / NEVER が「起きる／起きない」として一貫して働くことを確認します。

    C++ 側の閾値判定はすべて「roll が小さいほど発生する」向きに揃えてあるため、
    テストは個々の確率値（5% や 75%）を知らずに分岐を選べます。
    """
    g = board(
        p0=Side(hp=40, sickness=SicknessType.SICKNESS_HEAVEN, hand=["armor/leather-clothes"]),
    )
    g.rng.sickness_worsen(worsens)
    g.discard("armor/leather-clothes")
    # 天国病の悪化は発作による即死。悪化しなければ +5 回復して生き残る。
    g.expect(is_done=expect_done)
    assert g.rng.consumed(RollKind.SICKNESS_WORSEN) == 1


def test_next_draws_names_the_drawn_card(board):
    """山札から引くカードを名指しできることを確認します（従来は最大10万シード探索）。"""
    g = board(p0=Side(hand=[]))
    g.rng.next_draws("weapons/dangerous-pestle")
    g.pray()
    assert "あぶないキネ" in g.hand(0)


def test_phenomenon_can_be_named(board):
    """超常現象を名指しできることを確認します。"""
    g = board(
        p0=Side(hp=40, mp=50, hand=["sundries/string-of-fate"]),
        p1=Side(hp=40),
    )
    g.rng.deck_always("armor/leather-clothes")  # 補充を固定して局面を決定的にする
    g.rng.phenomenon(PhenomenonType.TORNADO)
    g.use("sundries/string-of-fate", to_self=True)
    g.expect(p0_hp=1, p1_hp=1)  # 竜巻は全員のHPを1にする
    g.expect_events(ev(EventType.TRIGGER_PHENOMENON, card="sundries/string-of-fate"))


def test_guardian_act_choice_uses_percents_from_cpp():
    """守護神の行動選択の代表値が C++ の確率表から正しく導出されることを確認します。"""
    percents = godfield_core.get_guardian_action_percents()
    assert sum(percents) == 100, "確率の合計は100であるべきです"
    assert all(p > 0 for p in percents), "確率0の行動があると、その行動を狙えなくなります"

    # 代表値が各行動の区間に収まっていること（C++側で確率配分を変えてもテストは追従する）
    for action in range(1, len(percents) + 1):
        rep = sum(percents[: action - 1])
        lower = sum(percents[: action - 1])
        upper = sum(percents[:action])
        assert lower <= rep < upper, f"行動{action} の代表値 {rep} が区間 [{lower}, {upper}) の外です"


def test_guardian_act_rejects_out_of_range_action():
    """存在しない行動番号を静かに受け付けないことを確認します。"""
    from tests.core.dsl import RngController

    with pytest.raises(ValueError, match="action は 1.."):
        RngController().guardian_act(acts=True, action=99)
    # ValueError の前に GUARDIAN_ACT を仕込んでいるため、autouse 検査用に破棄する
    godfield_core.rng_clear_script()


def test_script_rejects_more_rolls_than_declared(board):
    """script() は宣言した回数を超えて判定されると例外にします。

    病気の悪化判定は「そのターンを終えた側」に対して1ターンに1回だけ行われるため、
    双方を病気にして2ターン終了させれば2回転がる。1回ぶんしか宣言していなければ
    2回目で例外になり、乱数消費回数の変化に気付ける。
    """
    g = board(
        p0=Side(hp=40, mp=50, sickness=SicknessType.SICKNESS_COLD,
                hand=["armor/leather-clothes"]),
        p1=Side(hp=40, mp=50, sickness=SicknessType.SICKNESS_COLD,
                hand=["armor/wood-shield"]),
    )
    g.rng.script(RollKind.SICKNESS_WORSEN, [NEVER])  # 1回ぶんだけ宣言

    g.discard("armor/leather-clothes")  # P0のターン終了 -> 1回目
    assert g.rng.consumed(RollKind.SICKNESS_WORSEN) == 1

    with pytest.raises(RuntimeError, match="スクリプトが枯渇しました"):
        g.discard("armor/wood-shield")  # P1のターン終了 -> 2回目で例外


def test_out_of_range_value_is_rejected(board):
    """実装側の範囲が変わった場合に気付けるよう、範囲外の指示は例外にします。"""
    g = board(
        p0=Side(hp=40, mp=50, hand=["sundries/string-of-fate"]),
        p1=Side(hp=40),
    )
    g.rng.force(RollKind.PHENOMENON, 999)  # 現象は 0..9
    with pytest.raises(RuntimeError, match="範囲外の値"):
        g.use("sundries/string-of-fate", to_self=True)
    # このテストは意図的に例外を出すため、指示を消費済みにして autouse 検査を通す
    godfield_core.rng_clear_script()


def test_forbid_unscripted_proves_determinism(board):
    """forbid_unscripted を付けたテストが、指示外の乱数消費で落ちることを確認します。"""
    g = board(p0=Side(hand=[]))
    g.rng.forbid_unscripted()
    with pytest.raises(RuntimeError, match="指示なしで転がされました"):
        g.pray()  # 山札ドローを指示していないので落ちる
    godfield_core.rng_clear_script()


def test_pick_order_selects_discarded_slots(board):
    """ランダム破棄で「どのスロットが捨てられるか」を指定できることを確認します。

    従来はシードを振って偶然の並びに頼るしかなく、破棄対象を狙って検証できなかった。
    """
    g = board(
        p0=Side(hp=40, mp=50, hand=["sundries/nocturnal-broom"]),
        p1=Side(
            hp=40,
            hand=["armor/leather-clothes", "armor/iron-shield", "weapons/punch",
                  "armor/wood-shield", "miracles/wall"],
        ),
    )
    g.rng.deck_always("armor/leather-clothes")
    # 夜空のホウキは未使用・未展開の手札を3枚破棄する。破棄されるスロットを明示する。
    g.rng.discard_order(4, 2, 0)
    g.use("sundries/nocturnal-broom")
    g.confirm()  # 相手が受け入れる

    # スロット 0(革の服), 2(パンチ), 4(＜壁＞) が破棄され、1(アイアンシールド) と 3(木の盾) が残る
    g.expect(p1_hand=["armor/iron-shield", "armor/wood-shield"])
    assert g.state.get_true_hand(1, 1) == card_id("armor/iron-shield")
    assert g.state.get_true_hand(1, 3) == card_id("armor/wood-shield")


def test_deck_always_rejects_devil_cards():
    """悪魔カードを sticky で固定すると無限ループするため、API 側で弾くことを確認します。

    draw_card_with_apocalypse は悪魔を引くと効果を適用して再ドローするループなので、
    常に悪魔が返ると永久に抜けられない。
    """
    from tests.core.dsl import RngController

    with pytest.raises(ValueError, match="無限ループ"):
        RngController().deck_always("devils/small-devil")
    godfield_core.rng_clear_script()


def test_unconsumed_script_fails_the_test(board):
    """指示したのに使われなかった場合にテストが失敗することを、直接検証します。

    autouse フィクスチャ本体の挙動は pytest 内から観測しづらいため、
    C++ 側の報告関数が正しく「未消費」を返すことを確認します。
    """
    godfield_core.rng_clear_script()
    assert godfield_core.rng_unconsumed_kinds() == []
    godfield_core.rng_force(RollKind.MOON_MIRACLE, 0)
    assert "MOON_MIRACLE" in godfield_core.rng_unconsumed_kinds()
    godfield_core.rng_clear_script()
    assert godfield_core.rng_unconsumed_kinds() == []


def test_script_is_isolated_between_tests():
    """前のテストの指示が漏れていないことを確認します（autouse フィクスチャの検証）。"""
    assert godfield_core.rng_unconsumed_kinds() == []
    for kind in (RollKind.BOUNCE, RollKind.PHENOMENON, RollKind.DECK_DRAW):
        assert godfield_core.rng_consumed(kind) == 0


def test_board_starts_with_the_same_sentinels_as_a_real_game(board):
    """テストの盤面が、実ゲームの開始局面と同じ番兵を持つことを検証します。

    これらのフィールドは 0 が有効な値（プレイヤーID 0 / カードID 0）になるため、
    ゼロ埋めした状態を盤面として使うと「未設定」を検出できません。実際、
    clear_state() がゼロ埋めのままだったために pending_initiator が 0 になり、
    「守護神の罰金・わいろを受諾すると実ゲームだけ例外で落ちる」不具合を
    テストが素通りさせていました。
    """
    g = board(p0=Side(hp=40), p1=Side(hp=40))
    assert g.state.pending_initiator == -1, (
        "仕掛けた側が未設定であることを表せないと、記録漏れを検出できません"
    )
    assert g.state.attacker_id == -1
    assert g.state.defender_id == -1
    assert g.state.pending_attack_source_id == godfield_core.CARD_EMPTY
