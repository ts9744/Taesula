import json

from fastapi import APIRouter, HTTPException

from server.database import get_db
from server.schemas.request_models import GridMapRequest


router = APIRouter()


def validate_start_cell(raw_grid):
    """raw_grid 에 시작점(값 2)이 정확히 한 칸인지 확인한다. 아니면 400."""
    start_cells = [
        (x + 1, y + 1)
        for y, row in enumerate(raw_grid)
        for x, value in enumerate(row)
        if value == 2
    ]

    if not start_cells:
        raise HTTPException(
            status_code=400,
            detail="시작점이 없습니다. 시작점 모드로 한 칸을 지정한 뒤 저장하세요."
        )

    if len(start_cells) > 1:
        cells = ", ".join(f"({x}, {y})" for x, y in start_cells)
        raise HTTPException(
            status_code=400,
            detail=(
                f"시작점이 {len(start_cells)}칸입니다: {cells}. "
                "이동 가능 모드로 나머지 칸을 지우고 한 칸만 남긴 뒤 저장하세요."
            )
        )


def place_robot_if_invalid(cursor, grid_data):
    cursor.execute("SELECT current_x, current_y FROM robot_status WHERE id = 1")
    row = cursor.fetchone()

    if row and row[0] is not None and row[1] is not None:
        x, y = row[0] - 1, row[1] - 1
        if (0 <= x < grid_data.cols and 0 <= y < grid_data.rows
                and grid_data.pathfinding_grid[y][x] != 1):
            return False

    start_x, start_y = next(
        (x + 1, y + 1)
        for y, cells in enumerate(grid_data.raw_grid)
        for x, value in enumerate(cells)
        if value == 2
    )

    if row:
        cursor.execute(
            "UPDATE robot_status SET current_x = ?, current_y = ?, status = 'idle' WHERE id = 1",
            (start_x, start_y)
        )
    else:
        cursor.execute(
            "INSERT INTO robot_status (id, current_x, current_y, status) VALUES (1, ?, ?, 'idle')",
            (start_x, start_y)
        )
    return True


@router.post("/grid-map")
def save_grid_map(grid_data: GridMapRequest):
    # try 밖에서 검사해야 아래 except Exception 에 잡혀 500 으로 바뀌지 않는다
    validate_start_cell(grid_data.raw_grid)

    raw_grid_json = json.dumps(grid_data.raw_grid, ensure_ascii=False)
    pathfinding_grid_json = json.dumps(
        grid_data.pathfinding_grid,
        ensure_ascii=False
    )

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

        # 로봇 위치는 건드리지 않는다. 시작점(홈)을 바꿔도 로봇은 실제로 그 자리에 있기 때문.
        # 위치가 없거나(처음 설정) 새 지도 밖이거나 장애물 칸일 때만 시작점에 둔다.
        robot_placed = place_robot_if_invalid(cursor, grid_data)

        conn.commit()

        return {
            "message": "grid map saved",
            "rows": grid_data.rows,
            "cols": grid_data.cols,
            "robot_placed_at_start": robot_placed
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"grid map save error: {e}"
        )

    finally:
        if conn:
            conn.close()


@router.get("/grid-map")
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
