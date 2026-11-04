""" 흐름
  - /next-command 가 이동 명령을 내보낼 때 mark_dispatched() 를 부른다 (command.py 에서 호출).
      -> 이 이동을 '진행 중'으로 기록하고, ESP32 에 detect_cm / known_cm 를 돌려준다.
  - 다음 /next-command 가 오면 commit_pending_move() 가 '앞 이동이 끝났다'고 보고 DB 위치를 한 칸 옮긴다.
  - ESP32 가 지도에 없던 장애물을 확정하면 POST /robot/obstacle 로 보고한다.
      * 장애물이 다음 칸 안  : ESP32 가 출발 칸 중앙으로 되돌아온 상태(completed=false) -> 위치 그대로 재탐색
      * 장애물이 그 너머     : ESP32 가 이번 이동을 끝까지 마친 상태(completed=true)  -> 도착 칸에서 재탐색
"""
from fastapi import APIRouter
from pydantic import BaseModel

from algorithm.astar import a_star
from server import state
from server.database import get_db, load_grid_from_db
from server.routers.route import path_to_commands
from server.replan_logic import (
    replan, MOVE_DELTA, DETECT_CM,
    distance_to_known_cm, locate_obstacle, in_known_map,
)

router = APIRouter()
blocked_cells = {}          # {(x, y): 감지 시각}  - 서버 메모리에만 저장
HAS_SENSOR = ("forward", "left", "right")   # 앞/왼쪽/오른쪽 센서만 있다. 뒤로 갈 때는 감지 안 함


class ObstacleReport(BaseModel):
    direction: str            # 가던 방향 (forward/left/right)
    distance_cm: float        # 그 방향 센서 값
    moved_cm: float = 0.0     # 그때까지 이동한 거리 (출발 칸 중앙 기준)
    completed: bool = False   # True: 묶음 이동(steps칸)을 끝까지 마쳐서 도착 칸 중앙에 서 있음
    cells_done: int = 0       # completed=False 일 때: 묶음 중 끝낸 칸 수 (그 칸 중앙에 서 있음). 한 칸짜리면 0


# ---------- DB 위치 읽기/쓰기 (DB 는 1부터, 격자는 0부터) ----------
def _robot_pos():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT current_x, current_y FROM robot_status WHERE id=1")
    row = cur.fetchone()
    conn.close()
    return None if not row else (row[0] - 1, row[1] - 1)


def _save_robot(pos, status):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE robot_status SET current_x=?, current_y=?, status=? WHERE id=1",
        (pos[0] + 1, pos[1] + 1, status),
    )
    conn.commit()
    conn.close()


# ---------- command.py 의 /next-command 가 부르는 두 함수 ----------
def commit_pending_move():
    """직전에 내보낸 이동(steps 칸)이 무사히 끝난 것으로 보고 위치를 steps 칸 옮긴다."""
    cmd = getattr(state, "pending_move", None)
    steps = max(1, getattr(state, "pending_steps", 1))
    state.pending_move = None
    state.pending_steps = 1
    pos = _robot_pos()
    d = MOVE_DELTA.get(cmd)
    if pos is not None and d is not None:
        _save_robot((pos[0] + d[0] * steps, pos[1] + d[1] * steps), "moving")


def mark_dispatched(cmd, steps=1):
    """이동을 '진행 중'으로 기록하고, /next-command 응답에 덧붙일 값을 돌려준다.

    detect_cm : 장애물 탐지 범위(cm). 0 이면 이번 이동은 감지하지 않는다.
    known_cm  : 가는 방향의 지도 장애물/벽까지 예상 거리(cm). 없으면 None.
    """
    state.pending_move = cmd if cmd in MOVE_DELTA else None
    state.pending_steps = max(1, steps)
    extras = {"detect_cm": 0, "known_cm": None}

    if cmd == "stop":  # 경로 끝(도착): 상태를 idle 로 되돌림
        pos = _robot_pos()
        if pos is not None:
            _save_robot(pos, "idle")
        return extras

    if getattr(state, "skip_detect", False):      # 지도와 어긋난 오탐이었던 이동을 다시 시도하는 중
        state.skip_detect = False
        return extras

    if cmd in HAS_SENSOR:
        extras["detect_cm"] = DETECT_CM
        pos, grid = _robot_pos(), load_grid_from_db()
        if pos is not None and grid is not None:
            extras["known_cm"] = distance_to_known_cm(grid, pos, cmd)   # 묶음 시작 칸 기준
    return extras


# ---------- ESP32 가 장애물을 보고하는 곳 ----------
@router.post("/robot/obstacle")
def report_obstacle(r: ObstacleReport):
    move = r.direction if r.direction in MOVE_DELTA else getattr(state, "pending_move", None)
    steps = max(1, getattr(state, "pending_steps", 1))
    state.pending_move = None
    state.pending_steps = 1

    pos, goal, grid = _robot_pos(), getattr(state, "goal", None), load_grid_from_db()
    if pos is None or goal is None or grid is None or move not in MOVE_DELTA:
        state.current_command = "stop"
        return {"status": "ignored", "reason": "위치/목적지/격자 정보 없음"}

    n, cell = locate_obstacle(pos, move, r.distance_cm, r.moved_cm)
    d = MOVE_DELTA[move]
    k = steps if r.completed else max(0, min(r.cells_done, steps))
    arrived = (pos[0] + d[0] * k, pos[1] + d[1] * k)   # 지금 서 있는 칸 (묶음 전체를 마쳤거나, 중간 칸)

    # 이미 지도에 있는 장애물/벽으로 계산되면 오탐이다: 막힌 칸으로 만들지 않고 그 이동을 다시 시도한다
    if in_known_map(grid, cell):
        state.skip_detect = True
        _save_robot(arrived, "moving")
        if not r.completed:                       # 남은 칸을 다시 시도
            for _ in range(steps - k):
                state.current_path.insert(0, move)
        return {"status": "ignored", "reason": "지도에 있는 장애물/벽", "cell": list(cell)}

    # 지도에 없던 장애물
    state.current_command = "stop"
    state.current_path = []                       # 옛 경로 버리기
    pos = arrived                                 # 지금 서 있는 칸 중앙에서 재탐색
    _save_robot(pos, "obstacle_detected")

    result = replan(grid, pos, goal, move, blocked_cells, a_star,
                    lambda p: path_to_commands(p, "north"), cell=cell)
    if result["status"] == "replanned":
        state.current_path = result["commands"].copy()
    result["obstacle_cell_index"] = n
    return result


@router.get("/robot/blocked")
def get_blocked():
    return {"blocked_cells": sorted(blocked_cells)}