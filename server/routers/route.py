from fastapi import APIRouter

from algorithm.astar import a_star
from server import state
from server.database import get_db, load_grid_from_db


router = APIRouter()


def get_target_direction(prev_pos, next_pos):
    prev_x, prev_y = prev_pos
    next_x, next_y = next_pos

    dx = next_x - prev_x
    dy = next_y - prev_y

    if dx == 1 and dy == 0:
        return "east"
    elif dx == -1 and dy == 0:
        return "west"
    elif dx == 0 and dy == 1:
        return "south"
    elif dx == 0 and dy == -1:
        return "north"

    return None


def path_to_commands(path, start_direction):
    commands = []

    for i in range(1, len(path)):
        prev_pos = path[i - 1]
        next_pos = path[i]

        target_direction = get_target_direction(prev_pos, next_pos)

        if target_direction is None:
            continue

        move_command = direction_to_move_command(
            target_direction,
            start_direction
        )
        commands.append(move_command)

    commands.append("stop")
    return commands


def direction_to_move_command(target_direction, start_direction):
    directions = ["north", "east", "south", "west"]

    current_idx = directions.index(start_direction)
    target_idx = directions.index(target_direction)

    diff = (target_idx - current_idx) % 4

    if diff == 0:
        return "forward"
    elif diff == 1:
        return "right"
    elif diff == 2:
        return "backward"
    elif diff == 3:
        return "left"

    return "stop"


@router.get("/route/{qr_code}")
def get_route_by_qr(qr_code: str):
    conn = get_db()
    cursor = conn.cursor()

    # 1. QR 코드 기준으로 item 정보와 목적지 좌표 조회
    cursor.execute("""
        SELECT
            items.id,
            items.name,
            items.qr_code,
            items.status,
            locations.zone_name,
            locations.x,
            locations.y
        FROM items
        JOIN locations
        ON items.destination_id = locations.id
        WHERE items.qr_code = ?
    """, (qr_code,))

    item_row = cursor.fetchone()

    if not item_row:
        conn.close()
        return {"message": "item not found"}

    # 2. DB에 저장된 로봇 현재 위치와 상태 조회
    cursor.execute("""
        SELECT current_x, current_y, status
        FROM robot_status
        WHERE id = 1
    """)

    robot_row = cursor.fetchone()
    conn.close()

    if not robot_row:
        return {"message": "robot status not found"}

    # 3. grid_map 테이블에서 A*에 사용할 pathfinding_grid 조회
    grid = load_grid_from_db()

    if grid is None:
        return {
            "message": "grid map not found",
            "detail": "grid_map 테이블에 pathfinding_grid 데이터 필요"
        }

    # 4. 조회한 DB 결과를 경로 탐색에 사용할 값으로 분리
    item_id = item_row[0]
    item_name = item_row[1]
    item_qr_code = item_row[2]
    item_status = item_row[3]
    zone_name = item_row[4]
    goal_x = item_row[5] - 1
    goal_y = item_row[6] - 1

    current_x = robot_row[0] - 1
    current_y = robot_row[1] - 1
    robot_status = robot_row[2]

    start = (current_x, current_y)
    goal = (goal_x, goal_y)

    rows = len(grid)
    cols = len(grid[0])

    start_x, start_y = start
    goal_x_pos, goal_y_pos = goal

    # 5. 시작 좌표와 목적지 좌표가 grid 범위 안에 있는지 확인
    if not (0 <= start_x < cols and 0 <= start_y < rows):
        return {
            "message": "start position is out of grid range",
            "start": [start_x, start_y]
        }

    if not (0 <= goal_x_pos < cols and 0 <= goal_y_pos < rows):
        return {
            "message": "goal position is out of grid range",
            "goal": [goal_x_pos, goal_y_pos]
        }

    # 6. 시작점과 목적지가 장애물 칸인지 확인
    if grid[start_y][start_x] == 1:
        return {
            "message": "start position is obstacle",
            "start": [start_x, start_y]
        }

    if grid[goal_y_pos][goal_x_pos] == 1:
        return {
            "message": "goal position is obstacle",
            "goal": [goal_x_pos, goal_y_pos]
        }

    # 7. A* 알고리즘으로 현재 위치에서 목적지까지의 좌표 경로 탐색
    path = a_star(grid, start, goal)

    if path is None:
        return {
            "message": "path not found",
            "qr_code": item_qr_code,
            "item_name": item_name,
            "start": [start[0], start[1]],
            "goal": [goal[0], goal[1]]
        }

    # TODO: 시작 방향을 DB에서 조회해서 A*에 넘겨주고,
    # 그에 맞게 path_to_commands도 수정하기
    start_direction = "north"

    # 8. 좌표 경로를 JSON 응답용 리스트와 ESP32 명령 리스트로 변환
    path_list = [[x, y] for x, y in path]
    command_path = path_to_commands(path, start_direction)

    # 9. /next-command API에서 순차적으로 가져갈 수 있도록 명령 경로 저장
    state.current_path = command_path.copy()

    # 10. item, robot, destination, path 정보를 응답
    return {
        "message": "route found",
        "qr_code": item_qr_code,
        "item": {
            "item_id": item_id,
            "name": item_name,
            "status": item_status
        },
        "robot": {
            "current_x": current_x,
            "current_y": current_y,
            "status": robot_status,
            "start_direction": start_direction
        },
        "destination": {
            "zone_name": zone_name,
            "x": goal_x,
            "y": goal_y
        },
        "start": [start[0], start[1]],
        "goal": [goal[0], goal[1]],
        "path": path_list,
        "command_path": command_path
    }
