from typing import Literal
from pathlib import Path
import sys
import json
import sqlite3

import cv2
from fastapi import FastAPI
from fastapi import HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# =========================
# CONFIG
# =========================

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

DB_PATH = BASE_DIR / "SIDA_system.db"

from algorithm.astar import a_star
from camera.camera import get_camera, generate_camera_stream

# =========================
# FASTAPI APP
# =========================

app = FastAPI(
    title="Robot Communication API",
    description="Raspberry Pi와 ESP32 간 로봇 명령 및 상태 데이터 통신을 위한 API 서버",
    version="1.0.0"
)

# =========================
# DATABASE UTILS
# =========================

def get_db():
    return sqlite3.connect(DB_PATH)

def load_grid_from_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT pathfinding_grid
        FROM grid_map
        WHERE id = 1
    """)

    row = cursor.fetchone()
    conn.close()

    if not row or row[0] is None:
        return None

    return json.loads(row[0])

# =========================
# ROBOT COMMAND STATE & PATH UTILS
# =========================

current_command = "stop"
current_path = []
test_command = "stop"
test_command_ready = False

TestCommand = Literal["forward", "backward", "left", "right", "stop"]

class TestCommandRequest(BaseModel):
    command: TestCommand

DIRECTIONS = ["north", "east", "south", "west"]

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

def get_turn_commands(current_direction, target_direction):
    current_idx = DIRECTIONS.index(current_direction)
    target_idx = DIRECTIONS.index(target_direction)

    diff = (target_idx - current_idx) % 4

    if diff == 0:
        return []
    elif diff == 1:
        return ["right"]
    elif diff == 3:
        return ["left"]
    elif diff == 2:
        return ["right", "right"]

    return []


def path_to_commands(path, start_direction="east"):
    commands = []
    current_direction = start_direction

    for i in range(1, len(path)):
        prev_pos = path[i - 1]
        next_pos = path[i]

        target_direction = get_target_direction(prev_pos, next_pos)

        if target_direction is None:
            continue

        turn_commands = get_turn_commands(current_direction, target_direction)

        commands.extend(turn_commands)
        commands.append("forward")

        current_direction = target_direction

    commands.append("stop")
    return commands

# =========================
# REQUEST MODELS
# =========================

class CommandRequest(BaseModel):
    direction: Literal["forward", "backward", "left", "right", "stop"]


class PathRequest(BaseModel):
    path: list[Literal["forward", "backward", "left", "right", "stop"]]

class GridMapRequest(BaseModel):
    rows: int
    cols: int
    raw_grid: list[list[int]]
    pathfinding_grid: list[list[int]]
      
# =========================
# BASIC STATUS & COMMAND API
# =========================

@app.get("/")
def root():
    return {"message": "robot communication server is running"}


@app.get("/status")
def get_status():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id, current_x, current_y, status FROM robot_status WHERE id=1")
    row = cursor.fetchone()

    conn.close()

    if row:
        robot_db_status = {
            "id": row[0],
            "current_x": row[1],
            "current_y": row[2],
            "status": row[3]
        }
    else:
        robot_db_status = {
            "id": 1,
            "current_x": None,
            "current_y": None,
            "status": "not_initialized"
        }

    return {
        "robot_status": robot_db_status,
        "current_command": current_command,
        "current_path": current_path
    }

@app.get("/command")
def get_command():
    return {"direction": current_command}

@app.post("/test-command")
def set_test_command(request: TestCommandRequest):
    global test_command, test_command_ready

    test_command = request.command
    test_command_ready = True

    return {
        "message": "test command set",
        "command": test_command,
        "ready": test_command_ready
    }


@app.get("/test-command")
def get_test_command():
    global test_command, test_command_ready

    if not test_command_ready:
        return {
            "direction": "stop",
            "source": "test-command",
            "message": "no test command"
        }

    command_to_send = test_command

    # ESP32가 한 번 받아가면 다시 stop 상태로 초기화
    test_command = "stop"
    test_command_ready = False

    return {
        "direction": command_to_send,
        "source": "test-command",
        "message": "test command consumed"
    }

@app.get("/next-command")
def get_next_command():
    global current_command, current_path

    if not current_path:
        current_command = "stop"
        return {
            "direction": "stop",
            "message": "path is empty",
            "remaining_path": current_path
        }

    current_command = current_path.pop(0)

    return {
        "direction": current_command,
        "remaining_path": current_path
    }

@app.post("/command")
def set_command(command: CommandRequest):
    global current_command

    current_command = command.direction

    return {
        "message": "command updated",
        "direction": current_command
    }


@app.post("/path")
def set_path(path_data: PathRequest):
    global current_path

    current_path = path_data.path

    return {
        "message": "path updated",
        "path": current_path
    }

# =========================
# ITEMS API
# =========================

# CREATE
@app.post("/items")
def create_item(name: str, qr_code: str, destination_id: int):
    conn = None

    try:
        conn = get_db()
        cursor = conn.cursor()

        # 같은 이름의 item이 이미 있는지 확인
        cursor.execute(
            "SELECT id FROM items WHERE name=?",
            (name,)
        )
        duplicate_name = cursor.fetchone()

        if duplicate_name:
            raise HTTPException(
                status_code=400,
                detail="이미 같은 이름의 item이 존재합니다."
            )

        # 같은 qr_code의 item이 이미 있는지 확인
        cursor.execute(
            "SELECT id FROM items WHERE qr_code=?",
            (qr_code,)
        )
        duplicate_qr = cursor.fetchone()

        if duplicate_qr:
            raise HTTPException(
                status_code=400,
                detail="이미 같은 qr_code를 가진 item이 존재합니다."
            )

        cursor.execute(
            "INSERT INTO items (name, qr_code, destination_id) VALUES (?, ?, ?)",
            (name, qr_code, destination_id)
        )

        conn.commit()

        return {
            "message": "item created",
            "name": name,
            "qr_code": qr_code,
            "destination_id": destination_id
        }

    except sqlite3.OperationalError as e:
        raise HTTPException(
            status_code=500,
            detail=f"DB 처리 중 오류가 발생했습니다: {e}"
        )

    finally:
        if conn:
            conn.close()

# READ ALL
@app.get("/items")
def get_items():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id, name, qr_code, destination_id, status FROM items")
    rows = cursor.fetchall()

    conn.close()

    return [
        {
            "id": row[0],
            "name": row[1],
            "qr_code": row[2],
            "destination_id": row[3],
            "status": row[4]
        }
        for row in rows
    ]

# READ (QR 기준)
@app.get("/items/{qr_code}")
def get_item(qr_code: str):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            items.id,
            items.name,
            items.qr_code,
            items.status,
            locations.id,
            locations.zone_name,
            locations.x,
            locations.y
        FROM items
        JOIN locations
        ON items.destination_id = locations.id
        WHERE items.qr_code = ?
    """, (qr_code,))

    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "item_id": row[0],
            "name": row[1],
            "qr_code": row[2],
            "status": row[3],
            "destination": {
                "location_id": row[4],
                "zone_name": row[5],
                "x": row[6],
                "y": row[7]
            }
        }

    return {"message": "not found"}


# UPDATE
@app.put("/items/{qr_code}")
def update_item(qr_code: str, name: str, destination_id: int):
    conn = None

    try:
        conn = get_db()
        cursor = conn.cursor()

        # 수정 대상 item 존재 여부 확인
        cursor.execute(
            "SELECT id FROM items WHERE qr_code=?",
            (qr_code,)
        )
        target_item = cursor.fetchone()

        if not target_item:
            raise HTTPException(
                status_code=404,
                detail="수정할 item을 찾을 수 없습니다."
            )

        # 같은 이름을 가진 다른 item이 있는지 확인
        cursor.execute(
            "SELECT id FROM items WHERE name=? AND qr_code<>?",
            (name, qr_code)
        )
        duplicate_item = cursor.fetchone()

        if duplicate_item:
            raise HTTPException(
                status_code=400,
                detail="이미 같은 이름의 item이 존재합니다."
            )

        # item 정보 수정
        cursor.execute(
            "UPDATE items SET name=?, destination_id=? WHERE qr_code=?",
            (name, destination_id, qr_code)
        )

        conn.commit()

        return {
            "message": "item updated",
            "qr_code": qr_code,
            "name": name,
            "destination_id": destination_id
        }

    except sqlite3.OperationalError as e:
        raise HTTPException(
            status_code=500,
            detail=f"DB 처리 중 오류가 발생했습니다: {e}"
        )

    finally:
        if conn:
            conn.close()

# DELETE
@app.delete("/items/{qr_code}")
def delete_item(qr_code: str):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM items WHERE qr_code=?",
        (qr_code,)
    )

    conn.commit()
    conn.close()

    return {"message": "deleted"}

# =========================
# ROUTE API
# =========================

@app.get("/route/{qr_code}")
def get_route_by_qr(qr_code: str):
    global current_path

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

    current_x = robot_row[0]
    current_y = robot_row[1]
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
    
    start_direction = "east"

    # 8. 좌표 경로를 JSON 응답용 리스트와 ESP32 명령 리스트로 변환
    path_list = [[x, y] for x, y in path]
    command_path = path_to_commands(path, start_direction)

    # 9. /next-command API에서 순차적으로 가져갈 수 있도록 명령 경로 저장
    current_path = command_path.copy()

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

# =========================
# LOCATIONS API
# =========================

@app.post("/grid-map")
def save_grid_map(grid_data: GridMapRequest):
    raw_grid_json = json.dumps(grid_data.raw_grid, ensure_ascii=False)
    pathfinding_grid_json = json.dumps(grid_data.pathfinding_grid, ensure_ascii=False)

    conn = None

    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS grid_map (
                id INTEGER PRIMARY KEY,
                rows INTEGER NOT NULL,
                cols INTEGER NOT NULL,
                raw_grid TEXT NOT NULL,
                pathfinding_grid TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("SELECT id FROM grid_map WHERE id = 1")
        row = cursor.fetchone()

        if row:
            cursor.execute("""
                UPDATE grid_map
                SET rows = ?,
                    cols = ?,
                    raw_grid = ?,
                    pathfinding_grid = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = 1
            """, (
                grid_data.rows,
                grid_data.cols,
                raw_grid_json,
                pathfinding_grid_json
            ))
        else:
            cursor.execute("""
                INSERT INTO grid_map (
                    id,
                    rows,
                    cols,
                    raw_grid,
                    pathfinding_grid
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                1,
                grid_data.rows,
                grid_data.cols,
                raw_grid_json,
                pathfinding_grid_json
            ))

        conn.commit()

        return {
            "message": "grid map saved",
            "rows": grid_data.rows,
            "cols": grid_data.cols
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"grid map save error: {e}"
        )

    finally:
        if conn:
            conn.close()


@app.get("/grid-map")
def get_grid_map():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, rows, cols, raw_grid, pathfinding_grid, updated_at
        FROM grid_map
        WHERE id = 1
    """)

    row = cursor.fetchone()
    conn.close()

    if not row:
        return {
            "message": "grid map not found"
        }

    return {
        "id": row[0],
        "rows": row[1],
        "cols": row[2],
        "raw_grid": json.loads(row[3]),
        "pathfinding_grid": json.loads(row[4]),
        "updated_at": row[5]
    }

@app.post("/locations")
def create_location(zone_name: str, x: int, y: int):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO locations (zone_name, x, y) VALUES (?, ?, ?)",
        (zone_name, x, y)
    )

    conn.commit()
    conn.close()

    return {"message": "location created"}

@app.get("/locations")
def get_locations():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id, zone_name, x, y FROM locations")
    rows = cursor.fetchall()

    conn.close()

    return [
        {
            "id": row[0],
            "zone_name": row[1],
            "x": row[2],
            "y": row[3]
        }
        for row in rows
    ]

# UPDATE
@app.put("/locations/{location_id}")
def update_location(location_id: int, zone_name: str, x: int, y: int):
    conn = None

    try:
        conn = get_db()
        cursor = conn.cursor()

        # 수정 대상 location 존재 여부 확인
        cursor.execute(
            "SELECT id FROM locations WHERE id=?",
            (location_id,)
        )
        target_location = cursor.fetchone()

        if not target_location:
            raise HTTPException(
                status_code=404,
                detail="수정할 location을 찾을 수 없습니다."
            )

        # 같은 이름을 가진 다른 location이 있는지 확인
        cursor.execute(
            "SELECT id FROM locations WHERE zone_name=? AND id<>?",
            (zone_name, location_id)
        )
        duplicate_location = cursor.fetchone()

        if duplicate_location:
            raise HTTPException(
                status_code=400,
                detail="이미 같은 이름의 location이 존재합니다."
            )

        cursor.execute(
            "UPDATE locations SET zone_name=?, x=?, y=? WHERE id=?",
            (zone_name, x, y, location_id)
        )

        conn.commit()

        return {
            "message": "location updated",
            "id": location_id,
            "zone_name": zone_name,
            "x": x,
            "y": y
        }

    except sqlite3.OperationalError as e:
        raise HTTPException(
            status_code=500,
            detail=f"DB 처리 중 오류가 발생했습니다: {e}"
        )

    finally:
        if conn:
            conn.close()


# DELETE
@app.delete("/locations/{location_id}")
def delete_location(location_id: int):
    conn = None

    try:
        conn = get_db()
        cursor = conn.cursor()

        # 삭제 대상 location 존재 여부 확인
        cursor.execute(
            "SELECT id FROM locations WHERE id=?",
            (location_id,)
        )
        target_location = cursor.fetchone()

        if not target_location:
            raise HTTPException(
                status_code=404,
                detail="삭제할 location을 찾을 수 없습니다."
            )

        # 해당 location을 목적지로 사용하는 item이 있는지 확인
        cursor.execute(
            "SELECT id FROM items WHERE destination_id=?",
            (location_id,)
        )
        linked_item = cursor.fetchone()

        if linked_item:
            raise HTTPException(
                status_code=400,
                detail="해당 location을 목적지로 사용하는 item이 있어 삭제할 수 없습니다."
            )

        cursor.execute(
            "DELETE FROM locations WHERE id=?",
            (location_id,)
        )

        conn.commit()

        return {
            "message": "location deleted",
            "id": location_id
        }

    except sqlite3.OperationalError as e:
        raise HTTPException(
            status_code=500,
            detail=f"DB 처리 중 오류가 발생했습니다: {e}"
        )

    finally:
        if conn:
            conn.close()

# =========================
# ITEM STATUS API
# =========================

@app.put("/items/{qr_code}/status")
def update_item_status(qr_code: str, status: str):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE items SET status=? WHERE qr_code=?",
        (status, qr_code)
    )

    conn.commit()
    conn.close()

    return {
        "message": "item status updated",
        "qr_code": qr_code,
        "status": status
    }

# =========================
# ROBOT STATUS API
# =========================

@app.get("/robot/status")
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


@app.put("/robot/status")
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


# =========================
# CAMERA API
# =========================

qr_detector = cv2.QRCodeDetector()

# 라즈베리파이의 카메라를 통해 사진을 찍어 인식하는 부분
@app.get("/camera/qr")
def read_qr_from_camera():
    try:
        cam = get_camera()
        frame = cam.capture_array()

        qr_data, points, _ = qr_detector.detectAndDecode(frame)

        if qr_data:
            return {
                "detected": True,
                "qr_code": qr_data
            }

        return {
            "detected": False,
            "qr_code": None
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/camera/stream")
def camera_stream():
    return StreamingResponse(
        generate_camera_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

# =========================
# SERVER RUNNER
# =========================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
