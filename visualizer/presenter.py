import godfield_core
from visualizer.constants import CARDS_BY_ID, CURSE_NAMES, GUARDIAN_NAMES, SICKNESS_NAMES
from visualizer.event_formatter import format_event_log

# 相手の非公開スロットを「裏向きのカード」として描くためのプレースホルダ。
# 実際のカードIDではなく、枠を表示するためだけに使う（表示可否は hidden で判定する）。
HIDDEN_CARD_PLACEHOLDER = 0


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

    has_sell = any(c and c.get("name") == "売る" for c in staged_cards)
    if (has_sell or "SELL" in phase):
        # 取引カード自体には値段がつかないので、先頭の「売る」「買う」は数えない。
        # 価格の表示はこの計算が唯一の実装（C++ 側は価格を保持しない）。
        total_price = sum(
            c.get("price", 0)
            for idx, c in enumerate(staged_cards)
            if c and not (idx == 0 and c.get("name") in ["売る", "買う"])
        )
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


def deployed_order_of(slot_idx, is_deployed):
    """展開済み奇跡の並び順を返します（未展開なら -1）。

    フロントエンドはこの値の降順で展開済みカードを並べます（古いものが右端）。

    エンジンは「どの順に展開したか」を保持していません（deploy_miracle は
    is_deployed のブール値を立てるだけ）。以前ここでは
    state.get_num_deployed_miracles() / get_deployed_miracle_order() を
    呼んでいましたが、これらは C++ 側に存在せず、奇跡を展開した瞬間に
    AttributeError で可視化サーバーが落ちていました。

    並び順にはスロット番号を使います。**真の展開順は意図的に追跡していません。**
    実装するなら InternalState に順序を持たせることになりますが、この構造体は
    環境の数だけ並ぶ（学習時は1024環境）ので、見た目だけの都合で大きくするのは
    割に合わないという判断です。順序が狂って見えることがあっても不具合では
    ありません。
    """
    return slot_idx if is_deployed else -1


def serialize_observation(obs, player_id, state):
    phase = state.current_phase.name
    staged_cids = [cid for cid in obs.get_staged_cards() if cid != -1]
    staged_cards_info = [CARDS_BY_ID.get(cid) for cid in staged_cids]
    has_sell_staged = any(c and c.get("name") == "売る" for c in staged_cards_info)
    is_sell_mode = phase in ["PHASE_SELL_SELECT", "PHASE_SELL_SELECT_MIRROR"] or has_sell_staged
    is_buy_mode = phase in ["PHASE_BUY", "PHASE_BUY_SELECT_MIRROR"]
    is_transaction_mode = is_sell_mode or is_buy_mode
    is_defender = phase in ["PHASE_DEFENSE", "PHASE_MIRACLE_DEFENSE"] and state.current_actor_id == player_id

    def compute_card_power_label(card, slot_idx=None, owner_id=None, is_staged=False):
        if not card:
            return ""

        if slot_idx is not None and owner_id is not None and not is_staged:
            if state.get_is_used(owner_id, slot_idx):
                return ""

        is_trigger = False
        if card.get("name") in ["売る", "買う"]:
            if owner_id is not None:
                trigger_slot_idx = None
                if state.get_num_staged_cards(owner_id) > 0:
                    trigger_slot_idx = state.get_staged_card(owner_id, 0)

                if trigger_slot_idx is not None:
                    is_trigger = (slot_idx == trigger_slot_idx)
                else:
                    is_trigger = False
            else:
                is_trigger = True

        if is_transaction_mode:
            if is_trigger:
                return ""
            price = card.get("price", 0)
            return f"¥{price}"

        if card.get("name") in ["売る", "買う"]:
            return ""

        if is_sell_mode:
            price = card.get("price", 0)
            return f"¥{price}"

        cname = card.get("name", "")
        atk = card.get("attack_power", 0)
        df = card.get("defense_power", 0)
        reaction = card.get("reaction_type")
        timings = card.get("usage_timing", [])
        is_atk_plus = any("atk_plus" in str(t).lower() for t in timings)
        prefix = "+" if is_atk_plus else ""

        is_group = card.get("is_group_attack", False)
        acc = card.get("accuracy", 100)
        pct = f"{acc}%" if (is_group or acc < 100) else ""

        if is_defender:
            has_already_staged_other = len(staged_cids) > 0 and (not card or card.get("id") != staged_cids[0])

            is_valid_reaction = False
            if reaction:
                if phase == "PHASE_MIRACLE_DEFENSE":
                    if any("miracle_defence" in str(t).lower() for t in timings) or cname == "スーパーミラー":
                        is_valid_reaction = True
                elif phase == "PHASE_DEFENSE":
                    if cname in ["スーパーミラー", "壁", "反射剣", "乱弾武剣"]:
                        is_valid_reaction = True

            if is_valid_reaction and not has_already_staged_other:
                if reaction == "reflect":
                    return "はね返す"
                elif reaction == "bounce":
                    return "弾く"
                elif reaction == "block":
                    return "阻止"

            if df > 0:
                return f"守{df}"

        last_staged_card = staged_cards_info[-1] if staged_cards_info else None
        is_last_staged_miracle = last_staged_card and last_staged_card.get("type") == "miracle"

        if "精霊の" in cname:
            if is_last_staged_miracle:
                return "消費0"
        elif cname in ["オーラ", "＜オーラ＞"]:
            return "2倍"
        elif cname in ["蜃気楼", "＜蜃気楼＞"]:
            return "全体"

        if phase == "PHASE_ATTACK_PLUS" and is_atk_plus and atk > 0:
            return f"{pct}{prefix}攻{atk}"

        if phase == "PHASE_MAIN":
            has_main_atk = any("main_atk" in str(t).lower() for t in timings)
            if has_main_atk and atk > 0:
                return f"{pct}{prefix}攻{atk}"
            elif df > 0:
                return f"守{df}"

        if atk > 0:
            return f"{pct}{prefix}攻{atk}"
        if df > 0:
            return f"守{df}"

        return ""

    def get_card_info(card_id, slot_idx=None, owner_id=None, is_staged=False):
        if card_id == -1:
            return None
        card = CARDS_BY_ID.get(card_id)
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
            curses_me_list.append(CURSE_NAMES[idx])

    curses_opp_list = []
    for idx, val in enumerate(obs.get_curses_opp()):
        if val > 0:
            curses_opp_list.append(CURSE_NAMES[idx])

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

            card_info["deployed_order"] = deployed_order_of(idx, card_info["deployed"])
        hand.append(card_info)

    staged = []
    for idx, cid in enumerate(obs.get_staged_cards()):
        if cid == -1:
            continue
        actual_slot_idx = state.get_staged_card(player_id, idx)
        staged.append(get_card_info(cid, slot_idx=actual_slot_idx, owner_id=player_id, is_staged=True))

    # 相手の手札はスロット順に並べる。
    #
    # 観測の opponent_hand_cards は「公開されているカードだけを左詰め」した配列
    # （スロット位置が漏れないようにするため）なので、その添字はスロット番号では
    # ない。以前はこれをスロット番号として使っており、公開カードが別のスロットに
    # 表示され、表示可否の判定も別のスロットを見ていた。
    #
    # ここはデバッグ用の表示なので、スロットとの対応は state から直接取る。
    # 見えてよいかどうかは観測と同じ条件（公開済み、または展開済み。ただし
    # 自分が霧なら公開済みは見えない）で判定する。
    opp_id = 1 - player_id
    is_me_fog = state.get_curses(player_id, godfield_core.CurseType.CURSE_FOG)
    opp_hand = []
    for idx in range(godfield_core.MAX_HAND_SIZE):
        if state.get_apparent_hand(opp_id, idx) == -1:
            continue
        visible = state.get_is_deployed(opp_id, idx) or (
            state.get_is_known_to_opp(opp_id, idx) and not is_me_fog
        )
        # 非公開のスロットも「裏向きのカード」として描くため、プレースホルダの
        # カードIDを渡す（get_card_info は -1 だと None を返して枠ごと消える）。
        # 見えるかどうかは cid ではなく visible で判定するので、公開された
        # カードID 0（両替）が裏向き扱いになることはない。
        cid = state.get_true_hand(opp_id, idx) if visible else HIDDEN_CARD_PLACEHOLDER
        card_info = get_card_info(cid, slot_idx=idx, owner_id=opp_id)
        if card_info:
            card_info["slot_idx"] = idx
            card_info["hidden"] = not visible
            card_info["selected"] = state.get_is_used(opp_id, idx)
            card_info["deployed"] = state.get_is_deployed(opp_id, idx)
            card_info["deployed_order"] = deployed_order_of(idx, card_info["deployed"])
        opp_hand.append(card_info)

    opp_staged = []
    for idx, cid in enumerate(obs.get_opponent_staged_cards()):
        if cid == -1:
            continue
        actual_slot_idx = state.get_staged_card(opp_id, idx)
        opp_staged.append(get_card_info(cid, slot_idx=actual_slot_idx, owner_id=opp_id, is_staged=True))

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
                elif state.current_phase in [godfield_core.GamePhase.PHASE_BUY, godfield_core.GamePhase.PHASE_BUY_SELECT_MIRROR]:
                    desc = "買う"
                else:
                    desc = "決定 / 承諾"
            elif idx == 19:
                action_name = "ACTION_TARGET_SELF"
                if state.current_phase == godfield_core.GamePhase.PHASE_MAIN:
                    desc = "自分を対象にしてカードを使用"
                elif state.current_phase in [godfield_core.GamePhase.PHASE_BUY]:
                    desc = "買わない"
                elif state.current_phase in [godfield_core.GamePhase.PHASE_BUY_SELECT_MIRROR, godfield_core.GamePhase.PHASE_SELL_SELECT_MIRROR, godfield_core.GamePhase.PHASE_SUNDRY_SELECT_MIRROR]:
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
        "sickness_me": SICKNESS_NAMES[sick_me_idx],
        "sickness_opp": SICKNESS_NAMES[sick_opp_idx] if "霧" not in curses_me_list else "霧",
        "guardian_me": GUARDIAN_NAMES[guardian_me_idx],
        "guardian_opp": GUARDIAN_NAMES[guardian_opp_idx] if "霧" not in curses_me_list else "霧",
        "curses_me": curses_me_list,
        "curses_opp": curses_opp_list if "霧" not in curses_me_list else [],
        "hand": hand,
        "staged": staged,
        "staged_total_badge": staged_total_badge,
        "opponent_hand": opp_hand,
        "opponent_staged": opp_staged,
        "pending_card": get_card_info(state.pending_attack_source_id) if state.pending_attack_source_id != godfield_core.CARD_EMPTY else (get_card_info(opp_staged[0]["id"]) if state.current_phase.name == "PHASE_BUY" and state.current_actor_id == player_id and len(opp_staged) > 0 else None),
        "legal_actions": legal_actions,
        "current_actor_id": state.current_actor_id,
        "current_phase": state.current_phase.name,
        "current_turn": state.current_turn,
        "is_done": state.is_done,
        "is_apocalypse": state.current_turn >= 300,
        "event_log": event_log,
        "history_count": state.history_count,
    }
