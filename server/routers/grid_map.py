import json

from fastapi import APIRouter, HTTPException

from server.database import get_db
from server.schemas.request_models import GridMapRequest


router = APIRouter()


@router.post("/grid-map")
def save_grid_map(grid_data: GridMapRequest):
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