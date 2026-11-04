from pathlib import Path
import sys

from fastapi import FastAPI
from pydantic import BaseModel
import os
import secrets
from fastapi import Request, Security
from fastapi.responses import JSONResponse
from fastapi.security.api_key import APIKeyHeader

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
from server.routers import obstacle as obstacle_router
from server.routers import camera as camera_router
from server.routers import route as route_router
from server.routers import system as system_router
from server.routers.mobile_app import setup_mobile
from server.chatbot import agent as chat_agent

# =========================
# FASTAPI APP
# =========================
ENABLE_DOCS = os.environ.get("TAESULA_ENABLE_DOCS") == "1"

# Swagger에 Authorize 버튼을 띄우기 위한 선언 (실제 검사는 아래 미들웨어가 함)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

app = FastAPI(
    title="Robot Communication API",
    description="Raspberry Pi와 ESP32 간 로봇 명령 및 상태 데이터 통신을 위한 API 서버",
    version="1.0.0",
    docs_url="/docs" if ENABLE_DOCS else None,
    redoc_url=None,
    openapi_url="/openapi.json" if ENABLE_DOCS else None,
    dependencies=[Security(api_key_header)],
)

# =========================
# 외부(Funnel) 요청 인증
# =========================

API_KEY = os.environ.get("TAESULA_API_KEY", "")
PUBLIC_EXACT = {"/"} | ({"/docs", "/openapi.json"} if ENABLE_DOCS else set())
PUBLIC_PREFIXES = ("/app",)               # 앱 화면 파일은 키 없이 열려야 함
LOCAL_PROXY_HOSTS = {"127.0.0.1", "::1"}  # Funnel이 프록시하는 출발지
@app.middleware("http")
async def require_api_key_for_external(request: Request, call_next):
    client_host = request.client.host if request.client else ""
    path = request.url.path
    is_external = client_host in LOCAL_PROXY_HOSTS
    is_public = path in PUBLIC_EXACT or path.startswith(PUBLIC_PREFIXES)
    if is_external and not is_public:
        key = request.headers.get("x-api-key") or request.query_params.get("key") or ""
        if not API_KEY or not secrets.compare_digest(key.encode("utf-8"), API_KEY.encode("utf-8")):
            return JSONResponse({"detail": "인증이 필요합니다."}, status_code=401)
    return await call_next(request)

# 모바일 앱 제공: http://<서버 IP>:8000/app/
setup_mobile(app, BASE_DIR)

app.include_router(command_router.router)
app.include_router(items_router.router)
app.include_router(locations_router.router)
app.include_router(robot_router.router)
app.include_router(grid_map_router.router)
app.include_router(obstacle_router.router)
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
