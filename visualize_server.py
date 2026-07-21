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

    def get_card_info(card_id):
        if card_id == -1:
            return None
        card = cards_by_id.get(card_id)
        if card:
            # Add element details
            return {
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
            }
        return {
            "id": card_id,
            "name": f"未定義のカード ({card_id})",
            "type": "unknown",
            "id_str": "unknown",
            "usage_timing": [],
            "is_group_attack": False,
            "accuracy": 100,
            "reaction_type": None,
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
        card_info = get_card_info(cid)
        if card_info:
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
    staged = [get_card_info(cid) for cid in obs.get_staged_cards() if cid != -1]

    opp_id = 1 - player_id
    opp_hand = []
    for idx, cid in enumerate(obs.get_opponent_hand_cards()):
        if state.get_apparent_hand(opp_id, idx) == -1:
            continue
        if cid != 0:
            card_info = get_card_info(cid)
            if card_info:
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
        else:
            opp_hand.append({"hidden": True, "name": "？", "type": "hidden"})

    opp_staged = [get_card_info(cid) for cid in obs.get_opponent_staged_cards() if cid != -1]

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
                # Context sensitive description
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
                    godfield_core.GamePhase.PHASE_BUY_SELECT_MIRROR,
                ]:
                    desc = "断る"
                else:
                    desc = "自分を対象 / 断る / 確定"
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

            legal_actions.append({"action_id": idx, "name": action_name, "description": desc})

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
        "opponent_hand": opp_hand,
        "opponent_staged": opp_staged,
        "pending_card": get_card_info(obs.pending_card) if obs.pending_card != 0 else None,
        "legal_actions": legal_actions,
        "current_actor_id": state.current_actor_id,
        "current_phase": state.current_phase.name,
        "current_turn": state.current_turn,
        "is_done": state.is_done,
        "is_apocalypse": state.current_turn >= 300,
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
