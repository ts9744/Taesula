"""server/routers/obstacle.py 로 넣을 파일 (로컬 테스트용, GitHub 에 올리지 않음).

흐름
  - /next-command 가 이동 명령을 내보낼 때 mark_dispatched() 를 부른다 (command.py 에서 호출).
      -> 이 이동을 '진행 중'으로 기록하고, ESP32 에 detect_cm / known_cm 를 돌려준다.
  - 다음 /next-command 가 오면 commit_pending_move() 가 '앞 이동이 끝났다'고 보고 DB 위치를 한 칸 옮긴다.
  - ESP32 가 지도에 없던 장애물을 확정하면 POST /robot/obstacle 로 보고한다.
      * 장애물이 다음 칸 안  : ESP32 가 출발 칸 중앙으로 되돌아온 상태(completed=false) -> 위치 그대로 재탐색
      * 장애물이 그 너머     : ESP32 가 이번 이동을 끝까지 마친 상태(completed=true)  -> 도착 칸에서 재탐색
"""
import time

from fastapi import APIRouter
from pydantic import BaseModel

from algorithm.astar import a_star
from server import state
from server.database import get_db, load_grid_from_db
from server.routers.route import path_to_commands
from server.replan_logic import (
    replan, MOVE_DELTA, DETECT_CM, CELL_CM, SENSOR_OFFSET_CM,
    distance_to_known_cm, locate_obstacle, in_known_map, plan_with_release, drop_expired,
)

router = APIRouter()
blocked_cells = {}          # {(x, y): 감지 시각}  - 서버 메모리에만 저장
BLOCK_TTL_SEC = 30.0        # 막은 지 이 시간이 지나면 자동으로 푼다 (그 길로 가 보다가 아직 있으면 다시 막힌다)
RETRY_SEC = 10.0            # 길이 없을 때 재시도 간격
MAX_RETRIES = 4             # 이만큼 해도 안 되면 사람이 앱에서 직접 처리 (manual_required)
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
        for i in range(1, steps + 1):             # 실제로 지나간 칸은 비어 있었던 것
            blocked_cells.pop((pos[0] + d[0] * i, pos[1] + d[1] * i), None)
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
        state.nav_status, state.probing, state.retry_count = "idle", False, 0
        pos = _robot_pos()
        if pos is not None:
            _save_robot(pos, "idle")
        return extras

    if getattr(state, "skip_detect", False):      # 지도와 어긋난 오탐이었던 이동을 다시 시도하는 중
        state.skip_detect = False
        return extras

    if cmd in HAS_SENSOR:
        extras["detect_cm"] = DETECT_CM
        extras["check_blocked"] = _blocked_ahead(_robot_pos(), cmd)
        pos, grid = _robot_pos(), load_grid_from_db()
        if pos is not None and grid is not None:
            extras["known_cm"] = distance_to_known_cm(grid, pos, cmd)   # 묶음 시작 칸 기준
    return extras


def _blocked_ahead(pos, cmd):
    """가는 방향 탐지 범위 안에 막아 둔 칸이 있는가 (있으면 ESP32 가 센서 값을 서버에 알려 준다)."""
    d = MOVE_DELTA.get(cmd)
    if pos is None or d is None:
        return False
    n_max = int((DETECT_CM + SENSOR_OFFSET_CM - CELL_CM / 2) // CELL_CM) + 1
    return any((pos[0] + d[0] * n, pos[1] + d[1] * n) in blocked_cells for n in range(1, n_max + 1))


def idle_extras():
    """/next-command 가 'stop' 을 돌려줄 때 덧붙인다. 길이 없어 기다리는 중이면 제자리에서 센서를 계속 읽어 알려 달라고 한다."""
    if blocked_cells and getattr(state, "nav_status", None) in ("no_path", "manual_required"):
        return {"scan": True, "detect_cm": DETECT_CM}
    return {}


def expire_blocked(now=None):
    drop_expired(blocked_cells, time.time() if now is None else now, BLOCK_TTL_SEC)


class ClearReport(BaseModel):
    direction: str            # 센서 방향 (forward/left/right)
    distance_cm: float = -1   # 센서 값. 측정 안 됨(에코 없음)이면 -1 = 탐지 범위 안에 아무것도 없음
    moved_cm: float = 0.0     # 그 방향으로 이미 이동한 거리 (제자리면 0)


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
                    lambda p: path_to_commands(p, "north"), ttl_sec=BLOCK_TTL_SEC, cell=cell)
    if result["status"] == "replanned":
        state.current_path = result["commands"].copy()
        state.nav_status, state.retry_count, state.probing = "moving", 0, False
    else:                                         # 길이 없음: 잠시 뒤 막힌 칸을 하나씩 풀어 보며 재시도
        if not getattr(state, "probing", False):  # 풀어 본 칸이 또 막힌 경우에는 재시도 횟수를 이어간다
            state.retry_count = 0
        state.probing = False
        state.nav_status = "no_path"
        state.retry_at = time.time() + RETRY_SEC
        result["retry_in_sec"] = RETRY_SEC
    result["obstacle_cell_index"] = n
    return result


def _plan_release(release_count):
    pos, goal, grid = _robot_pos(), getattr(state, "goal", None), load_grid_from_db()
    if pos is None or goal is None or grid is None:
        return None, pos
    plan = plan_with_release(grid, pos, goal, blocked_cells, a_star,
                             lambda p: path_to_commands(p, "north"), release_count)
    return plan, pos


def try_retry(now=None):
    """/next-command 맨 앞에서 부른다. 길이 없어 기다리는 중이면 때가 됐을 때 막힌 칸을 오래된 것부터 풀고 다시 길을 찾는다.
    풀어 본 칸이 정말 비었는지는 로봇이 가다가 센서로 확인한다 (아직 있으면 다시 막힌다)."""
    now = time.time() if now is None else now
    expire_blocked(now)
    if getattr(state, "nav_status", None) != "no_path":
        return
    if now < getattr(state, "retry_at", 0):
        return
    k = getattr(state, "retry_count", 0) + 1
    if k > MAX_RETRIES:
        state.nav_status = "manual_required"      # 앱에서 사람이 처리
        return
    state.retry_count = k
    plan, pos = _plan_release(k - 1)             # 첫 재시도는 아무것도 풀지 않고, 이후 오래된 칸부터 하나씩 더 푼다
    if plan is None:
        state.retry_at = now + RETRY_SEC
        return
    for c in plan["released"]:
        blocked_cells.pop(tuple(c), None)
    state.current_path = plan["commands"].copy()
    state.nav_status, state.probing = "moving", True
    _save_robot(pos, "moving")


@router.post("/robot/resume")
def resume():
    """앱에서 사람이 '다시 시도'를 눌렀을 때: 막힌 칸을 모두 풀고 처음부터 길을 찾는다."""
    plan, pos = _plan_release(len(blocked_cells))
    if plan is None:
        return {"status": "no_path", "nav_status": getattr(state, "nav_status", None)}
    for c in plan["released"]:
        blocked_cells.pop(tuple(c), None)
    state.current_path = plan["commands"].copy()
    state.nav_status, state.retry_count, state.probing = "moving", 0, False
    _save_robot(pos, "moving")
    return {"status": "resumed", "path": plan["path"], "commands": plan["commands"]}


@router.post("/robot/clear")
def report_clear(r: ClearReport):
    """센서가 그 방향이 비어 있다고 알려 줄 때: 막아 둔 칸이 센서 값보다 가까우면(= 센서가 그 칸을 통과해 더 멀리 봤으면) 푼다."""
    pos = _robot_pos()
    d = MOVE_DELTA.get(r.direction)
    if pos is None or d is None or r.direction not in HAS_SENSOR:
        return {"released": []}
    reach = (r.distance_cm if r.distance_cm > 0 else DETECT_CM) + r.moved_cm + SENSOR_OFFSET_CM
    released = []
    for n in range(1, 6):
        if reach < CELL_CM * n + CELL_CM / 2 + 5:   # 이 칸의 먼 쪽 끝까지 못 봤으면 여기서 멈춘다
            break
        cell = (pos[0] + d[0] * n, pos[1] + d[1] * n)
        if blocked_cells.pop(cell, None) is not None:
            released.append(list(cell))
    if released and getattr(state, "nav_status", None) == "no_path":
        state.retry_at = 0                          # 풀렸으니 바로 다시 길을 찾아본다
    return {"released": released}


@router.get("/robot/obstacles")
def get_obstacles():
    """앱 격자 표시용. 좌표는 robot/status 와 같이 1부터 센다. 앱은 1~2초마다 호출하면 된다."""
    expire_blocked()
    now = time.time()
    pos, goal = _robot_pos(), getattr(state, "goal", None)

    path, cur = [], pos                      # 앞으로 갈 칸 (남은 명령을 칸으로 풀어 줌)
    for cmd in list(getattr(state, "current_path", []) or []):
        d = MOVE_DELTA.get(cmd)
        if cur is None or d is None:
            continue
        cur = (cur[0] + d[0], cur[1] + d[1])
        path.append([cur[0] + 1, cur[1] + 1])

    return {
        "nav_status": getattr(state, "nav_status", None) or "idle",   # idle / moving / no_path / manual_required
        "robot": None if pos is None else [pos[0] + 1, pos[1] + 1],
        "goal": None if goal is None else [goal[0] + 1, goal[1] + 1],
        "blocked": [{"x": c[0] + 1, "y": c[1] + 1,
                     "expires_in_sec": max(0, round(BLOCK_TTL_SEC - (now - t)))}
                    for c, t in sorted(blocked_cells.items())],
        "path": path,
        "retry_count": getattr(state, "retry_count", 0),
    }


@router.get("/robot/blocked")
def get_blocked():
    expire_blocked()
    return {"blocked_cells": sorted(blocked_cells),
            "nav_status": getattr(state, "nav_status", None),
            "retry_count": getattr(state, "retry_count", 0)}