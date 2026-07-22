import asyncio
import json
import os
import random
import uvicorn
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from fastapi.staticfiles import StaticFiles
import godfield_core

app = FastAPI()
app.mount("/assets", StaticFiles(directory="assets"), name="assets")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load card data registry
project_root = os.path.dirname(os.path.abspath(__file__))
json_path = os.path.join(project_root, "assets", "godfield_cards.json")
with open(json_path, encoding="utf-8") as f:
    cards = json.load(f)

# Initialize C++ game logic
godfield_core.init_game_logic(cards)
cards_by_id = {c["id"]: c for c in cards}

# Shared game state
env_pool = godfield_core.EnvPool(1)
state = None
ai_enabled = True  # Player 1 is controlled by AI by default


def reset_game(seed=None):
    global state
    if seed is None:
        seed = random.randint(0, 100000)
    env_pool.reset(seed)
    state = env_pool.get_state(0)


def get_ai_action():
    legal = godfield_core.get_legal_actions(state)
    valid_actions = [idx for idx, val in enumerate(legal) if val]
    if not valid_actions:
        return None

    # Heuristics:
    # 1. If Confirm/Target Opp/Self is available, prioritize it to finalize staging/defense
    if 18 in valid_actions:  # ACTION_TARGET_OPP / ACTION_DEAL_YES
        return 18
    if 19 in valid_actions:  # ACTION_TARGET_SELF / ACTION_DEAL_NO / ACTION_CONFIRM
        return 19
    # 2. Prefer using a weapon/miracle/defense card rather than discarding/praying
    card_actions = [a for a in valid_actions if a < 18]
    if card_actions:
        # Avoid empty slots
        non_empty_card_actions = []
        for a in card_actions:
            cid = state.get_apparent_hand(1, a)
            if cid != -1:
                non_empty_card_actions.append(a)
        if non_empty_card_actions:
            return random.choice(non_empty_card_actions)

    # 3. Fallback to random action
    return random.choice(valid_actions)


def run_ai_steps():
    # If it is Player 1's turn and AI is enabled, auto-step Player 1
    while not state.is_done and state.current_actor_id == 1 and ai_enabled:
        ai_act = get_ai_action()
        if ai_act is None:
            break
        godfield_core.step_game(state, godfield_core.ActionType(ai_act))

        # Auto-advance
        while not state.is_done:
            auto_action = godfield_core.get_single_legal_action(state)
            if auto_action == -1:
                break
            godfield_core.step_game(state, godfield_core.ActionType(auto_action))


def format_event_log(ev, player_id):
    if not hasattr(ev, "event_type") or ev.event_type == 0:
        return None

    actor_name = "自分" if ev.actor == 0 else "敵"
    card_name = "？"
    if ev.card_id >= 0:
        c_info = cards_by_id.get(ev.card_id)
        if c_info:
            card_name = c_info.get("name", f"ID:{ev.card_id}")
        elif ev.card_id == 0:
            card_name = "両替"
        else:
            card_name = f"カードID:{ev.card_id}"
    elif ev.card_id == -1:
        card_name = "裏向きカード"

    target_name = "自分" if ev.target_id == player_id else ("敵" if ev.target_id == (1 - player_id) else "")

    etype = ev.event_type
    text = ""
    if etype == 1:
        if ev.card_id == -1:
            text = f"{actor_name} 置いた 【捨てる】"
        else:
            text = f"{actor_name} 置いた 【{card_name}】"
    elif etype == 3:
        if ev.card_id > 0:
            if ev.target_id == ev.actor:
                text = f"{actor_name} 自分へ 【{card_name}】 を使った"
            elif ev.target_id >= 0:
                text = f"{actor_name} {target_name}へ 【{card_name}】 を使った"
            else:
                text = f"{actor_name} 確定 【{card_name}】"
        else:
            if ev.target_id >= 0:
                text = f"{actor_name} {target_name}へカードを使用"
            else:
                text = f"{actor_name} 行動確定"
    elif etype == 4:
        text = f"{actor_name} 防御確定 ({int(ev.value)}ガード)"
    elif etype == 5:
        text = f"{actor_name} 防御スルー (受領)"
    elif etype == 6:
        text = f"{actor_name} 攻撃ヒット ({int(ev.value)}ダメージ)"
    elif etype == 7:
        if ev.card_id == 109:
            text = f"{actor_name} 【昇天弓】 命中失敗 (ミス！)"
        else:
            text = f"{actor_name} 全体攻撃 命中失敗 (ミス！)"
    elif etype == 8:
        v = int(ev.value)
        sick_type = v & 0x0F
        is_damage = bool(v & 16)
        is_heal = bool(v & 32)
        is_worsened = bool(v & 64)
        is_seizure = bool(v & 128)

        sick_names = {1: "風邪", 2: "熱病", 3: "地獄病", 4: "天国病"}
        s_name = sick_names.get(sick_type, "病気")

        if is_seizure:
            text = f"{actor_name} 【{s_name}】の発作が発生！"
        elif is_worsened:
            text = f"{actor_name} 病気が【{s_name}】に悪化した！"
        elif is_heal:
            text = f"{actor_name} 【{s_name}】の効果で HP 5 回復"
        elif is_damage:
            dmg = 1 if sick_type == 1 else (2 if sick_type == 2 else 5)
            text = f"{actor_name} 【{s_name}】の症状で {dmg} ダメージ"
        else:
            text = f"{actor_name} 病気効果発動！"
    elif etype == 9:
        guardian_id = int(ev.value)
        guardian_names = {
            1: "火星神", 2: "水星神", 3: "木星神", 4: "土星神", 5: "天王神",
            6: "冥王神", 7: "海王神", 8: "金星神", 9: "地球神", 10: "月神"
        }
        g_name = guardian_names.get(guardian_id, "守護神")
        if card_name and card_name != "？" and not card_name.startswith("裏向き") and not card_name.startswith("カードID:"):
            text = f"{actor_name} (守護神: {g_name}) の【{card_name}】が発動！"
        else:
            text = f"{actor_name} の守護神 ({g_name}) が行動！"
    elif etype == 10:
        text = f"{actor_name} 【{card_name}】 で跳ね返した！" if ev.card_id > 0 else f"{actor_name} 跳ね返した！"
    elif etype == 11:
        text = f"{actor_name} {int(ev.value)} ダメージを受けた"
    elif etype == 12:
        text = f"{actor_name} HP {int(ev.value)} 回復"
    elif etype == 13:
        text = f"{actor_name} MP {int(ev.value)} 回復"
    elif etype == 14:
        price_str = f" ({int(ev.value)}円)" if ev.value > 0 else ""
        text = f"{actor_name} 【{card_name}】 を購入した{price_str}"
    elif etype == 15:
        price_str = f" (+{int(ev.value)}円)" if ev.value > 0 else ""
        text = f"{actor_name} 【{card_name}】 を売却した{price_str}"
    elif etype == 16:
        text = f"{actor_name} 両替を行った"
    elif etype == 17:
        text = f"{actor_name} 祈った (カードドロー)"
    elif etype == 18:
        text = f"{actor_name} 【{card_name}】 を捨てた" if ev.card_id > 0 else f"{actor_name} カードを捨てた"
    elif etype == 19:
        text = f"{actor_name} 【{card_name}】 を買わなかった" if ev.card_id > 0 else f"{actor_name} 取引を見送った"
    elif etype == 20:
        text = f"{actor_name} 【{card_name}】 で阻止した！" if ev.card_id > 0 else f"{actor_name} 阻止した！"
    elif etype == 21:
        if ev.value > 0:
            text = f"{actor_name} 【{card_name}】 で弾いた！" if ev.card_id > 0 else f"{actor_name} 弾いた！"
        else:
            text = f"{actor_name} 【{card_name}】 で弾くのを失敗した..." if ev.card_id > 0 else f"{actor_name} 弾くのを失敗した..."
    elif etype == 22:
        p_id = int(ev.value)
        phenomena_messages = [
            "夕焼けが発生！（全員熱病）",
            "濃霧が発生！（全員霧）",
            "きのこが大発生した！",
            "竜巻が発生！（全員HPが1になった）",
            "巨大なタライが降ってきた！",
            "ブラックホールが発生した！",
            "暖流が発生した！（HP+50）",
            "金山が発見された！（お金を独占）",
            "磁気嵐が発生した！（手札が入れ替わった）",
            "日食が発生した！（守護神が降臨した）"
        ]
        p_msg = phenomena_messages[p_id] if 0 <= p_id < len(phenomena_messages) else "超常現象が発生！"
        text = f"{actor_name} 【運命のひも】 で{p_msg}"
    elif etype == 23:
        text = f"{actor_name} 【{card_name}】 で跳ね返した！" if ev.card_id > 0 else f"{actor_name} 跳ね返した！"
    elif etype == 24:
        text = f"{actor_name} 【{card_name}】 の反撃が発動！" if ev.card_id > 0 else f"{actor_name} 指輪効果発動！"
    elif etype == 25:
        guardian_id = int(ev.value)
        guardian_names = {
            1: "火星神", 2: "水星神", 3: "木星神", 4: "土星神", 5: "天王神",
            6: "冥王神", 7: "海王神", 8: "金星神", 9: "地球神", 10: "月神"
        }
        g_name = guardian_names.get(guardian_id, "守護神")
        text = f"{actor_name} に守護神 ({g_name}) が宿った！"
    elif etype == 26:
        guardian_id = int(ev.value)
        guardian_names = {
            1: "火星神", 2: "水星神", 3: "木星神", 4: "土星神", 5: "天王神",
            6: "冥王神", 7: "海王神", 8: "金星神", 9: "地球神", 10: "月神"
        }
        g_name = guardian_names.get(guardian_id, "守護神")
        text = f"{actor_name} の守護神 ({g_name}) は帰っていった"
    elif etype == 27:
        v = int(ev.value)
        curse_type = v & 0x0F
        is_applied = bool(v & 16)
        is_cleared = bool(v & 32)
        curse_names = {1: "霧", 2: "閃光", 3: "暗雲", 4: "夢"}
        c_name = curse_names.get(curse_type, "呪い")
        if is_applied:
            text = f"{actor_name} 【{c_name}】状態になった！"
        elif is_cleared:
            text = f"{actor_name} 【{c_name}】状態から回復した"
        else:
            text = f"{actor_name} 呪い状態変化"
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


# Single Source of Truth for Card Element & Staged Calculation (Server Side)
def normalize_element(element):
    if not element:
        return "none"
    elem = str(element).lower().strip()
    if "fire" in elem or "火" in elem:
        return "fire"
    if "water" in elem or "水" in elem:
        return "water"
    if "wood" in elem or "木" in elem:
        return "wood"
    if "stone" in elem or "土" in elem:
        return "stone"
    if "light" in elem or "光" in elem:
        return "light"
    if "darkness" in elem or "闇" in elem:
        return "darkness"
    return "none"


def combine_elements(cards):
    if not cards:
        return "none"

    current_element = None
    has_processed = False

    for card in cards:
        if not card:
            continue

        cid = card.get("id", -1)
        name = card.get("name", "")
        raw_elem = card.get("element", "none")
        e = normalize_element(raw_elem)

        # ワンド（発火のワンド、水魔のワンド等）は無条件で攻撃属性をその属性へ確定・上書き
        is_wand = "ワンド" in name or cid in [63, 64]

        if "精霊" in name:
            # 精霊系カードは属性計算に関与しない
            continue
        elif is_wand:
            current_element = e
            has_processed = True
        else:
            if not has_processed:
                current_element = e
                has_processed = True
            else:
                if e == "none" or current_element == "none":
                    current_element = "none"
                elif e == "light":
                    if current_element == "darkness":
                        current_element = "none"
                elif current_element == "light":
                    if e == "darkness":
                        current_element = "none"
                    else:
                        current_element = e
                elif current_element != e:
                    current_element = "none"

    return current_element if has_processed else "none"


def get_element_badge_class(element):
    key = normalize_element(element)
    classes = {
        "fire": "bg-gradient-to-r from-red-600 to-rose-700 border border-red-400 text-white shadow-[0_0_15px_rgba(239,68,68,0.5)]",
        "water": "bg-gradient-to-r from-blue-600 to-cyan-700 border border-blue-400 text-white shadow-[0_0_15px_rgba(59,130,246,0.5)]",
        "wood": "bg-gradient-to-r from-orange-500 to-amber-600 border border-orange-400 text-white shadow-[0_0_15px_rgba(249,115,22,0.5)]",
        "stone": "bg-gradient-to-r from-slate-600 to-slate-800 border border-slate-400 text-slate-100 shadow-[0_0_15px_rgba(100,116,139,0.5)]",
        "light": "bg-gradient-to-r from-amber-400 to-yellow-400 border border-yellow-200 text-slate-950 font-black shadow-[0_0_15px_rgba(245,158,11,0.5)]",
        "darkness": "bg-gradient-to-r from-purple-800 to-indigo-950 border border-purple-400 text-purple-200 shadow-[0_0_15px_rgba(168,85,247,0.5)]",
    }
    return classes.get(
        key,
        "bg-gradient-to-r from-slate-800 to-slate-950 border border-slate-600 text-white font-black shadow-[0_0_12px_rgba(0,0,0,0.6)]",
    )


def get_element_text_color(element):
    key = normalize_element(element)
    colors = {
        "none": "#000000",
        "fire": "#ff6666",
        "water": "#3b82f6",
        "wood": "#ff9900",
        "stone": "#6688aa",
        "light": "#eab308",
        "darkness": "#a855f7",
    }
    return colors.get(key, "#000000")


def compute_staged_total_badge(staged_cards, player_id, game_state):
    if not staged_cards:
        return None

    phase = game_state.current_phase.name
    if phase == "PHASE_DISCARD":
        return None

    # C++ エンジンの pending リアルタイム更新情報を直接参照
    sell_price = getattr(game_state, "pending_sell_price", 0)
    has_sell = any(c and c.get("name") == "売る" for c in staged_cards)
    if (has_sell or "SELL" in phase):
        # 1枚目の「売る」「買う」はアクションカード（トリガー）なので除外し、2枚目以降（売却対象）の価格を合計する
        calc_price = 0
        for idx, c in enumerate(staged_cards):
            if c:
                if idx == 0 and c.get("name") in ["売る", "買う"]:
                    continue
                calc_price += c.get("price", 0)
        total_price = sell_price if sell_price > 0 else calc_price
        return {
            "label": f"¥{total_price}",
            "type": "price",
            "element": "none",
            "badge_class": "bg-amber-400 border border-amber-200 text-slate-950 font-black shadow-[0_0_15px_rgba(245,158,11,0.5)]",
        }

    is_defender = phase in ["PHASE_DEFENSE", "PHASE_MIRACLE_DEFENSE"] and game_state.current_actor_id == player_id

    if is_defender:
        def_power = getattr(game_state, "pending_defense_power", 0)
        if def_power == 0 and staged_cards:
            def_power = sum(c.get("defense_power", 0) for c in staged_cards if c)

        # リアクション効果（はね返す/弾く/阻止）は「1枚目に置かれたカード」かつ「現在の攻撃タイプに対応するリアクションカード」のみ有効
        first_staged = staged_cards[0] if staged_cards else None
        first_reaction = first_staged.get("reaction_type") if first_staged else None
        first_name = first_staged.get("name", "") if first_staged else ""
        first_timings = first_staged.get("usage_timing", []) if first_staged else []

        is_valid_first_reaction = False
        if first_reaction:
            if phase == "PHASE_MIRACLE_DEFENSE":
                if any("miracle_defence" in str(t).lower() for t in first_timings) or first_name == "スーパーミラー":
                    is_valid_first_reaction = True
            elif phase == "PHASE_DEFENSE":
                if first_name in ["スーパーミラー", "壁", "反射剣", "乱弾武剣"]:
                    is_valid_first_reaction = True

        if is_valid_first_reaction:
            if first_reaction == "reflect":
                return {
                    "label": "はね返す",
                    "type": "defense",
                    "element": "none",
                    "badge_class": "bg-blue-600 border border-blue-300 text-white font-black shadow-[0_0_15px_rgba(37,99,235,0.5)]",
                }
            elif first_reaction == "bounce":
                return {
                    "label": "弾く",
                    "type": "defense",
                    "element": "none",
                    "badge_class": "bg-cyan-600 border border-cyan-300 text-white font-black shadow-[0_0_15px_rgba(6,182,212,0.5)]",
                }
            elif first_reaction == "block":
                return {
                    "label": "阻止",
                    "type": "defense",
                    "element": "none",
                    "badge_class": "bg-emerald-600 border border-emerald-300 text-white font-black shadow-[0_0_15px_rgba(16,185,129,0.5)]",
                }
        elif def_power > 0:
            return {
                "label": f"守{def_power}",
                "type": "defense",
                "element": "none",
                "badge_class": "bg-slate-700 border border-slate-500 text-white font-black shadow-[0_0_12px_rgba(0,0,0,0.6)]",
            }
        return None
    else:
        atk_power = getattr(game_state, "pending_attack_power", 0)
        c_elem = getattr(game_state, "pending_attack_element", None)
        elem_name = normalize_element(str(c_elem) if c_elem is not None else "none")

        if atk_power > 0 or elem_name != "none":
            badge_cls = get_element_badge_class(elem_name)
            return {
                "label": f"攻{atk_power}",
                "type": "attack",
                "element": elem_name,
                "badge_class": badge_cls,
            }
        return None


def compute_smart_action_label(action_id, staged_cards, game_state):
    phase = game_state.current_phase.name
    first_card = staged_cards[0] if staged_cards else None
    first_name = first_card.get("name", "") if first_card else ""

    if action_id == 18:
        if phase in ["PHASE_BUY", "PHASE_BUY_SELECT_MIRROR"]:
            return "買う"
        if phase in ["PHASE_SELL_SELECT", "PHASE_SELL_SELECT_MIRROR"]:
            return "承諾"
        if first_card:
            # 全体攻撃や、売買・両替・確定系のカードは「決定」を表示
            is_non_targeted = (
                first_card.get("is_group_attack", False)
                or first_name in ["売る", "買う"]
                or "昇天" in first_name
                or "両替" in first_name
            )
            if is_non_targeted:
                return "決定"
        return "相手を対象"

    if action_id == 19:
        if phase in ["PHASE_TRADE", "PHASE_BUY"]:
            return "買わない"
        if phase in ["PHASE_BUY_SELECT_MIRROR", "PHASE_SELL_SELECT_MIRROR", "PHASE_SUNDRY_SELECT_MIRROR"]:
            if staged_cards:
                return "はね返す"
            return "受け入れる"
        if phase in ["PHASE_DEFENSE", "PHASE_MIRACLE_DEFENSE"]:
            return "確定"
        if phase == "PHASE_DISCARD":
            return "捨てる"
        if phase in ["PHASE_SELL_SELECT"]:
            return "確定"
        if staged_cards:
            return "自分を対象"
        return "確定"

    if action_id == 20:
        return "祈る"
    if action_id == 21:
        return "捨てる"

    return ""


def serialize_observation(obs, player_id):
    sickness_names = ["なし", "風邪", "熱病", "地獄病", "天国病"]
    guardian_names = [
        "なし",
        "火星神",
        "水星神",
        "木星神",
        "金星神",
        "土星神",
        "天王星神",
        "海王星神",
        "冥王星神",
        "月神",
        "地殻神",
    ]
    curse_names = ["霧", "閃光", "暗雲", "夢"]

    phase = state.current_phase.name
    # 売却フェイズまたは「売る」仮置き中かを検出
    staged_cids = [cid for cid in obs.get_staged_cards() if cid != -1]
    staged_cards_info = [cards_by_id.get(cid) for cid in staged_cids]
    has_sell_staged = any(c and c.get("name") == "売る" for c in staged_cards_info)
    is_sell_mode = phase in ["PHASE_SELL_SELECT", "PHASE_SELL_SELECT_MIRROR"] or has_sell_staged
    is_buy_mode = phase in ["PHASE_BUY", "PHASE_BUY_SELECT_MIRROR"]
    is_transaction_mode = is_sell_mode or is_buy_mode

    # 防御側ターン中かを検出
    is_defender = phase in ["PHASE_DEFENSE", "PHASE_MIRACLE_DEFENSE"] and state.current_actor_id == player_id

    def compute_card_power_label(card, slot_idx=None, owner_id=None, is_staged=False):
        """現在のコンテキスト（売却、防御、攻撃プラス、メイン等）に応じて、
        カードが持つ意味（価格、+攻、守、リアクション名、特殊効果等）を算出する。"""
        if not card:
            return ""

        # 手札内のカードであり、かつ使用中（ステージング済み）の場合は、手札側でのラベル表示を非表示にする
        if slot_idx is not None and owner_id is not None and not is_staged:
            if state.get_is_used(owner_id, slot_idx):
                return ""

        # 取引系カード（売る・買う）のトリガー判定
        is_trigger = False
        if card.get("name") in ["売る", "買う"]:
            if owner_id is not None:
                trigger_slot_idx = None
                if state.get_num_staged_cards(owner_id) > 0:
                    trigger_slot_idx = state.get_staged_card(owner_id, 0)
                
                if trigger_slot_idx is not None:
                    is_trigger = (slot_idx == trigger_slot_idx)
                else:
                    # まだ何もステージングされていない手札カードの中の「売る」「買う」
                    # 基本的に、現在手番のプレイヤーがメインフェイズでこれから使う場合は trigger になる可能性があるが、
                    # 手札に並んでいる時点（未選択）ではトリガーではないので False
                    is_trigger = False
            else:
                # owner_id がない場合はトリガーとみなす（安全側フォールバック）
                is_trigger = True

        # コンテキスト1: 取引モード（売買選択フェイズ、または売買カード仮置き中）
        if is_transaction_mode:
            if is_trigger:
                return ""
            price = card.get("price", 0)
            return f"¥{price}"

        if card.get("name") in ["売る", "買う"]:
            return ""

        # コンテキスト1: 売却モード（PHASE_SELL_SELECT や「売る」カード選択中）
        if is_sell_mode:
            price = card.get("price", 0)
            return f"¥{price}"

        cname = card.get("name", "")
        ctype = card.get("type")
        atk = card.get("attack_power", 0)
        df = card.get("defense_power", 0)
        reaction = card.get("reaction_type")
        timings = card.get("usage_timing", [])
        is_atk_plus = any("atk_plus" in str(t).lower() for t in timings)
        prefix = "+" if is_atk_plus else ""

        is_group = card.get("is_group_attack", False)
        acc = card.get("accuracy", 100)
        pct = f"{acc}%" if (is_group or acc < 100) else ""

        # コンテキスト2: 防御モード（PHASE_DEFENSE, PHASE_MIRACLE_DEFENSE）
        if is_defender:
            has_already_staged_other = len(staged_cids) > 0 and (not card or card.get("id") != staged_cids[0])

            # 現在の防御フェイズ（物理/奇跡）に応じた有効なリアクション判定
            is_valid_reaction = False
            if reaction:
                if phase == "PHASE_MIRACLE_DEFENSE":
                    if any("miracle_defence" in str(t).lower() for t in timings) or cname == "スーパーミラー":
                        is_valid_reaction = True
                elif phase == "PHASE_DEFENSE":
                    if cname in ["スーパーミラー", "壁", "反射剣", "乱弾武剣"]:
                        is_valid_reaction = True

            # 1枚目として出す場合のみリアクション表示
            if is_valid_reaction and not has_already_staged_other:
                if reaction == "reflect":
                    return "はね返す"
                elif reaction == "bounce":
                    return "弾く"
                elif reaction == "block":
                    return "阻止"

            # 防御ターンの場合は防御性能を表示
            if df > 0:
                return f"守{df}"

        # 仮置き場（staged_cards）の最後のカードが奇跡かを判定
        last_staged_card = staged_cards_info[-1] if staged_cards_info else None
        is_last_staged_miracle = last_staged_card and last_staged_card.get("type") == "miracle"

        # コンテキスト3: 特殊攻撃修飾カード・精霊系カード
        if "精霊の" in cname:
            if is_last_staged_miracle:
                return "消費0"
        elif cname in ["オーラ", "＜オーラ＞"]:
            return "2倍"
        elif cname in ["蜃気楼", "＜蜃気楼＞"]:
            return "全体"

        # コンテキスト4: 攻撃・攻撃プラス
        # 攻撃プラスフェイズ中は、プラス攻撃として使用可能なカードに +攻X を表示
        if phase == "PHASE_ATTACK_PLUS" and is_atk_plus and atk > 0:
            return f"{pct}{prefix}攻{atk}"

        # メインフェイズ（1枚目の単体攻撃選択中）
        if phase == "PHASE_MAIN":
            has_main_atk = any("main_atk" in str(t).lower() for t in timings)
            if has_main_atk and atk > 0:
                return f"{pct}{prefix}攻{atk}"
            elif df > 0:
                return f"守{df}"

        # デフォルトフォールバック
        if atk > 0:
            return f"{pct}{prefix}攻{atk}"
        if df > 0:
            return f"守{df}"

        return ""

    def get_card_info(card_id, slot_idx=None, owner_id=None, is_staged=False):
        if card_id == -1:
            return None
        card = cards_by_id.get(card_id)
        if card:
            info = {
                "id": card_id,
                "name": card.get("name"),
                "type": card.get("type"),
                "element": card.get("element", "none"),
                "attack_power": card.get("attack_power", 0),
                "defense_power": card.get("defense_power", 0),
                "price": card.get("price", 0),
                "id_str": card.get("id_str"),
                "usage_timing": card.get("usage_timing", []),
                "is_group_attack": card.get("is_group_attack", False),
                "accuracy": card.get("accuracy", 100),
                "reaction_type": card.get("reaction_type"),
                "text_color": get_element_text_color(card.get("element", "none")),
            }
            info["power_label"] = compute_card_power_label(info, slot_idx, owner_id, is_staged)
            return info
        return {
            "id": card_id,
            "name": f"未定義のカード ({card_id})",
            "type": "unknown",
            "id_str": "unknown",
            "usage_timing": [],
            "is_group_attack": False,
            "accuracy": 100,
            "reaction_type": None,
            "text_color": "#000000",
            "power_label": "",
        }

    curses_me_list = []
    for idx, val in enumerate(obs.get_curses_me()):
        if val > 0:
            curses_me_list.append(curse_names[idx])

    curses_opp_list = []
    for idx, val in enumerate(obs.get_curses_opp()):
        if val > 0:
            curses_opp_list.append(curse_names[idx])

    sick_me_idx = obs.get_sickness_me().index(1.0) if 1.0 in obs.get_sickness_me() else 0
    sick_opp_idx = obs.get_sickness_opp().index(1.0) if 1.0 in obs.get_sickness_opp() else 0

    guardian_me_idx = obs.get_guardian_me().index(1.0) if 1.0 in obs.get_guardian_me() else 0
    guardian_opp_idx = obs.get_guardian_opp().index(1.0) if 1.0 in obs.get_guardian_opp() else 0

    hand = []
    for idx, cid in enumerate(obs.get_hand_cards()):
        card_info = get_card_info(cid, slot_idx=idx, owner_id=player_id)
        if card_info:
            card_info["slot_idx"] = idx
            card_info["selected"] = state.get_is_used(player_id, idx)
            card_info["deployed"] = state.get_is_deployed(player_id, idx)

            deployed_order = -1
            if card_info["deployed"]:
                num_deployed = state.get_num_deployed_miracles(player_id)
                for k in range(num_deployed):
                    if state.get_deployed_miracle_order(player_id, k) == idx:
                        deployed_order = k
                        break
            card_info["deployed_order"] = deployed_order
        hand.append(card_info)
    staged = []
    for idx, cid in enumerate(obs.get_staged_cards()):
        if cid == -1:
            continue
        actual_slot_idx = state.get_staged_card(player_id, idx)
        staged.append(get_card_info(cid, slot_idx=actual_slot_idx, owner_id=player_id, is_staged=True))

    opp_id = 1 - player_id
    opp_hand = []
    for idx, cid in enumerate(obs.get_opponent_hand_cards()):
        if state.get_apparent_hand(opp_id, idx) == -1:
            continue
        card_info = get_card_info(cid, slot_idx=idx, owner_id=opp_id)
        if card_info:
            card_info["slot_idx"] = idx
            card_info["hidden"] = cid == 0 or cid == -1
            card_info["selected"] = state.get_is_used(opp_id, idx)
            card_info["deployed"] = state.get_is_deployed(opp_id, idx)
            deployed_order = -1
            if card_info["deployed"]:
                num_deployed = state.get_num_deployed_miracles(opp_id)
                for k in range(num_deployed):
                    if state.get_deployed_miracle_order(opp_id, k) == idx:
                        deployed_order = k
                        break
            card_info["deployed_order"] = deployed_order
        opp_hand.append(card_info)

    opp_staged = []
    for idx, cid in enumerate(obs.get_opponent_staged_cards()):
        if cid == -1:
            continue
        actual_slot_idx = state.get_staged_card(opp_id, idx)
        opp_staged.append(get_card_info(cid, slot_idx=actual_slot_idx, owner_id=opp_id, is_staged=True))

    # Convert legal actions
    legal_mask = obs.get_action_mask()
    legal_actions = []
    for idx, val in enumerate(legal_mask):
        if val > 0:
            action_name = ""
            desc = ""
            if idx <= 17:
                action_name = f"ACTION_SELECT_HAND_{idx}"
                hand_card_id = state.get_apparent_hand(player_id, idx)
                if hand_card_id != -1:
                    card_name = godfield_core.get_card_name(hand_card_id)
                    desc = f"手札の {card_name} を選択"
                else:
                    desc = f"手札スロット {idx} (空) を選択"
            elif idx == 18:
                action_name = "ACTION_TARGET_OPP"
                if state.current_phase == godfield_core.GamePhase.PHASE_MAIN:
                    desc = "相手を対象にしてカードを使用"
                elif state.current_phase in [
                    godfield_core.GamePhase.PHASE_BUY,
                    godfield_core.GamePhase.PHASE_BUY_SELECT_MIRROR,
                ]:
                    desc = "買う"
                else:
                    desc = "決定 / 承諾"
            elif idx == 19:
                action_name = "ACTION_TARGET_SELF"
                if state.current_phase == godfield_core.GamePhase.PHASE_MAIN:
                    desc = "自分を対象にしてカードを使用"
                elif state.current_phase in [
                    godfield_core.GamePhase.PHASE_BUY,
                ]:
                    desc = "買わない"
                elif state.current_phase in [
                    godfield_core.GamePhase.PHASE_BUY_SELECT_MIRROR,
                    godfield_core.GamePhase.PHASE_SELL_SELECT_MIRROR,
                    godfield_core.GamePhase.PHASE_SUNDRY_SELECT_MIRROR,
                ]:
                    if state.get_num_staged_cards(state.current_actor_id) > 0:
                        desc = "はね返す"
                    else:
                        desc = "受け入れる"
                else:
                    desc = "自分を対象 / 買わない / 受け入れる / はね返す / 確定"
            elif idx == 20:
                action_name = "ACTION_PRAY"
                desc = "祈る"
            elif idx == 21:
                action_name = "ACTION_DISCARD"
                desc = "捨てる"
            else:
                num = idx - 22
                action_name = f"ACTION_NUM_{num}"
                desc = f"両替数値: {num}"

            smart_label = compute_smart_action_label(idx, staged, state)
            legal_actions.append({"action_id": idx, "name": action_name, "description": desc, "smart_label": smart_label})

    # History log extraction
    raw_history = obs.get_history()
    event_log = []
    for ev in raw_history:
        if not hasattr(ev, "event_type") or ev.event_type == 0:
            continue
        fmt = format_event_log(ev, player_id)
        if fmt:
            event_log.append(fmt)

    staged_total_badge = compute_staged_total_badge(staged, player_id, state)

    return {
        "player_id": player_id,
        "hp_me": round(obs.hp_me * 100),
        "hp_opp": round(obs.hp_opp * 100) if "霧" not in curses_me_list else "？",
        "mp_me": round(obs.mp_me * 100),
        "mp_opp": round(obs.mp_opp * 100) if "霧" not in curses_me_list else "？",
        "money_me": round(obs.money_me * 100),
        "money_opp": round(obs.money_opp * 100) if "霧" not in curses_me_list else "？",
        "sickness_me": sickness_names[sick_me_idx],
        "sickness_opp": sickness_names[sick_opp_idx] if "霧" not in curses_me_list else "霧",
        "guardian_me": guardian_names[guardian_me_idx],
        "guardian_opp": guardian_names[guardian_opp_idx] if "霧" not in curses_me_list else "霧",
        "curses_me": curses_me_list,
        "curses_opp": curses_opp_list if "霧" not in curses_me_list else [],
        "hand": hand,
        "staged": staged,
        "staged_total_badge": staged_total_badge,
        "opponent_hand": opp_hand,
        "opponent_staged": opp_staged,
        "pending_card": get_card_info(obs.pending_card) if obs.pending_card != 0 else None,
        "legal_actions": legal_actions,
        "current_actor_id": state.current_actor_id,
        "current_phase": state.current_phase.name,
        "current_turn": state.current_turn,
        "is_done": state.is_done,
        "is_apocalypse": state.current_turn >= 300,
        "event_log": event_log,
        "history_count": obs.history_count,
    }


def get_current_observations_json():
    obs0 = godfield_core.get_observation(state, 0)
    obs1 = godfield_core.get_observation(state, 1)

    # Get element name safely
    elem_val = state.pending_attack_element
    elem_name = elem_val.name if hasattr(elem_val, "name") else str(elem_val)

    return json.dumps(
        {
            "p0_obs": serialize_observation(obs0, 0),
            "p1_obs": serialize_observation(obs1, 1),
            "current_actor_id": state.current_actor_id,
            "ai_enabled": ai_enabled,
            "current_phase": state.current_phase.name,
            "attacker_id": state.attacker_id,
            "defender_id": state.defender_id,
            "pending_attack_power": state.pending_attack_power,
            "pending_attack_element": elem_name,
        },
        ensure_ascii=False,
    )


@app.get("/")
async def get_index():
    file_path = os.path.join(project_root, "visualizer_web", "index_simple.html")
    with open(file_path, encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global ai_enabled
    await websocket.accept()

    # Reset game on connection
    reset_game()
    run_ai_steps()

    # Send initial state
    await websocket.send_text(get_current_observations_json())

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)

            if msg["type"] == "action":
                action_id = msg["action_id"]
                # Process player action
                godfield_core.step_game(state, godfield_core.ActionType(action_id))

                # Auto-advance
                while not state.is_done:
                    auto_action = godfield_core.get_single_legal_action(state)
                    if auto_action == -1:
                        break
                    godfield_core.step_game(state, godfield_core.ActionType(auto_action))

                # Run AI if it's AI's turn
                run_ai_steps()

            elif msg["type"] == "reset":
                seed = msg.get("seed")
                reset_game(seed)
                run_ai_steps()

            elif msg["type"] == "toggle_ai":
                ai_enabled = msg.get("ai_enabled", True)
                run_ai_steps()

            await websocket.send_text(get_current_observations_json())

    except Exception as e:
        print(f"WebSocket connection closed: {e}")


if __name__ == "__main__":
    print("Starting visualization server on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
