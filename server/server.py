from pathlib import Path
import sys

from fastapi import FastAPI
from pydantic import BaseModel

# =========================
# CONFIG
# =========================

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from server.routers import command as command_router
from server.routers import items as items_router
from server.routers import locations as locations_router
from server.routers import robot as robot_router
from server.routers import grid_map as grid_map_router
from server.routers import camera as camera_router
from server.routers import route as route_router
from server.routers import system as system_router

from server.chatbot import agent as chat_agent

# =========================
# FASTAPI APP
# =========================

app = FastAPI(
    title="Robot Communication API",
    description="Raspberry Pi와 ESP32 간 로봇 명령 및 상태 데이터 통신을 위한 API 서버",
    version="1.0.0"
)

app.include_router(command_router.router)
app.include_router(items_router.router)
app.include_router(locations_router.router)
app.include_router(robot_router.router)
app.include_router(grid_map_router.router)
app.include_router(camera_router.router)
app.include_router(route_router.router)
app.include_router(system_router.router)


# =========================
# CHATBOT API
# =========================

class ChatRequest(BaseModel):
    session_id: str
    message: str

@app.post("/chat")
def chat(request: ChatRequest):
    reply = chat_agent.run_agent_turn(request.session_id, request.message)
    return {"reply": reply}

# =========================
# SERVER RUNNER
# =========================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
