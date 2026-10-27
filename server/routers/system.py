from fastapi import APIRouter

from server import state
from server.database import get_db


router = APIRouter()


@router.get("/")
def root():
    return {"message": "robot communication server is running"}


@router.get("/status")
def get_status():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, current_x, current_y, status FROM robot_status WHERE id=1"
    )
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
        "current_command": state.current_command,
        "current_path": state.current_path
    }
