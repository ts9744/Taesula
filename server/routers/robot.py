import time

from fastapi import APIRouter
from pydantic import BaseModel

from server import state
from server.database import get_db
from server.routers import home


router = APIRouter()


@router.get("/robot/status")
def get_robot_status():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id, current_x, current_y, status FROM robot_status")
    row = cursor.fetchone()

    conn.close()

    if row:
        return {
            "id": row[0],
            "current_x": row[1],
            "current_y": row[2],
            "status": row[3]
        }

    return {"message": "robot status not found"}


@router.put("/robot/status")
def update_robot_status(current_x: int, current_y: int, status: str):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM robot_status WHERE id=1")
    row = cursor.fetchone()

    if row:
        cursor.execute(
            "UPDATE robot_status SET current_x=?, current_y=?, status=? WHERE id=1",
            (current_x, current_y, status)
        )
    else:
        cursor.execute(
            "INSERT INTO robot_status (id, current_x, current_y, status) VALUES (1, ?, ?, ?)",
            (current_x, current_y, status)
        )

    conn.commit()
    conn.close()

    return {
        "message": "robot status updated",
        "current_x": current_x,
        "current_y": current_y,
        "status": status
    }


# ---------- ESP32 연결 상태 (robot_bridge.py 의 heartbeat 가 2초마다 보고) ----------
ESP32_STALE_SEC = 6.0   # 이 시간 동안 보고가 없으면 브리지가 꺼진 것으로 본다 (heartbeat 2초 x 3)

esp32_link = {"connected": False, "message": "", "reported_at": None}


class Esp32Report(BaseModel):
    connected: bool
    message: str = ""


@router.post("/robot/esp32")
def report_esp32(report: Esp32Report):
    esp32_link["connected"] = report.connected
    esp32_link["message"] = report.message
    esp32_link["reported_at"] = time.time()
    return {"message": "esp32 status updated"}


@router.get("/robot/esp32")
def get_esp32():
    reported_at = esp32_link["reported_at"]

    if reported_at is None or time.time() - reported_at > ESP32_STALE_SEC:
        return {
            "connected": False,
            "bridge_running": False,
            "message": "로봇 브리지(robot_bridge.py)가 실행 중이 아닙니다.",
        }

    return {
        "connected": esp32_link["connected"],
        "bridge_running": True,
        "message": esp32_link["message"],
    }


# ---------- 로봇을 시작점에 두기 ----------
@router.post("/robot/place-at-start")
def place_at_start():
    """사람이 로봇을 시작점에 직접 갖다 놓았을 때.

    DB 위치를 시작점으로 바꾸고, 서버 메모리에 남은 이동 상태(진행 중인 이동, 남은 경로, 복귀 예약)를 모두 비운다.
    비우지 않으면 다음 /next-command 에서 commit_pending_move() 가 끊긴 이동을 끝난 것으로 보고 위치를 또 옮긴다.
    """
    start = home.load_home()
    if start is None:
        return {
            "status": "error",
            "message": "home not set",
            "detail": "격자 지도에 시작점이 없습니다. 격자 탭에서 시작점을 지정해 저장하세요.",
        }

    conn = get_db()
    cursor = conn.cursor()

    # 배송 도중에 끊긴 물품은 다시 대기 상태로
    item_qr = getattr(state, "current_item_qr", None)
    if item_qr:
        cursor.execute(
            "UPDATE items SET status = 'waiting' WHERE qr_code = ? AND status = 'moving'",
            (item_qr,)
        )

    cursor.execute(
        "UPDATE robot_status SET current_x = ?, current_y = ?, status = 'idle' WHERE id = 1",
        (start[0] + 1, start[1] + 1)
    )
    conn.commit()
    conn.close()

    state.current_command = "stop"
    state.current_path = []
    state.current_steps = 0
    state.current_item_qr = None
    state.pending_move = None
    state.pending_steps = 1
    state.goal = None
    state.mission = None
    state.return_at = None
    state.skip_detect = False
    state.nav_status, state.retry_count, state.probing = "idle", 0, False

    return {"status": "placed", "robot": [start[0] + 1, start[1] + 1]}
