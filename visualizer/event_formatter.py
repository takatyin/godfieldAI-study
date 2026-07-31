"""イベント履歴を、見ている人の視点で1行の日本語にする。

【呼び方の約束】ログを見ている本人が「あなた」、その対戦相手が「相手」。
席番号（プレイヤー0/1）は出しません。両方の席のログを同じ関数で作るので、
`player_id` を基準に決めるのが唯一の正解です。

「自分」という語は使いません。以前は行為者を指すのか閲覧者を指すのかが
文脈で変わっており、「敵 自分へ 【回復】 を使った」が
『敵が敵自身に使った』とも『敵が私に使った』とも読めていました。
行為者と対象が同じときは「相手 が 相手自身 に」のように明示します。
"""

from visualizer.constants import CARDS_BY_ID, CURSE_DICT, GUARDIAN_DICT, PHENOMENA_MESSAGES, SICKNESS_DICT

# 閲覧者と、その対戦相手の呼び方。
VIEWER_NAME = "あなた"
OPPONENT_NAME = "相手"


def _fmt_type_1(ev, actor_name, card_name, target_name):
    if ev.card_id == -1:
        return f"{actor_name} 置いた 【捨てる】"
    return f"{actor_name} 置いた 【{card_name}】"

# 現在のエンジンは UNSTAGE_CARD を発行していないが、EventType には定義されており
# 将来使われる可能性がある。未登録のまま発行されると「イベント (種別:2)」という
# 意味不明な行になるため、あらかじめ用意しておく。
def _fmt_type_2(ev, actor_name, card_name, target_name):
    return f"{actor_name} 戻した 【{card_name}】"

def _fmt_type_3(ev, actor_name, card_name, target_name):
    # 対象が行為者自身のときは「自分へ」では誰を指すのか読めないので、
    # 「あなた が あなた自身 に」のように行為者を名指しして繰り返す。
    if ev.target_id == ev.actor:
        target_name = f"{actor_name}自身"
    if ev.card_id > 0:
        if ev.target_id >= 0:
            return f"{actor_name} が {target_name} に 【{card_name}】 を使った"
        return f"{actor_name} 確定 【{card_name}】"
    if ev.target_id >= 0:
        return f"{actor_name} が {target_name} にカードを使用"
    return f"{actor_name} 行動確定"

def _fmt_type_4(ev, actor_name, card_name, target_name):
    return f"{actor_name} 防御確定 ({int(ev.value)}ガード)"

def _fmt_type_5(ev, actor_name, card_name, target_name):
    return f"{actor_name} 防御スルー (受領)"

def _fmt_type_6(ev, actor_name, card_name, target_name):
    return f"{actor_name} 攻撃ヒット ({int(ev.value)}ダメージ)"

def _fmt_type_7(ev, actor_name, card_name, target_name):
    if ev.card_id == 109:
        return f"{actor_name} 【昇天弓】 命中失敗 (ミス！)"
    return f"{actor_name} 全体攻撃 命中失敗 (ミス！)"

def _fmt_type_8(ev, actor_name, card_name, target_name):
    v = int(ev.value)
    sick_type = v & 0x0F
    is_damage = bool(v & 16)
    is_heal = bool(v & 32)
    is_worsened = bool(v & 64)
    is_seizure = bool(v & 128)
    is_cured = bool(v & 256)
    s_name = SICKNESS_DICT.get(sick_type, "病気")
    if is_cured:
        return f"{actor_name} 【{s_name}】が治った"
    if is_seizure:
        return f"{actor_name} 【{s_name}】の発作が発生！"
    if is_worsened:
        return f"{actor_name} 病気が【{s_name}】に悪化した！"
    if is_heal:
        return f"{actor_name} 【{s_name}】の効果で HP 5 回復"
    if is_damage:
        dmg = 1 if sick_type == 1 else (2 if sick_type == 2 else 5)
        return f"{actor_name} 【{s_name}】の症状で {dmg} ダメージ"
    return f"{actor_name} 病気効果発動！"

def _fmt_type_9(ev, actor_name, card_name, target_name):
    guardian_id = int(ev.value)
    g_name = GUARDIAN_DICT.get(guardian_id, "守護神")
    if card_name and card_name != "？" and not card_name.startswith("裏向き") and not card_name.startswith("カードID:"):
        return f"{actor_name} (守護神: {g_name}) の【{card_name}】が発動！"
    return f"{actor_name} の守護神 ({g_name}) が行動！"

def _fmt_type_10(ev, actor_name, card_name, target_name):
    return f"{actor_name} 【{card_name}】 で跳ね返した！" if ev.card_id > 0 else f"{actor_name} 跳ね返した！"

def _fmt_type_11(ev, actor_name, card_name, target_name):
    return f"{actor_name} {int(ev.value)} ダメージを受けた"

def _fmt_type_12(ev, actor_name, card_name, target_name):
    return f"{actor_name} HP {int(ev.value)} 回復"

def _fmt_type_13(ev, actor_name, card_name, target_name):
    return f"{actor_name} MP {int(ev.value)} 回復"

# 取引の3種（購入・売却・見送り）は、相手が誰かを必ず書く。
# 「買う」「売る」は対象選択の結果として USE_CARD が発行されないため、
# ここに相手を出さないと「誰に仕掛けた取引なのか」がログから消える。
# イベント側には取引相手が target_id として入っている。
def _fmt_type_14(ev, actor_name, card_name, target_name):
    price_str = f" ({int(ev.value)}円)" if ev.value > 0 else ""
    seller = f"{target_name} から " if target_name else ""
    return f"{actor_name} が {seller}【{card_name}】 を購入した{price_str}"

def _fmt_type_15(ev, actor_name, card_name, target_name):
    price_str = f" (+{int(ev.value)}円)" if ev.value > 0 else ""
    buyer = f"{target_name} に " if target_name else ""
    return f"{actor_name} が {buyer}【{card_name}】 を売却した{price_str}"

def _fmt_type_16(ev, actor_name, card_name, target_name):
    return f"{actor_name} 両替を行った"

def _fmt_type_17(ev, actor_name, card_name, target_name):
    return f"{actor_name} 祈った (カードドロー)"

def _fmt_type_18(ev, actor_name, card_name, target_name):
    return f"{actor_name} 【{card_name}】 を捨てた" if ev.card_id > 0 else f"{actor_name} カードを捨てた"

def _fmt_type_19(ev, actor_name, card_name, target_name):
    seller = f"{target_name} の " if target_name else ""
    if ev.card_id > 0:
        return f"{actor_name} が {seller}【{card_name}】 を買わなかった"
    return f"{actor_name} が {target_name} との取引を見送った" if target_name else f"{actor_name} 取引を見送った"

def _fmt_type_20(ev, actor_name, card_name, target_name):
    return f"{actor_name} 【{card_name}】 で阻止した！" if ev.card_id > 0 else f"{actor_name} 阻止した！"

def _fmt_type_21(ev, actor_name, card_name, target_name):
    if ev.value > 0:
        return f"{actor_name} 【{card_name}】 で弾いた！" if ev.card_id > 0 else f"{actor_name} 弾いた！"
    return f"{actor_name} 【{card_name}】 で弾くのを失敗した..." if ev.card_id > 0 else f"{actor_name} 弾くのを失敗した..."

def _fmt_type_22(ev, actor_name, card_name, target_name):
    p_id = int(ev.value)
    p_msg = PHENOMENA_MESSAGES[p_id] if 0 <= p_id < len(PHENOMENA_MESSAGES) else "超常現象が発生！"
    return f"{actor_name} 【運命のひも】 で{p_msg}"

def _fmt_type_23(ev, actor_name, card_name, target_name):
    return f"{actor_name} 【{card_name}】 で跳ね返した！" if ev.card_id > 0 else f"{actor_name} 跳ね返した！"

def _fmt_type_24(ev, actor_name, card_name, target_name):
    return f"{actor_name} 【{card_name}】 の反撃が発動！" if ev.card_id > 0 else f"{actor_name} 指輪効果発動！"

def _fmt_type_25(ev, actor_name, card_name, target_name):
    guardian_id = int(ev.value)
    g_name = GUARDIAN_DICT.get(guardian_id, "守護神")
    return f"{actor_name} に守護神 ({g_name}) が宿った！"

def _fmt_type_26(ev, actor_name, card_name, target_name):
    guardian_id = int(ev.value)
    g_name = GUARDIAN_DICT.get(guardian_id, "守護神")
    return f"{actor_name} の守護神 ({g_name}) は帰っていった"

def _fmt_type_27(ev, actor_name, card_name, target_name):
    v = int(ev.value)
    curse_type = v & 0x0F
    is_applied = bool(v & 16)
    is_cleared = bool(v & 32)
    c_name = CURSE_DICT.get(curse_type, "呪い")
    if is_applied:
        return f"{actor_name} 【{c_name}】状態になった！"
    if is_cleared:
        return f"{actor_name} 【{c_name}】状態から回復した"
    return f"{actor_name} 呪い状態変化"

def _fmt_type_28(ev, actor_name, card_name, target_name):
    return f"{actor_name} 闇属性の攻撃を防ぎきれず即死した！"

def _fmt_type_29(ev, actor_name, card_name, target_name):
    hp = int(ev.value)
    revived = f"HP{hp} で復活した！" if hp > 0 else "復活した！"
    return f"{actor_name} 【{card_name}】 で{revived}" if ev.card_id > 0 else f"{actor_name} {revived}"

FORMATTERS = {
    1: _fmt_type_1,
    2: _fmt_type_2,
    3: _fmt_type_3,
    4: _fmt_type_4,
    5: _fmt_type_5,
    6: _fmt_type_6,
    7: _fmt_type_7,
    8: _fmt_type_8,
    9: _fmt_type_9,
    10: _fmt_type_10,
    11: _fmt_type_11,
    12: _fmt_type_12,
    13: _fmt_type_13,
    14: _fmt_type_14,
    15: _fmt_type_15,
    16: _fmt_type_16,
    17: _fmt_type_17,
    18: _fmt_type_18,
    19: _fmt_type_19,
    20: _fmt_type_20,
    21: _fmt_type_21,
    22: _fmt_type_22,
    23: _fmt_type_23,
    24: _fmt_type_24,
    25: _fmt_type_25,
    26: _fmt_type_26,
    27: _fmt_type_27,
    28: _fmt_type_28,
    29: _fmt_type_29,
}

def format_event_log(ev, player_id):
    if not hasattr(ev, "event_type") or ev.event_type == 0:
        return None

    # 席0を決め打ちにしてはいけない。ログはプレイヤー1の視点でも作られるので
    # （visualize_server が p0_obs / p1_obs の両方を serialize する）、
    # 席0固定だとプレイヤー1のログでは行為者の呼び方が入れ替わってしまう。
    # 対象側は元から player_id を見ており、行為者だけがずれていた。
    actor_name = VIEWER_NAME if ev.actor == player_id else OPPONENT_NAME
    card_name = "？"
    if ev.card_id >= 0:
        c_info = CARDS_BY_ID.get(ev.card_id)
        if c_info:
            card_name = c_info.get("name", f"ID:{ev.card_id}")
        elif ev.card_id == 0:
            card_name = "両替"
        else:
            card_name = f"カードID:{ev.card_id}"
    elif ev.card_id == -1:
        card_name = "裏向きカード"

    if ev.target_id == player_id:
        target_name = VIEWER_NAME
    elif ev.target_id == 1 - player_id:
        target_name = OPPONENT_NAME
    else:
        target_name = ""

    etype = ev.event_type

    formatter = FORMATTERS.get(etype)
    if formatter:
        text = formatter(ev, actor_name, card_name, target_name)
    else:
        text = f"{actor_name} イベント (種別:{etype})"

    return {
        "actor": ev.actor,
        "event_type": etype,
        "card_id": ev.card_id,
        "card_name": card_name,
        "target_id": ev.target_id,
        "value": ev.value,
        "text": text,
    }
