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
from godfield_rl.agents.heuristic_agent import get_ai_action
from godfield_rl.opponents import make_opponent, FrozenOpponent
from sb3_contrib import MaskablePPO
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

# Setup Opponents
opponents = {
    "heuristic": make_opponent("heuristic"),
    "random": make_opponent("random"),
}
try:
    mlp_model = MaskablePPO.load("assets/models/best_mlp_gen50.zip")
    opponents["mlp_gen50"] = FrozenOpponent(mlp_model)
    current_opponent_type = "mlp_gen50"
except Exception as e:
    print(f"Could not load mlp_gen50 model: {e}")
    current_opponent_type = "heuristic"


def reset_game(seed=None):
    global state
    if seed is None:
        seed = random.randint(0, 100000)
    env_pool.reset(seed)
    state = env_pool.get_state(0)


async def run_ai_steps():
    # If it is Player 1's turn and AI is enabled, auto-step Player 1
    while not state.is_done and state.current_actor_id == 1 and ai_enabled:
        opponent = opponents[current_opponent_type]
        
        if current_opponent_type in ["heuristic", "random"]:
            ai_act = opponent.act(state)
        else:
            # FrozenOpponent (PPO) expects numpy arrays
            obs_flat = env_pool.get_observations()
            obs_flat = obs_flat.reshape(1, -1)
            features_dim = godfield_core.OBSERVATION_FEATURE_SIZE
            action_dim = godfield_core.ACTION_SPACE_SIZE
            
            obs_tensor = obs_flat[:, :features_dim - action_dim]
            masks_tensor = obs_flat[:, features_dim - action_dim : features_dim]
            ai_act = opponent.act(obs_tensor, masks_tensor)[0]
            
        if ai_act is None:
            break
        godfield_core.step_game(state, godfield_core.ActionType(ai_act))
        await asyncio.sleep(0)

        # Auto-advance
        while not state.is_done:
            auto_action = godfield_core.get_single_legal_action(state)
            if auto_action == -1:
                break
            godfield_core.step_game(state, godfield_core.ActionType(auto_action))
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

                # Auto-advance
                while not state.is_done:
                    auto_action = godfield_core.get_single_legal_action(state)
                    if auto_action == -1:
                        break
                    godfield_core.step_game(state, godfield_core.ActionType(auto_action))
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
