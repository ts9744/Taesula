from fastapi import APIRouter

from server.database import get_db


router = APIRouter()


@router.get("/robot/status")
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


@router.put("/robot/status")
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
