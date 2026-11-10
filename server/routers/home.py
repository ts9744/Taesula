"""배송을 마친 로봇을 시작점(홈)으로 되돌리는 기능.

홈 위치
  - 앱/GUI 격자 탭에서 저장하는 '시작점'이 grid_map.raw_grid 에 값 2 로 들어 있다. 그 칸을 홈으로 쓴다.

흐름
  - /route 로 배송 시작            -> state.mission = "deliver"
  - 목적지 도착(/command/done)      -> 물품 arrived, AUTO_RETURN_DELAY_SEC 뒤 복귀 예약 (state.return_at)
  - /next-command 가 불릴 때마다    -> maybe_auto_return() 이 예약 시간이 지났으면 복귀 경로를 대기열에 넣음
  - POST /robot/return-home        -> 예약을 기다리지 않고 바로 복귀
  - 홈 도착(/command/done)          -> state.mission = None, state.goal = None

복귀 중에는 state.goal 이 홈이므로, 장애물 재탐색(/robot/obstacle, try_retry, /robot/resume)이
그대로 홈을 목표로 동작한다.
"""
import json
import time

from fastapi import APIRouter

from algorithm.astar import a_star
from server import state
from server.database import get_db, load_grid_from_db
from server.replan_logic import MOVE_DELTA, plan_with_release
from server.routers import obstacle
from server.routers.route import path_to_commands, start_delivery


router = APIRouter()

# 목적지 도착 후 이 시간(초)만큼 기다렸다가 자동 복귀 (물건 내리는 시간). None 이면 자동 복귀 안 함.
AUTO_RETURN_DELAY_SEC = 10.0

# 대기열 물품: 로봇이 시작점에 돌아온 뒤 이 시간(초)만큼 기다렸다가 출발 (물건 싣는 시간)
QUEUE_START_DELAY_SEC = 10.0


def find_start_cells():
    """raw_grid 에서 시작점(값 2) 칸을 모두 찾는다. [(x, y), ...] 0부터 시작, 행 우선 순서."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT raw_grid FROM grid_map WHERE id = 1")
    row = cursor.fetchone()
    conn.close()

    if not row or row[0] is None:
        return []

    raw_grid = json.loads(row[0])
    return [(x, y) for y, cells in enumerate(raw_grid) for x, value in enumerate(cells) if value == 2]


def load_home():
    """시작점(홈) 칸 (x, y) 0부터 시작. 없으면 None.

    앱(grid.js)과 GUI(gridMap.py)는 지도를 불러올 때 값 2 중 '마지막' 칸을 시작점으로 쓰고,
    저장할 때 그 칸을 robot_status 에 넣는다. 같은 규칙으로 마지막 칸을 쓴다.
    """
    cells = find_start_cells()
    return cells[-1] if cells else None


def schedule_return(now=None):
    """목적지 도착 시 command_done 이 부른다."""
    if AUTO_RETURN_DELAY_SEC is None:
        state.return_at = None
        return
    now = time.time() if now is None else now
    state.return_at = now + AUTO_RETURN_DELAY_SEC


def maybe_auto_return(now=None):
    """/next-command 맨 앞에서 부른다. 복귀 예약 시간이 지났으면 복귀를 시작한다."""
    return_at = getattr(state, "return_at", None)
    if return_at is None:
        return
    now = time.time() if now is None else now
    if now < return_at:
        return
    if state.current_path:          # 그 사이 새 명령이 들어왔으면 복귀하지 않는다
        state.return_at = None
        return
    start_return()


def start_return():
    state.return_at = None

    home = load_home()
    if home is None:
        return {
            "status": "error",
            "message": "home not set",
            "detail": "격자 지도에 시작점이 없습니다. 격자 탭에서 시작점을 지정해 저장하세요.",
        }

    pos = obstacle._robot_pos()
    grid = load_grid_from_db()
    if pos is None or grid is None:
        return {"status": "error", "message": "robot status or grid map not found"}

    pos = tuple(pos)
    rows, cols = len(grid), len(grid[0])
    if not (0 <= home[0] < cols and 0 <= home[1] < rows):
        return {"status": "error", "message": "home is out of grid range", "home": list(home)}

    if pos == home:
        state.mission = None
        state.goal = None
        return {"status": "already_home", "home": list(home)}

    state.goal = home
    state.mission = "return"
    state.current_item_qr = None

    # blocked_cells(센서로 막아 둔 칸)를 피해서 경로를 찾는다. release_count=0 이면 아무것도 풀지 않음.
    plan = plan_with_release(
        grid, pos, home, obstacle.blocked_cells, a_star,
        lambda p: path_to_commands(p, "north"), 0,
    )

    if plan is None:
        # 길이 없으면 장애물 대기 흐름(try_retry)에 맡긴다. goal 이 홈이라 그대로 재시도된다.
        state.current_path = []
        state.nav_status, state.retry_count, state.probing = "no_path", 0, False
        state.retry_at = time.time() + obstacle.RETRY_SEC
        obstacle._save_robot(pos, "obstacle_detected")
        return {
            "status": "no_path",
            "start": list(pos),
            "home": list(home),
            "retry_in_sec": obstacle.RETRY_SEC,
        }

    state.current_path = plan["commands"].copy()
    state.nav_status, state.retry_count, state.probing = "moving", 0, False
    obstacle._save_robot(pos, "moving")

    return {
        "status": "returning",
        "start": list(pos),
        "home": list(home),
        "path": plan["path"],
        "command_path": plan["commands"],
    }


def _queue_item_back_to_waiting(qr):
    conn = get_db()
    conn.execute("UPDATE items SET status = 'waiting' WHERE qr_code = ? AND status = 'queued'", (qr,))
    conn.commit()
    conn.close()


def maybe_start_queued(now=None):
    """/next-command 맨 앞에서 부른다. 대기열 물품을 시작점에서 순서대로 출발시킨다.

    1. 이전 배송·도착 후 대기·복귀가 모두 끝날 때까지 기다린다.
    2. 로봇이 시작점이 아니면 먼저 시작점으로 복귀시킨다. (자동 복귀를 꺼 둔 경우 등)
    3. 시작점에 도착하면 QUEUE_START_DELAY_SEC 동안 물건을 싣고, 다음 물품 배송을 시작한다.
    """
    with state.lock:
        if not state.delivery_queue:
            state.next_start_at = None
            return

        busy = (
            getattr(state, "mission", None) is not None
            or getattr(state, "return_at", None) is not None
            or bool(state.current_path)
            or getattr(state, "pending_move", None) is not None
        )
        if busy:
            state.next_start_at = None
            return

        home = load_home()
        pos = obstacle._robot_pos()
        if home is not None and pos is not None and tuple(pos) != tuple(home):
            start_return()
            return

        now = time.time() if now is None else now
        if state.next_start_at is None:
            state.next_start_at = now + QUEUE_START_DELAY_SEC
            return
        if now < state.next_start_at:
            return

        state.next_start_at = None
        while state.delivery_queue:
            qr = state.delivery_queue.pop(0)
            result = start_delivery(qr)
            if result.get("message") == "route found":
                print(f"[queue] {qr} 출발 (남은 대기 {len(state.delivery_queue)}개)", flush=True)
                return
            # 경로가 없거나 물품이 삭제된 경우: 대기로 되돌리고 다음 물품으로
            print(f"[queue] {qr} 출발 실패: {result.get('message')}", flush=True)
            _queue_item_back_to_waiting(qr)


@router.post("/robot/return-home")
@state.locked
def return_home():
    """앱/챗봇에서 '복귀'를 눌렀을 때. 자동 복귀 예약을 기다리지 않고 바로 시작한다."""
    # mission 은 /command/done 에서 도착이 확정돼야 None 이 된다.
    # 마지막 이동이 나간 직후(남은 경로가 stop 뿐)에도 DB 위치는 아직 이전 칸이므로 여기서 막아야 한다.
    mission = getattr(state, "mission", None)
    if mission == "deliver" or getattr(state, "pending_move", None) in MOVE_DELTA:
        return {"status": "busy", "message": "배송 중에는 복귀할 수 없습니다."}
    if mission == "return" and getattr(state, "nav_status", None) == "moving":
        return {"status": "busy", "message": "이미 시작점으로 복귀 중입니다."}
    return start_return()


@router.get("/robot/home")
def get_home():
    cells = find_start_cells()
    home = cells[-1] if cells else None
    return_at = getattr(state, "return_at", None)
    return {
        "home": None if home is None else [home[0] + 1, home[1] + 1],   # robot/status 와 같이 1부터
        "start_cells": [[x + 1, y + 1] for x, y in cells],             # 2개 이상이면 격자 탭에서 다시 저장 필요
        "mission": getattr(state, "mission", None),                    # deliver / return / None
        "auto_return_in_sec": None if return_at is None else max(0, round(return_at - time.time())),
    }
