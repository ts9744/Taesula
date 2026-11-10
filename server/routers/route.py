from fastapi import APIRouter

from algorithm.astar import a_star
from server import state
from server.database import get_db, load_grid_from_db
from server.routers import obstacle


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


def robot_busy():
    """배송·도착 후 대기·복귀 중이거나, 대기열에 먼저 들어온 물품이 있으면 True.
    이때 새로 인식한 물품은 바로 출발하지 않고 대기열 뒤에 선다."""
    return (
        getattr(state, "mission", None) is not None
        or getattr(state, "return_at", None) is not None
        or bool(state.current_path)
        or getattr(state, "pending_move", None) is not None
        or bool(state.delivery_queue)
    )


def enqueue(qr_code):
    """물품을 대기열 뒤에 넣는다. 등록되지 않은 QR은 넣지 않는다."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM items WHERE qr_code = ?", (qr_code,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {"message": "item not found"}

    cursor.execute("UPDATE items SET status = 'queued' WHERE qr_code = ?", (qr_code,))
    conn.commit()
    conn.close()

    state.delivery_queue.append(qr_code)
    return {
        "message": "queued",
        "qr_code": qr_code,
        "item_name": row[0],
        "queue_position": len(state.delivery_queue),
        "current_qr": state.current_item_qr,
    }


@router.get("/route/{qr_code}")
def get_route_by_qr(qr_code: str):
    with state.lock:
        # 같은 물품을 이미 운반 중이면 경로를 새로 만들지 않는다
        # (여러 화면에서 같은 QR을 동시에 인식하는 경우)
        if state.current_item_qr == qr_code and getattr(state, "mission", None) == "deliver":
            return {"message": "already delivering", "qr_code": qr_code}

        if qr_code in state.delivery_queue:
            return {
                "message": "already queued",
                "qr_code": qr_code,
                "queue_position": state.delivery_queue.index(qr_code) + 1,
            }

        # 다른 배송이 진행 중이면 대기열로.
        # 지금 배송 -> 도착 -> 시작점 복귀까지 끝난 뒤 시작점에서 출발한다 (home.maybe_start_queued)
        if robot_busy():
            return enqueue(qr_code)

        return start_delivery(qr_code)


def start_delivery(qr_code):
    """로봇의 현재 위치(DB)에서 물품 목적지까지 경로를 만들고 배송을 시작한다.
    /route 와 대기열 출발(home.maybe_start_queued)이 함께 쓴다. state.lock 안에서 부른다."""
    # 이동 중에 새 경로를 만들면 진행 중인 이동이 위치에 반영되지 않아 DB 위치가 어긋난다.
    # 브리지가 이미 보낸 이동은 끝난 것으로 먼저 반영하고, 그 칸을 시작점으로 쓴다.
    # (이동이 실패하면 브리지가 halt 하므로 이후 경로는 실행되지 않는다)
    if getattr(state, "pending_move", None) is not None:
        obstacle.commit_pending_move()

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

    # 로봇은 메카넘휠 횡이동 방식이라 회전하지 않는다.
    # 항상 격자의 북쪽(위쪽)을 바라보도록 놓고 시작하는 것을 기준으로 한다.
    start_direction = "north"

    # 8. 좌표 경로를 JSON 응답용 리스트와 ESP32 명령 리스트로 변환
    path_list = [[x, y] for x, y in path]
    command_path = path_to_commands(path, start_direction)

    # 이전 배송이 끝나기 전에 새 배송으로 덮어쓰면, 이전 물품은 arrived 로 바뀔 기회가 없어
    # moving 에 계속 남는다. 대기 상태로 되돌린다.
    previous_qr = state.current_item_qr
    if previous_qr and previous_qr != item_qr_code:
        conn = get_db()
        conn.execute(
            "UPDATE items SET status = 'waiting' WHERE qr_code = ? AND status = 'moving'",
            (previous_qr,)
        )
        conn.commit()
        conn.close()

    # 9. /next-command API에서 순차적으로 가져갈 수 있도록 명령 경로 저장
    state.current_path = command_path.copy()
    state.goal = goal
    state.current_item_qr = item_qr_code
    state.current_steps = 0
    state.mission = "deliver"
    state.return_at = None          # 복귀 대기 중에 새 배송이 들어오면 복귀 예약 취소

    # 배송 시작: 물품과 로봇 상태를 이동 중으로 변경
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE items SET status = 'moving' WHERE qr_code = ?",
        (item_qr_code,)
    )
    cursor.execute("UPDATE robot_status SET status = 'moving' WHERE id = 1")
    conn.commit()
    conn.close()

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
