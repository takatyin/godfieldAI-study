import asyncio
import glob
import json
import os
import random

import uvicorn
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

import godfield_core
from godfield_rl.evaluation import load_policy, split_observation
from godfield_rl.opponents import make_opponent
from visualizer.constants import CARDS, project_root
from visualizer.presenter import serialize_observation

app = FastAPI()
app.mount("/assets", StaticFiles(directory="assets"), name="assets")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize C++ game logic
godfield_core.init_game_logic(CARDS)

# Shared game state
env_pool = godfield_core.EnvPool(1)
state = None
ai_enabled = True  # Player 1 is controlled by AI by default

# 対戦相手。人手の方策は常に使え、学習済みモデルは assets/models にあるものを拾う。
#
# 学習済みモデルは観測レイアウトが変わると読めなくなる（HISTORY_LENGTH を変えた等）。
# 読めないものは黙って落として人手の方策で遊べるようにしてある。
opponents: dict[str, object] = {
    "strategic": make_opponent("strategic"),
    "heuristic": make_opponent("heuristic"),
    "random": make_opponent("random"),
}
current_opponent_type = "strategic"

for path in sorted(glob.glob(os.path.join(project_root, "assets", "models", "*.zip"))):
    name = os.path.splitext(os.path.basename(path))[0]
    try:
        # 人間と対戦させるので、学習時（探索のために確率的に選ぶ）と違い決定的に指させる
        opponents[name] = load_policy(path, deterministic=True)
        current_opponent_type = name
    except Exception as exc:
        print(f"[skip] {name} は読み込めませんでした: {str(exc).splitlines()[0]}")

print(f"対戦相手: {', '.join(opponents)}（既定 {current_opponent_type}）")


def reset_game(seed=None):
    global state
    if seed is None:
        seed = random.randint(0, 100000)
    env_pool.reset(seed)
    state = env_pool.get_state(0)


def opponent_action(opponent) -> int:
    """相手方策に1手選ばせます。

    相手方策はすべて Opponent（act(観測, マスク) のバッチ受け取り）で統一されています。
    以前は heuristic / random だけ act(state) で呼んでおり、選ぶと TypeError で
    落ちていました（godfield_rl.agents.heuristic_agent という別実装が残っていた名残）。
    """
    obs, masks = split_observation(env_pool.get_observations(), 1)
    return int(opponent.act(obs, masks)[0])


async def run_ai_steps():
    # If it is Player 1's turn and AI is enabled, auto-step Player 1
    while not state.is_done and state.current_actor_id == 1 and ai_enabled:
        ai_act = opponent_action(opponents[current_opponent_type])
        godfield_core.step_game(state, godfield_core.ActionType(ai_act))
        env_pool.set_state(0, state)
        await asyncio.sleep(0)

        while not state.is_done:
            auto_action = godfield_core.get_single_legal_action(state)
            if auto_action == -1:
                break
            godfield_core.step_game(state, godfield_core.ActionType(auto_action))
            env_pool.set_state(0, state)
            await asyncio.sleep(0)


def get_current_observations_json():
    obs0 = godfield_core.get_observation(state, 0)
    obs1 = godfield_core.get_observation(state, 1)

    # Get element name safely
    elem_val = state.pending_attack_element
    elem_name = elem_val.name if hasattr(elem_val, "name") else str(elem_val)

    return json.dumps(
        {
            "p0_obs": serialize_observation(obs0, 0, state),
            "p1_obs": serialize_observation(obs1, 1, state),
            "current_actor_id": state.current_actor_id,
            "ai_enabled": ai_enabled,
            "available_opponents": list(opponents.keys()),
            "current_opponent": current_opponent_type,
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
    await run_ai_steps()

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
                env_pool.set_state(0, state)

                # Auto-advance
                while not state.is_done:
                    auto_action = godfield_core.get_single_legal_action(state)
                    if auto_action == -1:
                        break
                    godfield_core.step_game(state, godfield_core.ActionType(auto_action))
                    env_pool.set_state(0, state)
                    await asyncio.sleep(0)

                # Run AI if it's AI's turn
                await run_ai_steps()

            elif msg["type"] == "reset":
                seed = msg.get("seed")
                reset_game(seed)
                await run_ai_steps()

            elif msg["type"] == "toggle_ai":
                ai_enabled = msg.get("ai_enabled", True)
                await run_ai_steps()

            elif msg["type"] == "change_opponent":
                new_opp = msg.get("opponent")
                if new_opp in opponents:
                    global current_opponent_type
                    current_opponent_type = new_opp
                    await run_ai_steps()

            await websocket.send_text(get_current_observations_json())

    except Exception as e:
        print(f"WebSocket connection closed: {e}")


if __name__ == "__main__":
    print("Starting visualization server on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
