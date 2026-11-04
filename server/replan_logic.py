"""장애물이 나왔을 때 '막힌 칸 계산 -> 다른 길 다시 찾기'만 담당하는 순수 파이썬 모듈.

FastAPI/DB를 전혀 쓰지 않으므로 서버 없이 테스트할 수 있다.
좌표 규칙은 서버(route.py)와 같다:
  - 격자는 grid[y][x], 값 1이 장애물
  - 위(north)는 y 감소 = forward, 오른쪽(east)은 x 증가 = right
  - 로봇 방향은 항상 north 고정 (횡이동)
"""
import math
import time

# 현장 치수 (실제 로봇으로 재서 맞출 것)
CELL_CM = 50.0           # 한 칸
SENSOR_OFFSET_CM = 10.0  # 센서에서 로봇 중심까지
DETECT_CM = 100.0        # 장애물 탐지 범위(약 두 칸)

# route.py 의 path_to_commands(start_direction="north") 와 동일한 대응
MOVE_DELTA = {
    "forward": (0, -1),
    "backward": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
}


def blocked_cell_for(pos, command):
    """로봇이 pos 에서 command 로 가려던 칸. 이동 명령이 아니면 None."""
    d = MOVE_DELTA.get(command)
    if d is None:
        return None
    return (pos[0] + d[0], pos[1] + d[1])


def known_beyond_next(grid, pos, command):
    """가는 방향으로 목적지 칸 바로 앞 칸이 지도 장애물(또는 지도 밖 = 실제 벽)이면 True.

    이동 중 센서는 목적지 칸 너머를 보므로, 그곳의 지도 장애물에 걸린 감지는 '예상된 장애물'이다.
    """
    d = MOVE_DELTA.get(command)
    if d is None:
        return False
    x, y = pos[0] + 2 * d[0], pos[1] + 2 * d[1]
    rows, cols = len(grid), len(grid[0])
    if not (0 <= x < cols and 0 <= y < rows):
        return True
    return grid[y][x] == 1


def distance_to_known_cm(grid, pos, command, max_cells=4):
    """이동 시작 시점에, 가는 방향의 지도 장애물/벽(지도 밖)까지 센서가 재게 될 거리(cm).

    다음 칸(B)은 경로가 지나가는 빈 칸이므로 그 너머(2번째 칸부터)를 본다. 없으면 None.
    """
    d = MOVE_DELTA.get(command)
    if d is None:
        return None
    rows, cols = len(grid), len(grid[0])
    for n in range(2, max_cells + 1):
        x, y = pos[0] + n * d[0], pos[1] + n * d[1]
        if not (0 <= x < cols and 0 <= y < rows) or grid[y][x] == 1:
            return CELL_CM / 2 - SENSOR_OFFSET_CM + CELL_CM * (n - 1)
    return None


def locate_obstacle(pos, command, distance_cm, moved_cm):
    """센서 값으로 장애물이 출발 칸(pos)에서 몇 번째 칸에 있는지 구한다. 1 = 다음 칸.

    출발 칸 중앙에서의 거리 = 센서 값 + 이미 이동한 거리 + 센서~로봇 중심.
    반환: (n, (x, y)) 또는 이동 명령이 아니면 (None, None)
    """
    d = MOVE_DELTA.get(command)
    if d is None:
        return None, None
    s = distance_cm + moved_cm + SENSOR_OFFSET_CM
    n = max(1, math.ceil((s - CELL_CM / 2) / CELL_CM))
    return n, (pos[0] + n * d[0], pos[1] + n * d[1])


def in_known_map(grid, cell):
    """그 칸이 지도 장애물이거나 지도 밖(실제 벽)이면 True."""
    x, y = cell
    rows, cols = len(grid), len(grid[0])
    return not (0 <= x < cols and 0 <= y < rows) or grid[y][x] == 1


def drop_expired(blocked, now, ttl_sec):
    """ttl_sec 이 지난 센서 장애물은 목록에서 뺀다 (치워졌을 수 있으므로)."""
    for cell in [c for c, t in blocked.items() if now - t >= ttl_sec]:
        del blocked[cell]


def replan(grid, pos, goal, command, blocked, a_star, to_commands,
           ttl_sec=30.0, now=None, cell=None):
    """장애물을 만난 뒤 새 경로를 만든다.

    grid        : pathfinding_grid (원본은 건드리지 않는다)
    pos, goal   : (x, y) 0부터 시작하는 격자 좌표
    command     : 로봇이 마지막으로 받은 명령 (forward/left/...)
    blocked     : {(x, y): 감지된 시각} - 서버가 계속 들고 있는 딕셔너리
    a_star      : 기존 algorithm.astar.a_star(grid, start, goal)
    to_commands : 좌표 경로 -> 명령 리스트 (route.py 의 path_to_commands 를 감싼 것)
    cell        : 막힌 칸을 직접 지정 (없으면 pos 에서 command 방향 바로 다음 칸)
    반환: {"status": "replanned"|"no_path"|"ignored", ...}
    """
    now = time.time() if now is None else now
    drop_expired(blocked, now, ttl_sec)

    if cell is None:
        cell = blocked_cell_for(pos, command)
    rows, cols = len(grid), len(grid[0])
    if cell is None:
        return {"status": "ignored", "reason": "이동 명령이 아님"}
    if not (0 <= cell[0] < cols and 0 <= cell[1] < rows):
        return {"status": "ignored", "reason": "격자 밖 (벽)"}
    if cell == tuple(goal):
        # 목적지 칸 자체가 막힘: 길을 바꿔도 소용없으니 정지하고 알린다
        return {"status": "no_path", "blocked_cell": cell,
                "reason": "목적지가 막힘"}

    blocked[cell] = now

    work = [row[:] for row in grid]
    for (x, y) in blocked:
        if 0 <= x < cols and 0 <= y < rows and (x, y) != tuple(pos):
            work[y][x] = 1

    path = a_star(work, tuple(pos), tuple(goal))
    if path is None:
        return {"status": "no_path", "blocked_cell": cell,
                "blocked_cells": sorted(blocked)}

    return {
        "status": "replanned",
        "blocked_cell": cell,
        "blocked_cells": sorted(blocked),
        "path": [list(p) for p in path],
        "commands": to_commands(path),
    }