import time
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from server import state
from server.database import get_db
from server.replan_logic import MOVE_DELTA
from server.routers import home, obstacle, route


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
    # 상태가 바뀔 때만 서버 로그에 남긴다 (2초마다 같은 내용이 쌓이지 않게)
    if report.connected != esp32_link["connected"] or report.message != esp32_link["message"]:
        print(f"[esp32] connected={report.connected} {report.message}", flush=True)
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
@state.locked
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

    # 대기열도 비운다 (사람이 초기화한 것이므로 쌓여 있던 물품은 다시 인식해야 출발)
    for qr in getattr(state, "delivery_queue", []):
        cursor.execute(
            "UPDATE items SET status = 'waiting' WHERE qr_code = ? AND status = 'queued'",
            (qr,)
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
    state.delivery_queue = []
    state.next_start_at = None
    state.skip_detect = False
    state.nav_status, state.retry_count, state.probing = "idle", 0, False
    state.placed_at = time.time()          # 추가: 브리지가 이 값을 보고 halt를 푼다

    return {"status": "placed", "robot": [start[0] + 1, start[1] + 1]}


# ---------- 수동 이동 (챗봇 move_robot) ----------
# 배송과 같은 길로 보낸다: state.current_path -> /next-command -> robot_bridge.py -> ESP32
# 메카넘휠 횡이동이라 로봇은 항상 격자 북쪽을 바라본다.
#   forward = 위(북), backward = 아래(남), left = 왼쪽(서), right = 오른쪽(동) 으로 한 칸씩 평행이동
MANUAL_MAX_STEPS = 5


class ManualMoveRequest(BaseModel):
    direction: Literal["forward", "backward", "left", "right"]
    steps: int = Field(default=1, ge=1, le=MANUAL_MAX_STEPS)


def _reject(reason, message, **extra):
    return {"status": "rejected", "reason": reason, "message": message, **extra}


@router.post("/robot/manual-move")
@state.locked
def manual_move(req: ManualMoveRequest):
    """로봇을 지정한 방향으로 steps 칸 평행이동시킨다.

    로봇이 쉬고 있을 때만 받는다. 가는 칸 중 하나라도 격자 밖, 지도 장애물, 센서/사람이 막아 둔 칸이면 거절한다.
    받아들이면 바로 응답하고, 실제 이동은 브리지가 다음 /next-command 에서 가져가 실행한다.
    """
    link = get_esp32()
    if not link["connected"]:
        return _reject("robot_not_connected", link["message"] or "로봇(ESP32)이 연결되어 있지 않습니다.")

    if route.robot_busy() or getattr(state, "nav_status", None) in ("no_path", "manual_required"):
        return _reject("busy", "로봇이 배송·복귀 중이거나 대기 중인 작업이 있어 지금은 움직일 수 없습니다.")

    pos = obstacle._robot_pos()
    grid = obstacle._grid()             # 사람이 앱에서 표시한 칸도 장애물로 들어가 있다
    if pos is None or grid is None:
        return _reject("no_map", "로봇 위치나 격자 지도가 없습니다. 격자 탭에서 지도를 저장하세요.")

    rows, cols = len(grid), len(grid[0])
    dx, dy = MOVE_DELTA[req.direction]

    for i in range(1, req.steps + 1):
        x, y = pos[0] + dx * i, pos[1] + dy * i
        cell = [x + 1, y + 1]           # 응답 좌표는 robot/status 와 같이 1부터
        if not (0 <= x < cols and 0 <= y < rows):
            return _reject("out_of_grid", f"{i}번째 칸이 격자 밖이라 움직일 수 없습니다.", blocked_at=cell)
        if grid[y][x] != 0:
            return _reject("wall", f"{i}번째 칸이 벽(장애물)이라 움직일 수 없습니다.", blocked_at=cell)
        if (x, y) in obstacle.blocked_cells:
            return _reject("obstacle", f"{i}번째 칸에 센서가 감지한 장애물이 있어 움직일 수 없습니다.", blocked_at=cell)

    target = (pos[0] + dx * req.steps, pos[1] + dy * req.steps)

    # 목적지 없는 이동: 장애물을 만나면 다시 길을 찾지 않고 그 자리에서 멈춘다 (obstacle.report_obstacle)
    state.goal = None
    state.current_path = [req.direction] * req.steps + ["stop"]
    state.nav_status, state.retry_count, state.probing = "moving", 0, False
    obstacle._save_robot(pos, "moving")

    return {
        "status": "accepted",
        "direction": req.direction,
        "steps": req.steps,
        "from": [pos[0] + 1, pos[1] + 1],
        "to": [target[0] + 1, target[1] + 1],
        "message": "이동 명령을 로봇에 보냈습니다. 몇 초 안에 이동을 마칩니다.",
    }
