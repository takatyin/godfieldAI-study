import asyncio
import json
import time
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from godfield_rl.env_wrapper import GodFieldVectorEnv
from godfield_rl.agents.random_agent import RandomAgent

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# We will run 1 environment for visualization
env = GodFieldVectorEnv(num_envs=1)
agent_p0 = RandomAgent(env.action_space)
agent_p1 = RandomAgent(env.action_space)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # Reset environment
    obs, _ = env.reset()
    
    try:
        while True:
            # 1. Send current state to the client
            state_json = env.core_env.get_state_json(0)
            await websocket.send_text(state_json)
            
            # Wait for client to request next step (or just auto-step)
            data = await websocket.receive_text()
            if data == "step":
                # Both agents take an action
                action_p0 = agent_p0.predict_batch(obs)
                # env.step handles action_p1 internally as random for now in the wrapper
                # Wait, our wrapper generates random actions for p1. 
                # Let's just use the wrapper's built-in step.
                obs, rewards, dones, _, _ = env.step(action_p0)
                
                # Small delay to make it viewable if it's auto-stepping
                await asyncio.sleep(0.1)
                
    except Exception as e:
        print(f"WebSocket connection closed: {e}")

if __name__ == "__main__":
    print("Starting visualization server on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
